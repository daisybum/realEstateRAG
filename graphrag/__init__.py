"""
GraphRAG Module

FalkorDB 기반 부동산 투자 분석 GraphRAG 시스템
"""

# v2.0 Schema
from .graph_schema import (
    WolbuOntologyV2,
    GraphSchemaManager,
    Report,
    InvestmentAnalysis,
    Indicator,
    Region,
    ApartmentComplex,
    GradeMetric,
    SupplyEvent,
    InvestmentVerdict,
    IndicatorType,
)
from .graph_ingester import GraphIngesterV2, GraphIngester
from .query_engine import HybridRAGEngine, QueryResult

__all__ = [
    # v2.0 Ontology
    "WolbuOntologyV2",
    "GraphSchemaManager",
    "Report",
    "InvestmentAnalysis",
    "Indicator",
    "Region",
    "ApartmentComplex",
    "GradeMetric",
    "SupplyEvent",
    "InvestmentVerdict",
    "IndicatorType",
    # Ingester
    "GraphIngesterV2",
    "GraphIngester",  # backward compatibility
    # Query Engine  
    "HybridRAGEngine",
    "QueryResult",
]
