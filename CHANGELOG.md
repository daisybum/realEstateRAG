# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2024-12-11

### Added

#### Week 1: Core Foundation
- Python package structure (`src/realestaterag/`)
- Pydantic v2 domain models (Location, District, Infra, MarketSnapshot, etc.)
- Core enumerations (GradeLevel, InfraCategory, EntityType)
- Custom exception hierarchy
- Pydantic Settings for environment configuration
- pyproject.toml with full dependency specification

#### Week 2: Ingestion Pipeline
- `MultimodalLoader` for async text/image loading
- `QwenAnalyzer` with 4-stage analysis pipeline
- `IngestionPipeline` orchestration with batch processing
- Entity/relationship extraction from LLM output

#### Week 3: Query Engine
- `NLToCypherTranslator` with preset patterns and LLM fallback
- `GraphRetriever` with lazy FalkorDB connection
- `ResponseSynthesizer` for investment-focused answers
- `QueryCache` with in-memory backend
- `QueryEngine` orchestration

#### Week 4: API Layer
- FastAPI application with CORS and metrics
- Health endpoints (`/health`, `/ready`, `/live`)
- Query endpoints (`/api/v1/query`, `/facility`, `/price-trend`)
- Ingestion endpoints (`/single`, `/batch`)
- Background task processing

#### Week 5-6: Deployment
- Multi-stage Dockerfile with uv
- Docker Compose for full stack
- Kubernetes manifests with Kustomize
- GitHub Actions CI pipeline
- Makefile for common commands

#### Week 7: Testing
- pytest configuration with asyncio support
- 49 unit tests for models, query, ingestion
- Integration tests for API endpoints
- Coverage reporting

#### Week 8: Documentation
- Updated README with new architecture
- CHANGELOG tracking
- Migration guide (v2→v3)
- Production roadmap

### Changed
- Default `GraphIngester` now points to v3
- Default `HybridRAGEngine` now points to v3
- Package version updated to 1.0.0

### Deprecated
- Legacy `analysis/` module (migration to `src/realestaterag/ingestion/`)
- Legacy `graphrag/` module (migration to `src/realestaterag/graph/`)

### Notes
- Breaking change: Input format now expects `entities + relationships` instead of nested JSON
- Requires Python 3.10+
- FalkorDB graph name: `wolbu_v3`

---

## [0.3.0] - 2024-12-11 (GraphRAG v3.0)

### Added
- GraphRAG v3.0 ontology with entity-centric design
- `Infra` nodes for named facilities
- `MarketSnapshot` nodes for time-series data
- `Neighborhood` nodes for spatial hierarchy
- Migration script (`scripts/migrate_v2_to_v3.py`)
- Query engine v3 with facility-based search
- Comprehensive v3 documentation

---

## [0.2.0] - Previous

### Added
- Initial GraphRAG v2.0 implementation
- Basic ingestion pipeline
- Streamlit UI
- FalkorDB integration
