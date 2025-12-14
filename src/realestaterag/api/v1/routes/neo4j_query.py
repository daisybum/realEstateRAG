"""
Neo4j Query Routes - Semantic Search Endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

from realestaterag.query.neo4j_query_engine import Neo4jQueryEngine, get_neo4j_engine

router = APIRouter()


class SemanticSearchRequest(BaseModel):
    """의미론적 검색 요청"""
    query: str = Field(..., min_length=1, description="자연어 검색 쿼리")
    node_type: str = Field(default="Complex", description="검색할 노드 타입")
    top_k: int = Field(default=10, ge=1, le=50, description="결과 개수")


class SemanticSearchResponse(BaseModel):
    """의미론적 검색 응답"""
    query: str
    results: List[Dict[str, Any]]
    count: int


class FacilitySearchRequest(BaseModel):
    """시설 기반 검색 요청"""
    facility: str = Field(..., description="시설명 (예: 강남역)")
    max_distance: int = Field(default=30, ge=1, le=120, description="최대 거리 (분)")
    jeonse_ratio: Optional[float] = Field(default=None, description="최소 전세가율 (%)")
    min_price: Optional[int] = Field(default=None, description="최소 가격 (만원)")
    max_price: Optional[int] = Field(default=None, description="최대 가격 (만원)")


class FacilitySearchResponse(BaseModel):
    """시설 기반 검색 응답"""
    facility: str
    results: List[Dict[str, Any]]
    count: int


class HybridSearchRequest(BaseModel):
    """하이브리드 검색 요청"""
    query: str = Field(..., min_length=1, description="자연어 쿼리")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="추가 필터")
    top_k: int = Field(default=10, ge=1, le=50, description="결과 개수")


@router.post("/semantic", response_model=SemanticSearchResponse)
async def semantic_search(
    request: SemanticSearchRequest,
    engine: Neo4jQueryEngine = Depends(get_neo4j_engine)
):
    """
    의미론적 유사도 검색 (Vector Search)
    
    벡터 임베딩을 사용하여 자연어 쿼리와 유사한 부동산 정보를 검색합니다.
    
    - **query**: "전세가율 높은 아파트", "투자 가치 좋은 단지" 등
    - **node_type**: 검색할 노드 타입 (Complex, Facility 등)
    - **top_k**: 반환할 결과 개수
    """
    try:
        results = await engine.semantic_search(
            query=request.query,
            node_type=request.node_type,
            top_k=request.top_k
        )
        
        return SemanticSearchResponse(
            query=request.query,
            results=results,
            count=len(results)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Semantic search failed: {str(e)}")


@router.post("/facility", response_model=FacilitySearchResponse)
async def facility_based_search(
    request: FacilitySearchRequest,
    engine: Neo4jQueryEngine = Depends(get_neo4j_engine)
):
    """
    시설 기반 그래프 검색
    
    특정 시설(역, 학교 등) 근처의 부동산 정보를 그래프 탐색으로 검색합니다.
    
    - **facility**: 시설명 (예: "강남역", "판교역")
    - **max_distance**: 최대 이동 시간 (분)
    - **filters**: 가격, 전세가율 등 추가 필터
    """
    try:
        filters = {}
        if request.jeonse_ratio:
            filters["jeonse_ratio"] = request.jeonse_ratio
        if request.min_price:
            filters["min_price"] = request.min_price
        if request.max_price:
            filters["max_price"] = request.max_price
        
        results = await engine.facility_based_search(
            facility_name=request.facility,
            max_distance=request.max_distance,
            filters=filters
        )
        
        return FacilitySearchResponse(
            facility=request.facility,
            results=results,
            count=len(results)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Facility search failed: {str(e)}")


@router.post("/hybrid", response_model=SemanticSearchResponse)
async def hybrid_search(
    request: HybridSearchRequest,
    engine: Neo4jQueryEngine = Depends(get_neo4j_engine)
):
    """
    하이브리드 검색 (Vector + Graph)
    
    의미론적 검색과 그래프 탐색을 결합하여 더 정확한 결과를 제공합니다.
    
    - **query**: 자연어 쿼리
    - **filters**: 추가 필터 조건
    - **top_k**: 결과 개수
    """
    try:
        results = await engine.hybrid_search(
            query=request.query,
            filters=request.filters or {},
            top_k=request.top_k
        )
        
        return SemanticSearchResponse(
            query=request.query,
            results=results,
            count=len(results)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Hybrid search failed: {str(e)}")


@router.get("/statistics")
async def get_graph_statistics(
    engine: Neo4jQueryEngine = Depends(get_neo4j_engine)
):
    """
    Neo4j 그래프 통계
    
    노드 개수, 관계 개수 등 그래프 통계 정보를 반환합니다.
    """
    try:
        stats = await engine.get_statistics()
        return {"statistics": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Statistics query failed: {str(e)}")


@router.get("/health")
async def neo4j_health_check():
    """Neo4j 연결 상태 확인"""
    try:
        engine = get_neo4j_engine()
        # Simple health check
        stats = await engine.get_statistics()
        return {
            "status": "healthy",
            "database": "neo4j",
            "node_count": sum(v for k, v in stats.items() if k.endswith("_count") and "relationship" not in k)
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }
