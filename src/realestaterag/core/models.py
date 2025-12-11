"""
Core Domain Models for RealEstateRAG

Pydantic 기반 도메인 모델 정의
- 유효성 검증
- 직렬화/역직렬화
- 타입 안전성
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator

from realestaterag.core.enums import (
    GradeLevel,
    InfraCategory,
    EntityType,
    InvestmentVerdict,
)


# ============================================================
# Base Models
# ============================================================

class Location(BaseModel):
    """지리적 위치 모델"""
    district: str = Field(..., description="구/군 (예: 수지구)")
    city: str = Field(default="", description="시 (예: 용인시)")
    province: str = Field(default="", description="도/광역시 (예: 경기도)")
    neighborhood: Optional[str] = Field(default=None, description="읍/면/동")
    coordinates: Optional[tuple[float, float]] = Field(default=None, description="위도, 경도")
    
    @property
    def full_address(self) -> str:
        """전체 주소 문자열"""
        parts = [p for p in [self.province, self.city, self.district, self.neighborhood] if p]
        return " ".join(parts)


class GradeMetric(BaseModel):
    """입지 등급 지표"""
    category: str = Field(..., description="등급 유형 (Jobs, Transport, School, Environment)")
    grade: GradeLevel = Field(..., description="등급 (S/A/B/C/D)")
    raw_value: Optional[str] = Field(default=None, description="원시 값")
    evidence: Optional[str] = Field(default=None, description="근거")


# ============================================================
# Entity Models
# ============================================================

class District(BaseModel):
    """지역/구 엔티티"""
    id: str = Field(..., description="고유 ID")
    name: str = Field(..., description="지역명")
    location: Optional[Location] = None
    grades: List[GradeMetric] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        extra = "allow"


class Infra(BaseModel):
    """인프라 시설 엔티티"""
    id: str = Field(..., description="고유 ID (INFRA_ prefix)")
    name: str = Field(..., description="시설명 (예: 강남역, Starfield Hanam)")
    category: InfraCategory = Field(..., description="시설 유형")
    tier: GradeLevel = Field(default=GradeLevel.B, description="시설 등급")
    address: Optional[str] = Field(default=None, description="주소")
    coordinates: Optional[tuple[float, float]] = None
    
    @field_validator("id")
    @classmethod
    def validate_id_prefix(cls, v: str) -> str:
        if not v.startswith("INFRA_"):
            return f"INFRA_{v}"
        return v


class MarketSnapshot(BaseModel):
    """시장 데이터 스냅샷 (시계열)"""
    id: str = Field(..., description="고유 ID (MARKET_ prefix)")
    date: str = Field(..., description="날짜 (YYYY-MM)")
    
    # 가격 정보
    sales_price: Optional[int] = Field(default=None, description="매매가 (만원)")
    jeonse_price: Optional[int] = Field(default=None, description="전세가 (만원)")
    jeonse_rate: Optional[float] = Field(default=None, description="전세가율 (%)")
    gap_price: Optional[int] = Field(default=None, description="갭 (만원)")
    
    # 인구/공급 정보
    population: Optional[int] = Field(default=None, description="인구수")
    supply_volume: Optional[int] = Field(default=None, description="공급물량")
    
    @field_validator("date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        import re
        if not re.match(r"^\d{4}-\d{2}$", v):
            raise ValueError("Date must be in YYYY-MM format")
        return v


class PropertyComplex(BaseModel):
    """아파트 단지 엔티티"""
    id: str = Field(..., description="고유 ID")
    name: str = Field(..., description="단지명")
    location: Optional[Location] = None
    
    # 정적 정보
    total_units: Optional[int] = Field(default=None, description="총 세대수")
    year_built: Optional[int] = Field(default=None, description="준공연도")
    address: Optional[str] = Field(default=None, description="상세 주소")
    
    # 관련 스냅샷
    snapshots: List[MarketSnapshot] = Field(default_factory=list)
    
    @property
    def latest_snapshot(self) -> Optional[MarketSnapshot]:
        """최신 시장 데이터"""
        if not self.snapshots:
            return None
        return sorted(self.snapshots, key=lambda x: x.date, reverse=True)[0]


class Report(BaseModel):
    """임장 보고서"""
    id: str = Field(..., description="보고서 ID")
    title: str = Field(default="", description="제목")
    date: datetime = Field(default_factory=datetime.now, description="작성일")
    location: Optional[Location] = None
    
    # 파일 경로
    content_path: Optional[str] = Field(default=None, description="본문 경로")
    image_paths: List[str] = Field(default_factory=list, description="이미지 경로 목록")
    
    # 메타데이터
    source: Optional[str] = Field(default=None, description="출처")
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class InvestmentAnalysis(BaseModel):
    """투자 분석 결과"""
    complex_id: str = Field(..., description="대상 단지 ID")
    verdict: InvestmentVerdict = Field(..., description="투자 판단")
    reasoning: str = Field(default="", description="추론 과정")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    
    # 지표 기반 분석
    grade_summary: Dict[str, GradeLevel] = Field(default_factory=dict)
    key_factors: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    
    # 시계열 분석
    price_trend: Optional[str] = Field(default=None)
    supply_outlook: Optional[str] = Field(default=None)
    
    analysis_date: datetime = Field(default_factory=datetime.now)


class AnalysisResult(BaseModel):
    """분석 파이프라인 출력"""
    report_id: str = Field(..., description="원본 보고서 ID")
    
    # 추출 결과
    facts: List[str] = Field(default_factory=list)
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    relationships: List[Dict[str, Any]] = Field(default_factory=list)
    
    # 분석 결과
    sentiments: Dict[str, float] = Field(default_factory=dict)
    insights: List[str] = Field(default_factory=list)
    
    # 메타데이터
    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0)
    processing_time: float = Field(default=0.0, description="처리 시간 (초)")
    stages_completed: List[str] = Field(default_factory=list)


# ============================================================
# Query Models
# ============================================================

class QueryRequest(BaseModel):
    """쿼리 요청"""
    question: str = Field(..., min_length=1, description="자연어 질문")
    use_cache: bool = Field(default=True)
    max_results: int = Field(default=20, ge=1, le=100)


class QueryResult(BaseModel):
    """쿼리 결과"""
    query: str = Field(..., description="원본 질문")
    cypher: str = Field(default="", description="생성된 Cypher")
    results: List[Dict[str, Any]] = Field(default_factory=list)
    answer: str = Field(default="", description="자연어 답변")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    sources: List[str] = Field(default_factory=list)
    query_type: str = Field(default="general")
