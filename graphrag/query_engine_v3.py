"""
Query Engine v3.0

v3.0 온톨로지 지원: Infra, MarketSnapshot, Neighborhood
새 쿼리 타입: 시설 기반 검색, 가격 추이 분석, 다중 홉 그래프 탐색
"""

import json
import logging
import re
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

from .graph_schema_v3 import WolbuOntologyV3, CYPHER_TEMPLATES_V3

logger = logging.getLogger(__name__)


@dataclass
class QueryResultV3:
    """쿼리 결과 컨테이너 (v3.0)"""
    query: str
    cypher: str
    graph_results: List[Dict]
    answer: str
    confidence: float
    sources: List[str]
    query_type: str  # NEW: facility_access, price_trend, grade_analysis, etc.


# v3.0 Cypher 생성 프롬프트
CYPHER_GENERATION_PROMPT_V3 = """You are a Cypher query expert for a real estate investment knowledge graph (v3.0).

## Graph Schema (Wolbu Ontology v3.0)

### Nodes:
- **Region/District**: {name}
- **Neighborhood**: {name, district, region}
- **ApartmentComplex**: {name, households, built_year, address}
- **Infra**: {name, category (Subway|JobCenter|DeptStore|School), tier (S|A|B|C)}
- **MarketSnapshot**: {date (YYYY-MM), sales_price, jeonse_price, jeonse_rate, gap_price, population, supply_volume}
- **Report**: {report_id, title, analysis_date}
- **InvestmentAnalysis**: {verdict, reasoning, confidence}

### Relationships:
- (:Neighborhood)-[:LOCATED_IN]->(:District)
- (:Complex)-[:LOCATED_IN]->(:Neighborhood)
- (:District)-[:ACCESS_TO {time_min, transport_mode}]->(:Infra)
- (:District)-[:CONTAINS_FACILITY]->(:Infra)
- (:Complex)-[:HAS_SNAPSHOT]->(:MarketSnapshot)
- (:District)-[:HAS_SNAPSHOT]->(:MarketSnapshot)
- (:Complex)-[:HAS_ANALYSIS]->(:InvestmentAnalysis)

### Key Changes from v2.0:
1. **Named Facilities**: Use specific facility names (e.g., "강남역", "Starfield Hanam")
2. **Time-Series Data**: Prices are in MarketSnapshot nodes, not in Complex
3. **Spatial Hierarchy**: Region → District → Neighborhood → Complex

## Task
Translate the user's natural language question into a valid Cypher query.

## Rules:
1. Return ONLY the Cypher query, no explanation
2. For time-series queries, join with MarketSnapshot using HAS_SNAPSHOT
3. For facility queries, use Infra nodes and ACCESS_TO/CONTAINS_FACILITY relationships
4. Always use latest MarketSnapshot data: WHERE m.date = (SELECT MAX(m2.date) FROM ...)

## Examples:

User: 강남역 30분 이내 접근 가능한 단지에서 전세가율 60% 이상인 곳
Cypher:
```cypher
MATCH (d:District)-[r:ACCESS_TO]->(i:Infra {name: '강남역'})
WHERE r.time_min <= 30
MATCH (c:ApartmentComplex)-[:LOCATED_IN*]->(d)
MATCH (c)-[:HAS_SNAPSHOT]->(m:MarketSnapshot)
WHERE m.date = (
  SELECT MAX(m2.date) 
  FROM (c)-[:HAS_SNAPSHOT]->(m2:MarketSnapshot)
)
AND m.jeonse_rate >= 60
RETURN c.name, d.name as district, m.jeonse_rate, r.time_min
ORDER BY m.jeonse_rate DESC
LIMIT 20
```

User: 은마아파트 가격 추이
Cypher:
```cypher
MATCH (c:ApartmentComplex {name: '은마아파트'})-[:HAS_SNAPSHOT]->(m:MarketSnapshot)
RETURN m.date, m.sales_price, m.jeonse_price, m.jeonse_rate
ORDER BY m.date ASC
```

User: 수지구에 있는 백화점 목록
Cypher:
```cypher
MATCH (d:District {name: '수지구'})-[:CONTAINS_FACILITY]->(i:Infra)
WHERE i.category = 'DeptStore'
RETURN i.name, i.tier, i.address
ORDER BY i.tier ASC
```
"""

