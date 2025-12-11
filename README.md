# RealEstateRAG

GraphRAG-powered Real Estate Intelligence Platform

## 🚀 Quick Start

```bash
# Clone repository
git clone https://github.com/daisybum/realEstateRAG.git
cd realEstateRAG

# Install with uv
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Start API server
python -m realestaterag.api.main
```

## 📦 Installation

### Development
```bash
make dev
```

### Production
```bash
make install
```

## 🏗️ Architecture

```
src/realestaterag/
├── core/          # Domain models, enums, exceptions
├── config/        # Pydantic Settings
├── ingestion/     # Multimodal analysis pipeline
├── query/         # Natural language query engine
├── api/           # FastAPI REST API
├── graph/         # GraphRAG v3.0 (legacy integration)
└── infrastructure/# DB, LLM, Storage clients
```

## 🔧 Configuration

Copy `.env.example` to `.env` and configure:

```bash
# LLM
LLM_API_URL=http://localhost:8000/v1
LLM_MODEL=Qwen/Qwen3-VL-30B-A3B-Instruct

# FalkorDB
FALKORDB_HOST=localhost
FALKORDB_PORT=6379
FALKORDB_GRAPH_NAME=wolbu_v3
```

## 📡 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/api/v1/query` | Natural language query |
| POST | `/api/v1/query/facility` | Facility-based search |
| POST | `/api/v1/query/price-trend` | Price trend query |
| POST | `/api/v1/ingestion/single` | Single report ingestion |
| POST | `/api/v1/ingestion/batch` | Batch ingestion |

## 🐳 Docker

```bash
# Start all services
docker-compose -f deployments/docker/docker-compose.yml up -d

# With monitoring
docker-compose -f deployments/docker/docker-compose.yml --profile monitoring up -d
```

## ☸️ Kubernetes

```bash
# Development
kubectl apply -k deployments/kubernetes/base

# Production
kubectl apply -k deployments/kubernetes/overlays/production
```

## 🧪 Testing

```bash
# All tests
make test

# With coverage
pytest tests/ --cov=src/realestaterag --cov-report=html

# Linting
make lint
```

## 📚 Documentation

- [Migration Guide](docs/MIGRATION_V3.md) - v2.0 → v3.0 migration
- [Production Roadmap](docs/PRODUCTION_ROADMAP.md) - Architecture plan
- [Testing Guide](docs/graphrag_v3_testing_deployment.md) - Testing & deployment

## 🔄 GraphRAG v3.0

This project uses an entity-centric knowledge graph:

**Nodes:** Region, District, Neighborhood, Complex, Infra, MarketSnapshot

**Key Features:**
- Named facility extraction (강남역, Starfield, etc.)
- Time-series price data separation
- Multi-hop graph traversal queries

## 📊 Example Queries

```python
from realestaterag.query import QueryEngine

engine = QueryEngine()

# Facility access query
result = await engine.query("강남역 30분 이내 전세가율 60% 이상 단지")

# Price trend
result = await engine.get_price_trend("은마아파트")
```

## 🛠️ Development

```bash
# Format code
make format

# Build Docker image
make docker-build
```

## 📄 License

MIT

## 👥 Contributors

- daisybum
