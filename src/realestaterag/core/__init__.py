"""
Core Module - Domain models, enums, and exceptions

핵심 도메인 정의:
- Pydantic 모델
- 열거형
- 커스텀 예외
"""

from realestaterag.core.enums import (
    GradeLevel,
    InfraCategory,
    EntityType,
    InvestmentVerdict,
    AnalysisStage,
    StorageBackend,
    Environment,
)

from realestaterag.core.models import (
    Location,
    GradeMetric,
    District,
    Infra,
    MarketSnapshot,
    PropertyComplex,
    Report,
    InvestmentAnalysis,
    AnalysisResult,
    QueryRequest,
    QueryResult,
)

from realestaterag.core.exceptions import (
    RealEstateRAGError,
    IngestionError,
    LoaderError,
    ParsingError,
    ValidationError,
    AnalysisError,
    GraphError,
    SchemaError,
    CypherError,
    EntityNotFoundError,
    DuplicateEntityError,
    QueryError,
    TranslationError,
    RetrievalError,
    SynthesisError,
    InfrastructureError,
    DatabaseConnectionError,
    LLMError,
    StorageError,
    ConfigurationError,
)

__all__ = [
    # Enums
    "GradeLevel",
    "InfraCategory",
    "EntityType",
    "InvestmentVerdict",
    "AnalysisStage",
    "StorageBackend",
    "Environment",
    # Models
    "Location",
    "GradeMetric",
    "District",
    "Infra",
    "MarketSnapshot",
    "PropertyComplex",
    "Report",
    "InvestmentAnalysis",
    "AnalysisResult",
    "QueryRequest",
    "QueryResult",
    # Exceptions
    "RealEstateRAGError",
    "IngestionError",
    "LoaderError",
    "ParsingError",
    "ValidationError",
    "AnalysisError",
    "GraphError",
    "SchemaError",
    "CypherError",
    "EntityNotFoundError",
    "DuplicateEntityError",
    "QueryError",
    "TranslationError",
    "RetrievalError",
    "SynthesisError",
    "InfrastructureError",
    "DatabaseConnectionError",
    "LLMError",
    "StorageError",
    "ConfigurationError",
]
