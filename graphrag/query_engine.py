"""
Hybrid RAG Query Engine

자연어 질의 → Cypher 변환 → FalkorDB 검색 → LLM 답변 생성

Features:
- Natural Language to Cypher translation
- Graph + Vector hybrid search
- Context-aware answer generation
"""

import json
import logging
import re
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

from .graph_schema import WolbuOntology, CYPHER_TEMPLATES

logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    """쿼리 결과 컨테이너"""
    query: str  # 원본 자연어 질의
    cypher: str  # 생성된 Cypher 쿼리
    graph_results: List[Dict]  # 그래프 검색 결과
    answer: str  # 최종 답변
    confidence: float  # 신뢰도
    sources: List[str]  # 참조 소스


# 자연어 → Cypher 변환용 시스템 프롬프트
CYPHER_GENERATION_PROMPT = """You are a Cypher query expert for a real estate investment knowledge graph.

## Graph Schema (Wolbu Ontology)

### Nodes:
- **Region**: {name, population, appropriate_demand, supply_risk_status}
- **ApartmentComplex**: {name, sales_price, jeonse_price, gap_price, jeonse_rate, is_undervalued, investment_comment}
- **GradeMetric**: {category (Jobs|Transport|School|Environment), grade (S|A|B|C), raw_value, evidence_text}
- **SupplyEvent**: {year, volume}

### Relationships:
- (:ApartmentComplex)-[:LOCATED_IN]->(:Region)
- (:Region)-[:HAS_GRADE]->(:GradeMetric)
- (:Region)-[:HAS_SUPPLY]->(:SupplyEvent)

### Investment Criteria (월급쟁이부자들):
- 전세가율(jeonse_rate) >= 60% → 투자 매력
- is_undervalued = true → 저평가 단지
- Grade S/A = 좋은 입지

## Task
Translate the user's natural language question into a valid Cypher query.

## Rules:
1. Return ONLY the Cypher query, no explanation
2. Use MATCH, WHERE, RETURN clauses
3. For grade filtering, use category and grade properties
4. Always return relevant node properties

## Examples:

User: 전세가율 60% 이상인 저평가 단지 찾아줘
Cypher:
```cypher
MATCH (c:ApartmentComplex)-[:LOCATED_IN]->(r:Region)
WHERE c.jeonse_rate >= 60 AND c.is_undervalued = true
RETURN c.name, c.jeonse_rate, c.gap_price, r.name as region
ORDER BY c.jeonse_rate DESC
LIMIT 20
```

User: 교통 S등급 지역의 아파트 단지들
Cypher:
```cypher
MATCH (c:ApartmentComplex)-[:LOCATED_IN]->(r:Region)
MATCH (r)-[:HAS_GRADE]->(g:GradeMetric {category: 'Transport', grade: 'S'})
RETURN c.name, r.name as region, g.grade as transport_grade
```

User: 부산진구 공급물량 조회
Cypher:
```cypher
MATCH (r:Region {name: '부산진구'})-[:HAS_SUPPLY]->(s:SupplyEvent)
RETURN s.year, s.volume
ORDER BY s.year
```
"""

# 답변 생성용 시스템 프롬프트
ANSWER_GENERATION_PROMPT = """You are a professional real estate investment analyst.
Based on the graph query results, provide a comprehensive investment analysis in Korean.

## Analysis Framework (월급쟁이부자들 기준):
- 전세가율 60% 이상: 갭투자 유리
- 저평가(is_undervalued): 상승 여력 있음
- 입지 등급 S/A: 장기 가치 보존

## Guidelines:
1. 데이터에 있는 정보만 언급 (할루시네이션 금지)
2. 구체적인 수치 인용
3. 투자 관점에서 분석
4. 리스크도 함께 언급
"""


