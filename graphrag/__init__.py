"""
GraphRAG Module

Knowledge Graph Construction and Query for Real Estate Analysis

Versions:
- v2.0: Document-centric ontology
- v3.0: Entity-centric ontology with time-series separation
"""

# v2.0 Schema
from .graph_schema import (
    WolbuOntologyV2,
    GraphSchemaManager,
    Region,
    ApartmentComplex,
    GradeMetric,
    InvestmentAnalysis,
    Indicator,
    SupplyEvent,
    Report,
)

# v3.0 Schema
from .graph_schema_v3 import (
    WolbuOntologyV3,
    GraphSchemaManagerV3,
    Neighborhood,
    Infra,
    MarketSnapshot,
)

from .graph_ingester import GraphIngesterV2
from .graph_ingester_v3 import GraphIngesterV3

from .query_engine import HybridRAGEngine as HybridRAGEngineV2, QueryResult
from .query_engine_v3 import HybridRAGEngineV3, QueryResultV3

# Default to v3
GraphIngester = GraphIngesterV3
HybridRAGEngine = HybridRAGEngineV3

__version__ = "3.0.0"

__all__ = [
    # v2.0
    "WolbuOntologyV2",
    "GraphSchemaManager",
    "GraphIngesterV2",
    "HybridRAGEngineV2",
    "QueryResult",
    # v3.0
    "WolbuOntologyV3",
    "GraphSchemaManagerV3",
    "GraphIngesterV3",
    "HybridRAGEngineV3",
    "QueryResultV3",
    "Neighborhood",
    "Infra",
    "MarketSnapshot",
    # Common (default to v3)
    "GraphIngester",
    "HybridRAGEngine",
    "Region",
    "ApartmentComplex",
    "Report",
    # v2.0 specific exports (for backward compatibility if needed, though some might be deprecated)
    "InvestmentAnalysis",
    "Indicator",
    "GradeMetric",
    "SupplyEvent",
]
