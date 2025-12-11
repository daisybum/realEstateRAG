"""
Query Engine

쿼리 처리 오케스트레이션
"""

from typing import Dict, Any, Optional

from loguru import logger

from realestaterag.core.models import QueryResult
from realestaterag.query.nl_to_cypher import NLToCypherTranslator
from realestaterag.query.retriever import GraphRetriever
from realestaterag.query.synthesizer import ResponseSynthesizer
from realestaterag.query.cache import QueryCache


class QueryEngine:
    """쿼리 엔진
    
    자연어 질의 처리:
    1. NL → Cypher 변환
    2. 그래프 검색
    3. 응답 생성
    """
    
    def __init__(
        self,
        translator: NLToCypherTranslator = None,
        retriever: GraphRetriever = None,
        synthesizer: ResponseSynthesizer = None,
        cache: QueryCache = None,
    ):
        self.translator = translator or NLToCypherTranslator()
        self.retriever = retriever or GraphRetriever()
        self.synthesizer = synthesizer or ResponseSynthesizer()
        self.cache = cache or QueryCache()
    
    async def query(
        self,
        question: str,
        use_cache: bool = True,
    ) -> QueryResult:
        """자연어 쿼리 실행
        
        Args:
            question: 사용자 질문
            use_cache: 캐시 사용 여부
            
        Returns:
            QueryResult
        """
        logger.info(f"Processing query: {question}")
        
        # 캐시 확인
        if use_cache:
            cached = await self.cache.get(question)
            if cached:
                logger.info("Cache hit")
                return QueryResult(**cached)
        
        try:
            # 1. NL → Cypher
            logger.info("Translating to Cypher...")
            cypher_queries = await self.translator.translate(question)
            cypher = cypher_queries[0] if cypher_queries else ""
            
            # 2. 그래프 검색
            logger.info("Executing graph query...")
            results = await self.retriever.execute_queries(cypher_queries)
            
            # 3. 응답 생성
            logger.info("Synthesizing response...")
            response = await self.synthesizer.synthesize(question, results)
            
            # 결과 구성
            query_result = QueryResult(
                query=question,
                cypher=cypher,
                results=results,
                answer=response["answer"],
                confidence=response["confidence"],
                sources=response["sources"],
                query_type=self._classify_query(question),
            )
            
            # 캐싱
            if use_cache:
                await self.cache.set(question, query_result.model_dump())
            
            return query_result
            
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return QueryResult(
                query=question,
                cypher="",
                results=[],
                answer=f"쿼리 처리 중 오류가 발생했습니다: {e}",
                confidence=0.0,
                sources=[],
            )
    
    def _classify_query(self, question: str) -> str:
        """쿼리 타입 분류"""
        q = question.lower()
        
        # 순서 중요: 더 구체적인 패턴을 먼저 체크
        if any(k in q for k in ["추이", "변화"]):
            return "price_trend"
        if any(k in q for k in ["저평가", "갭"]):
            return "undervalued"
        if any(k in q for k in ["역", "접근", "분"]):
            return "facility_access"
        
        return "general"
    
    # === Convenience Methods ===
    
    async def find_by_facility(
        self,
        facility: str,
        max_time: int = 40,
        min_rate: float = 60.0,
    ):
        """시설 접근성 기반 검색"""
        question = f"{facility} {max_time}분 이내 전세가율 {min_rate}% 이상 단지"
        return await self.query(question, use_cache=False)
    
    async def get_price_trend(self, complex_name: str):
        """가격 추이 조회"""
        question = f"{complex_name} 가격 추이"
        return await self.query(question, use_cache=False)
    
    def get_statistics(self) -> Dict[str, int]:
        """그래프 통계"""
        return self.retriever.get_statistics()


# Factory
def create_query_engine() -> QueryEngine:
    """쿼리 엔진 생성"""
    return QueryEngine()
