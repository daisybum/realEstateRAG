"""
Core Enumerations for RealEstateRAG

도메인 전반에서 사용되는 열거형 정의
"""

from enum import Enum


class GradeLevel(str, Enum):
    """입지 등급 (월급쟁이부자들 기준)"""
    S = "S"  # 최상급
    A = "A"  # 우수
    B = "B"  # 양호
    C = "C"  # 보통
    D = "D"  # 미흡


class InfraCategory(str, Enum):
    """인프라 시설 유형"""
    SUBWAY = "Subway"           # 지하철역
    BUS_TERMINAL = "BusTerminal" # 버스터미널
    JOB_CENTER = "JobCenter"    # 대기업/일자리 중심지
    DEPT_STORE = "DeptStore"    # 백화점
    SHOPPING_MALL = "ShoppingMall" # 쇼핑몰
    SCHOOL = "School"           # 학교 (학군)
    HOSPITAL = "Hospital"       # 병원
    PARK = "Park"               # 공원


class EntityType(str, Enum):
    """그래프 엔티티 타입"""
    REGION = "Region"
    DISTRICT = "District"
    NEIGHBORHOOD = "Neighborhood"
    COMPLEX = "Complex"
    INFRA = "Infra"
    MARKET_SNAPSHOT = "MarketSnapshot"
    REPORT = "Report"
    INVESTMENT_ANALYSIS = "InvestmentAnalysis"


class InvestmentVerdict(str, Enum):
    """투자 판단"""
    UNDERVALUED = "undervalued"     # 저평가
    FAIR = "fair"                   # 적정가
    OVERVALUED = "overvalued"       # 고평가
    WATCHLIST = "watchlist"         # 관심 목록


class AnalysisStage(str, Enum):
    """분석 파이프라인 단계"""
    FACT_EXTRACTION = "fact_extraction"
    VISUAL_VERIFICATION = "visual_verification"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    INSIGHT_GENERATION = "insight_generation"


class StorageBackend(str, Enum):
    """스토리지 백엔드 타입"""
    LOCAL = "local"
    S3 = "s3"
    GCS = "gcs"


class Environment(str, Enum):
    """실행 환경"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
