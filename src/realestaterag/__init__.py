"""
RealEstateRAG - GraphRAG-powered Real Estate Intelligence Platform

Production-ready PropTech solution with:
- Multimodal AI analysis (Qwen3-VL)
- Knowledge graph (FalkorDB)
- Entity-centric ontology (v3.0)
"""

__version__ = "1.0.0"

from realestaterag.core.models import (
    Report,
    District,
    PropertyComplex,
    Infra,
    MarketSnapshot,
    AnalysisResult,
)

from realestaterag.core.enums import (
    GradeLevel,
    InfraCategory,
    EntityType,
)

__all__ = [
    "__version__",
    # Models
    "Report",
    "District",
    "PropertyComplex",
    "Infra",
    "MarketSnapshot",
    "AnalysisResult",
    # Enums
    "GradeLevel",
    "InfraCategory",
    "EntityType",
]
