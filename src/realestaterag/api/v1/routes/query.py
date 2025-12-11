"""
Query Routes
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

from realestaterag.query import QueryEngine

router = APIRouter()


class QueryRequest(BaseModel):
    """쿼리 요청"""
    question: str = Field(..., min_length=1, description="자연어 질문")
    use_cache: bool = Field(default=True, description="캐시 사용 여부")


class QueryResponse(BaseModel):
    """쿼리 응답"""
    query: str
    answer: str
    cypher: str
    results: List[Dict[str, Any]]
    confidence: float
    sources: List[str]
    query_type: str


class FacilitySearchRequest(BaseModel):
    """시설 검색 요청"""
    facility: str = Field(..., description="시설명 (예: 강남역)")
    max_time: int = Field(default=40, description="최대 이동시간 (분)")
    min_rate: float = Field(default=60.0, description="최소 전세가율 (%)")


class PriceTrendRequest(BaseModel):
    """가격 추이 요청"""
    complex_name: str = Field(..., description="단지명")


# 싱글톤 엔진
_engine: Optional[QueryEngine] = None

def get_engine() -> QueryEngine:
    global _engine
    if _engine is None:
        _engine = QueryEngine()
    return _engine


@router.post("", response_model=QueryResponse)
@router.post("/", response_model=QueryResponse)
async def execute_query(request: QueryRequest):
    """자연어 쿼리 실행"""
    try:
        engine = get_engine()
        result = await engine.query(
            question=request.question,
            use_cache=request.use_cache,
        )
        
        return QueryResponse(
            query=result.query,
            answer=result.answer,
            cypher=result.cypher,
            results=result.results,
            confidence=result.confidence,
            sources=result.sources,
            query_type=result.query_type,
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/facility", response_model=QueryResponse)
async def search_by_facility(request: FacilitySearchRequest):
    """시설 기반 검색"""
    try:
        engine = get_engine()
        result = await engine.find_by_facility(
            facility=request.facility,
            max_time=request.max_time,
            min_rate=request.min_rate,
        )
        
        return QueryResponse(
            query=result.query,
            answer=result.answer,
            cypher=result.cypher,
            results=result.results,
            confidence=result.confidence,
            sources=result.sources,
            query_type=result.query_type,
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/price-trend", response_model=QueryResponse)
async def get_price_trend(request: PriceTrendRequest):
    """가격 추이 조회"""
    try:
        engine = get_engine()
        result = await engine.get_price_trend(request.complex_name)
        
        return QueryResponse(
            query=result.query,
            answer=result.answer,
            cypher=result.cypher,
            results=result.results,
            confidence=result.confidence,
            sources=result.sources,
            query_type=result.query_type,
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics")
async def get_statistics():
    """그래프 통계"""
    try:
        engine = get_engine()
        stats = engine.get_statistics()
        return {"statistics": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
