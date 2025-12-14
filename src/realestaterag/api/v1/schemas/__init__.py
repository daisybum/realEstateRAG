"""
API Schemas

요청/응답 모델 정의
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


# ============================================================
# Query Schemas
# ============================================================

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
    query_type: str = "general"


class FacilitySearchRequest(BaseModel):
    """시설 검색 요청"""
    facility: str = Field(..., description="시설명 (예: 강남역)")
    max_time: int = Field(default=40, description="최대 이동시간 (분)")
    min_rate: float = Field(default=60.0, description="최소 전세가율 (%)")


class PriceTrendRequest(BaseModel):
    """가격 추이 요청"""
    complex_name: str = Field(..., description="단지명")


# ============================================================
# Ingestion Schemas
# ============================================================

class IngestionRequest(BaseModel):
    """인제스천 요청"""
    report_id: str = Field(..., description="리포트 ID")


class BatchIngestionRequest(BaseModel):
    """배치 인제스천 요청"""
    report_ids: List[str] = Field(..., description="리포트 ID 목록")
    max_concurrent: int = Field(default=5, description="최대 동시 처리 수")


class IngestionResponse(BaseModel):
    """인제스천 응답"""
    report_id: str
    success: bool
    message: str
    facts_count: int = 0
    entities_count: int = 0
    relationships_count: int = 0
    processing_time: float = 0.0


class BatchIngestionResponse(BaseModel):
    """배치 인제스천 응답"""
    total: int
    successful: int
    failed: int
    results: List[IngestionResponse]


# ============================================================
# Report Schemas
# ============================================================

class ReportSummary(BaseModel):
    """리포트 요약"""
    id: str
    title: str
    date: datetime
    district: str


class ReportDetail(BaseModel):
    """리포트 상세"""
    id: str
    title: str
    date: datetime
    district: str
    facts: List[str] = []
    entities: List[Dict[str, Any]] = []
    confidence_score: float = 0.0


# ============================================================
# Statistics Schemas
# ============================================================

class GraphStatistics(BaseModel):
    """그래프 통계"""
    node_counts: Dict[str, int] = {}
    relationship_counts: Dict[str, int] = {}
    total_nodes: int = 0
    total_relationships: int = 0