# 답변 생성 프롬프트 (v3.0 - 동일)
ANSWER_GENERATION_PROMPT_V3 = """You are a professional real estate investment analyst.
Based on the graph query results, provide a comprehensive investment analysis in Korean.

## Analysis Framework (월급쟁이부자들 기준):
- 전세가율 60% 이상: 갭투자 유리
- 입지 독점성: 특정 시설(강남역, 백화점) 접근성
- 공급 리스크: 향후 3년 공급물량 대비 적정수요

## Guidelines:
1. 데이터에 있는 정보만 언급 (할루시네이션 금지)
2. 구체적인 수치 인용
3. 투자 관점에서 분석
4. 리스크도 함께 언급
"""


class HybridRAGEngineV3:
    """하이브리드 RAG 쿼리 엔진 v3.0
    
    v3.0 온톨로지 지원:
    - Infra 기반 시설 검색
    - MarketSnapshot 시계열 분석
    - 다중 홉 그래프 탐색
    """
    
    def __init__(self, graph, llm_client, model_name: str = None, schema_version: str = "v3"):
        """
        Args:
            graph: FalkorDB Graph 객체
            llm_client: OpenAI 호환 클라이언트
            model_name: 모델명
            schema_version: "v2" or "v3" (default: v3)
        """
        self.graph = graph
        self.llm = llm_client
        self.model_name = model_name or self._get_default_model()
        self.schema_version = schema_version
        self.ontology = WolbuOntologyV3()
    
    def _get_default_model(self) -> str:
        import os
        return os.environ.get("LLM_MODEL", "Qwen/Qwen3-VL-30B-A3B-Instruct")
    
    def query(self, natural_language: str) -> QueryResultV3:
        """자연어 질의 처리"""
        logger.info(f"Processing query (v3): {natural_language}")
        
        # 1. 쿼리 타입 결정
        query_type = self._classify_query(natural_language)
        logger.info(f"Query type: {query_type}")
        
        # 2. Cypher 생성
        cypher = self._generate_cypher(natural_language, query_type)
        logger.info(f"Generated Cypher: {cypher}")
        
        # 3. 실행
        graph_results = self._execute_cypher(cypher)
        logger.info(f"Graph returned {len(graph_results)} results")
        
        # 4. 답변 생성
        answer, confidence = self._generate_answer(natural_language, graph_results, query_type)
        
        # 5. 소스 추출
        sources = self._extract_sources(graph_results)
        
        return QueryResultV3(
            query=natural_language,
            cypher=cypher,
            graph_results=graph_results,
            answer=answer,
            confidence=confidence,
            sources=sources,
            query_type=query_type,
        )
    
    def _classify_query(self, question: str) -> str:
        """쿼리 타입 분류"""
        q = question.lower()
        
        # 시설 기반 검색
        facilities = ["역", "백화점", "학교", "병원", "판교", "강남역", "서면역"]
        if any(f in q for f in facilities) and any(k in q for k in ["접근", "근처", "거리"]):
            return "facility_access"
        
        # 가격 추이
        if "추이" in q or "변화" in q or "트렌드" in q:
            return "price_trend"
        
        # 지역 내 시설 목록
        if any(k in q for k in ["목록", "있는", "리스트"]) and any(f in q for f in facilities):
            return "facility_list"
        
        # 기본: 등급 기반 분석
        return "grade_analysis"
    
    def _generate_cypher(self, question: str, query_type: str) -> str:
        """자연어 → Cypher 변환"""
        # 사전 정의 쿼리 매칭
        preset = self._match_preset_query_v3(question, query_type)
        if preset:
            return preset
        
        # LLM으로 생성
        messages = [
            {"role": "system", "content": CYPHER_GENERATION_PROMPT_V3},
            {"role": "user", "content": f"Question: {question}\nCypher:"}
        ]
        
        response = self.llm.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=0.1,
            max_tokens=500,
        )
        
        cypher_raw = response.choices[0].message.content
        return self._extract_cypher(cypher_raw)
    
    def _match_preset_query_v3(self, question: str, query_type: str) -> Optional[str]:
        """v3.0 사전 정의 쿼리 매칭"""
        if query_type == "facility_access":
            # 시설명 추출 (간단한 패턴)
            facility_keywords = {
                "강남역": "강남역",
                "판교": "판교역",
                "서면": "서면역",
            }
            facility_name = None
            for keyword, name in facility_keywords.items():
                if keyword in question:
                    facility_name = name
                    break
            
            # 시간 추출
            time_match = re.search(r'(\d+)\s*분', question)
            max_time = int(time_match.group(1)) if time_match else 40
            
            # 전세가율 추출
            rate_match = re.search(r'(\d+)\s*%', question)
            min_rate = float(rate_match.group(1)) if rate_match else 60.0
            
            if facility_name:
                return CYPHER_TEMPLATES_V3["find_by_facility_access"].format(
                    facility_name=facility_name,
                    max_time_min=max_time,
                    min_jeonse_rate=min_rate,
                )
        
        elif query_type == "price_trend":
            # 단지명 추출 (간단한 패턴)
            complex_match = re.search(r'([가-힣]+아파트|[가-힣]+타운)', question)
            if complex_match:
                complex_name = complex_match.group(1)
                return CYPHER_TEMPLATES_V3["get_price_trend"].format(
                    complex_name=complex_name
                )
        
        elif query_type == "facility_list":
            # 지역명 추출
            district_match = re.search(r'([가-힣]+구|[가-힣]+시)', question)
            if district_match:
                district_name = district_match.group(1)
                
                # 시설 카테고리
                category_map = {
                    "백화점": "DeptStore",
                    "지하철": "Subway",
                    "학교": "School",
                    "병원": "Hospital",
                }
                category = "DeptStore"  # default
                for keyword, cat in category_map.items():
                    if keyword in question:
                        category = cat
                        break
                
                return CYPHER_TEMPLATES_V3["find_facilities_in_district"].format(
                    district_name=district_name,
                    category=category,
                )
        
        return None
    
    def _extract_cypher(self, text: str) -> str:
        """텍스트에서 Cypher 추출"""
        match = re.search(r'```(?:cypher)?\\s*(.*?)```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        match = re.search(r'(MATCH\\s+.*)', text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        return text.strip()
    
    def _execute_cypher(self, cypher: str) -> List[Dict]:
        """Cypher 실행"""
        try:
            result = self.graph.query(cypher)
            
            if result.result_set:
                columns = result.header if hasattr(result, 'header') else [f"col_{i}" for i in range(len(result.result_set[0]))]
                
                return [
                    {columns[i]: row[i] for i in range(len(row))}
                    for row in result.result_set
                ]
            return []
        except Exception as e:
            logger.error(f"Cypher execution failed: {e}")
            return []
    
    def _generate_answer(self, question: str, results: List[Dict], query_type: str) -> Tuple[str, float]:
        """답변 생성"""
        if not results:
            return "검색 결과가 없습니다. 다른 조건으로 질문해보세요.", 0.0
        
        context = json.dumps(results[:20], ensure_ascii=False, indent=2)
        
        messages = [
            {"role": "system", "content": ANSWER_GENERATION_PROMPT_V3},
            {"role": "user", "content": f"""
질문: {question}
쿼리 타입: {query_type}

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
        confidence = min(len(results) / 10, 1.0)
        
        return answer, confidence
    
    def _extract_sources(self, results: List[Dict]) -> List[str]:
        """소스 추출"""
        sources = set()
        for row in results:
            for key, value in row.items():
                if 'name' in key.lower() and value:
                    sources.add(str(value))
        return list(sources)[:10]
    
    # === v3.0 Convenience Methods ===
    
    def find_by_facility_access(self, facility_name: str, max_time_min: int = 40, min_jeonse_rate: float = 60.0) -> List[Dict]:
        """시설 접근성 기반 단지 검색"""
        cypher = CYPHER_TEMPLATES_V3["find_by_facility_access"].format(
            facility_name=facility_name,
            max_time_min=max_time_min,
            min_jeonse_rate=min_jeonse_rate,
        )
        return self._execute_cypher(cypher)
    
    def get_price_trend(self, complex_name: str) -> List[Dict]:
        """단지 가격 추이 조회"""
        cypher = CYPHER_TEMPLATES_V3["get_price_trend"].format(
            complex_name=complex_name
        )
        return self._execute_cypher(cypher)
    
    def find_facilities_in_district(self, district_name: str, category: str = "DeptStore") -> List[Dict]:
        """지역 내 시설 목록 조회"""
        cypher = CYPHER_TEMPLATES_V3["find_facilities_in_district"].format(
            district_name=district_name,
            category=category,
        )
        return self._execute_cypher(cypher)
    
    def get_graph_statistics(self) -> Dict[str, int]:
        """그래프 통계"""
        from .graph_schema_v3 import GraphSchemaManagerV3
        manager = GraphSchemaManagerV3(self.graph)
        return manager.get_statistics()


# Backward compatibility
HybridRAGEngine = HybridRAGEngineV3


if __name__ == "__main__":
    print("=== Hybrid RAG Query Engine v3.0 ===")
    print("New features:")
    print("- Facility-based search (Infra nodes)")
    print("- Price trend analysis (MarketSnapshot)")
    print("- Multi-hop graph traversal")