class HybridRAGEngine:
    """하이브리드 RAG 쿼리 엔진
    
    자연어 질의를 처리하여:
    1. Cypher 쿼리로 변환
    2. FalkorDB에서 그래프 검색
    3. 검색 결과 기반 답변 생성
    """
    
    def __init__(self, graph, llm_client, model_name: str = None):
        """
        Args:
            graph: FalkorDB Graph 객체
            llm_client: OpenAI 호환 클라이언트 (llama.cpp/vLLM)
            model_name: 모델명 (None이면 환경변수에서 가져옴)
        """
        self.graph = graph
        self.llm = llm_client
        self.model_name = model_name or self._get_default_model()
        self.ontology = WolbuOntology()
    
    def _get_default_model(self) -> str:
        """기본 모델명"""
        import os
        return os.environ.get("LLM_MODEL", "Qwen/Qwen3-VL-30B-A3B-Instruct")
    
    def query(self, natural_language: str) -> QueryResult:
        """
        자연어 질의 처리
        
        Args:
            natural_language: 사용자 질문
            
        Returns:
            QueryResult 객체
        """
        logger.info(f"Processing query: {natural_language}")
        
        # 1. 자연어 → Cypher 변환
        cypher = self._generate_cypher(natural_language)
        logger.info(f"Generated Cypher: {cypher}")
        
        # 2. 그래프 검색
        graph_results = self._execute_cypher(cypher)
        logger.info(f"Graph returned {len(graph_results)} results")
        
        # 3. 답변 생성
        answer, confidence = self._generate_answer(natural_language, graph_results)
        
        # 4. 소스 추출
        sources = self._extract_sources(graph_results)
        
        return QueryResult(
            query=natural_language,
            cypher=cypher,
            graph_results=graph_results,
            answer=answer,
            confidence=confidence,
            sources=sources,
        )
    
    def _generate_cypher(self, question: str) -> str:
        """자연어 → Cypher 변환"""
        # 사전 정의된 쿼리 패턴 매칭 시도
        preset = self._match_preset_query(question)
        if preset:
            return preset
        
        # LLM으로 Cypher 생성
        messages = [
            {"role": "system", "content": CYPHER_GENERATION_PROMPT},
            {"role": "user", "content": f"Question: {question}\nCypher:"}
        ]
        
        response = self.llm.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=0.1,  # 결정적 출력
            max_tokens=500,
        )
        
        cypher_raw = response.choices[0].message.content
        
        # Cypher 추출 (마크다운 코드블록에서)
        cypher = self._extract_cypher(cypher_raw)
        
        return cypher
    
    def _match_preset_query(self, question: str) -> Optional[str]:
        """사전 정의된 쿼리 패턴 매칭"""
        question_lower = question.lower()
        
        # 저평가 단지 조회
        if "저평가" in question and ("단지" in question or "아파트" in question):
            jeonse_rate = 60.0
            # 전세가율 수치 추출 시도
            rate_match = re.search(r'(\d+)\s*%', question)
            if rate_match:
                jeonse_rate = float(rate_match.group(1))
            
            return CYPHER_TEMPLATES["find_undervalued"].replace(
                "$min_jeonse_rate", str(jeonse_rate)
            )
        
        # 특정 등급 조회
        for category in ["교통", "직장", "학군", "환경"]:
            if category in question:
                for grade in ["S", "A", "B", "C"]:
                    if grade in question.upper():
                        cat_map = {
                            "교통": "Transport",
                            "직장": "Jobs",
                            "학군": "School",
                            "환경": "Environment"
                        }
                        return CYPHER_TEMPLATES["find_by_grade"].replace(
                            "$category", f"'{cat_map[category]}'"
                        ).replace("$grade", f"'{grade}'")
        
        return None
    
    def _extract_cypher(self, text: str) -> str:
        """텍스트에서 Cypher 쿼리 추출"""
        # 코드블록 추출
        match = re.search(r'```(?:cypher)?\s*(.*?)```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        # MATCH로 시작하는 부분 찾기
        match = re.search(r'(MATCH\s+.*)', text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        return text.strip()
    
    def _execute_cypher(self, cypher: str) -> List[Dict]:
        """Cypher 쿼리 실행"""
        try:
            result = self.graph.query(cypher)
            
            # 결과를 딕셔너리 리스트로 변환
            if result.result_set:
                # 컬럼명 추출
                columns = result.header if hasattr(result, 'header') else [f"col_{i}" for i in range(len(result.result_set[0]))]
                
                return [
                    {columns[i]: row[i] for i in range(len(row))}
                    for row in result.result_set
                ]
            return []
        except Exception as e:
            logger.error(f"Cypher execution failed: {e}")
            return []
    
    def _generate_answer(self, question: str, results: List[Dict]) -> Tuple[str, float]:
        """검색 결과 기반 답변 생성"""
        if not results:
            return "검색 결과가 없습니다. 다른 조건으로 질문해보세요.", 0.0
        
        # 결과를 컨텍스트로 포맷
        context = json.dumps(results[:20], ensure_ascii=False, indent=2)
        
        messages = [
            {"role": "system", "content": ANSWER_GENERATION_PROMPT},
            {"role": "user", "content": f"""
질문: {question}

그래프 검색 결과:
{context}

위 데이터를 바탕으로 투자 관점에서 분석해주세요.
"""}
        ]
        
        response = self.llm.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=0.3,
            max_tokens=2000,
        )
        
        answer = response.choices[0].message.content
        
        # 신뢰도 계산 (결과 수 기반)
        confidence = min(len(results) / 10, 1.0)
        
        return answer, confidence
    
    def _extract_sources(self, results: List[Dict]) -> List[str]:
        """결과에서 소스(단지명, 지역명) 추출"""
        sources = set()
        for row in results:
            for key, value in row.items():
                if key in ('name', 'region', 'c.name', 'r.name') and value:
                    sources.add(str(value))
        return list(sources)[:10]
    
    # === 편의 메서드 ===
    
    def find_undervalued(self, min_jeonse_rate: float = 60.0) -> List[Dict]:
        """저평가 단지 조회"""
        cypher = f"""
        MATCH (c:ApartmentComplex)-[:LOCATED_IN]->(r:Region)
        WHERE c.is_undervalued = true AND c.jeonse_rate >= {min_jeonse_rate}
        RETURN c.name, c.jeonse_rate, c.gap_price, r.name as region
        ORDER BY c.jeonse_rate DESC
        LIMIT 20
        """
        return self._execute_cypher(cypher)
    
    def find_by_grade(self, category: str, grade: str) -> List[Dict]:
        """등급별 단지 조회"""
        cypher = f"""
        MATCH (c:ApartmentComplex)-[:LOCATED_IN]->(r:Region)
        MATCH (r)-[:HAS_GRADE]->(g:GradeMetric {{category: '{category}', grade: '{grade}'}})
        WHERE c.is_undervalued = true
        RETURN c.name, c.jeonse_rate, r.name as region, g.grade
        LIMIT 20
        """
        return self._execute_cypher(cypher)
    
    def get_region_supply(self, region_name: str) -> List[Dict]:
        """지역 공급물량 조회"""
        cypher = f"""
        MATCH (r:Region {{name: '{region_name}'}})-[:HAS_SUPPLY]->(s:SupplyEvent)
        RETURN s.year, s.volume
        ORDER BY s.year
        """
        return self._execute_cypher(cypher)
    
    def get_graph_statistics(self) -> Dict[str, int]:
        """그래프 통계"""
        from .graph_schema import GraphSchemaManager
        manager = GraphSchemaManager(self.graph)
        return manager.get_statistics()


if __name__ == "__main__":
    print("=== Hybrid RAG Query Engine ===")
    print("System prompt preview:")
    print(CYPHER_GENERATION_PROMPT[:500] + "...")
