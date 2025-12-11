# GraphRAG v3.0 Testing & Deployment Guide

## Testing Guide

### 1. Unit Tests

**Schema Tests:**
```bash
# Test v3.0 schema
python3 graphrag/graph_schema_v3.py

# Expected output:
# === Wolbu Ontology Schema v3.0 ===
# Infra example: {'name': '강남역', 'category': 'Subway', ...}
# MarketSnapshot example: {'date': '2024-12', ...}
```

**Pydantic Model Tests:**
```bash
# Test Pydantic validation
python3 graphrag/pydantic_models_v3.py

# Expected output:
# === Pydantic Models v3.0 Test ===
# ✓ Created KnowledgeGraphOutput with 2 entities
# ✓ All tests passed
```

### 2. Integration Tests

**Graph Ingestion Test:**
```python
from graphrag import GraphIngesterV3, WolbuOntologyV3
from graphrag.pydantic_models_v3 import KnowledgeGraphOutput, Entity, Relationship, EntityType
from falkordb import FalkorDB

# Setup
db = FalkorDB()
graph = db.select_graph("test_v3")
ingester = GraphIngesterV3(graph)

# Test data
test_kg = KnowledgeGraphOutput(
    entities=[
        Entity(id="GYEONGGI_SUJI", type=EntityType.DISTRICT, name="수지구", properties={}),
        Entity(id="INFRA_GANGNAM_STATION", type=EntityType.INFRA, name="강남역", 
               properties={"category": "Subway", "tier": "S"}),
        Entity(id="MARKET_SUJI_202412", type=EntityType.MARKET_SNAPSHOT, date="2024-12",
               properties={"population": 450000}),
    ],
    relationships=[
        Relationship(source="GYEONGGI_SUJI", target="INFRA_GANGNAM_STATION", 
                    type="ACCESS_TO", properties={"time_min": 40}),
        Relationship(source="GYEONGGI_SUJI", target="MARKET_SUJI_202412",
                    type="HAS_SNAPSHOT", properties={}),
    ]
)

# Ingest
stats = ingester.ingest_knowledge_graph(test_kg)
print(f"Created {stats['nodes_created']} nodes, {stats['relationships_created']} relationships")

# Verify
result = graph.query("MATCH (i:Infra {name: '강남역'}) RETURN i")
assert len(result.result_set) == 1
print("✓ Infra node created successfully")
```

**Query Engine Test:**
```python
from graphrag import HybridRAGEngineV3
from openai import OpenAI

# Setup
llm = OpenAI(base_url="http://localhost:8000/v1", api_key="EMPTY")
engine = HybridRAGEngineV3(graph, llm)

# Test facility-based search
result = engine.query("강남역 30분 이내 전세가율 60% 이상 단지")
print(f"Query type: {result.query_type}")
print(f"Results: {len(result.graph_results)}")
print(f"Confidence: {result.confidence}")

# Test price trend
complexes = engine.get_price_trend("은마아파트")
assert len(complexes) > 0
print("✓ Query engine working")
```

### 3. Migration Test

**Dry Run:**
```bash
python3 scripts/migrate_v2_to_v3.py \
  --source-graph wolbu_v2 \
  --target-graph test_migration_v3 \
  --dry-run

# Expected output:
# === Migration Statistics ===
# regions_migrated: X
# complexes_migrated: Y
# market_snapshots_created: Z
```

**Actual Migration:**
```bash
# Backup v2.0 data first!
docker exec falkordb-gb10 redis-cli --rdb /var/lib/falkordb/backup_v2.rdb

# Run migration
python3 scripts/migrate_v2_to_v3.py \
  --source-graph wolbu_v2 \
  --target-graph wolbu_v3 \
  --migration-date 2024-12

# Validate
python3 scripts/migrate_v2_to_v3.py \
  --source-graph wolbu_v2 \
  --target-graph wolbu_v3 \
  --validate-only

# Expected:
# ✅ Validation PASSED
#   ✅ regions_count_match: True
#   ✅ complexes_count_match: True
#   ✅ market_snapshots_exist: True
```

### 4. LangSmith Quality Check

**Setup LangSmith Tracing:**
```python
import os
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "graphrag-v3-testing"

# Run queries and check LangSmith dashboard
# https://smith.langchain.com
```

---

## Deployment Guide

### Prerequisites

1. **FalkorDB Running:**
   ```bash
   cd docker/falkordb
   docker-compose up -d
   ```

2. **LLM Server Running:**
   ```bash
   # llama.cpp or vLLM
   cd docker/llama-server
   docker-compose up -d
   ```

3. **Environment Variables:**
   ```bash
   export LLM_MODEL="Qwen/Qwen3-VL-30B-A3B-Instruct"
   export FALKORDB_URL="redis://localhost:6379"
   export LANGSMITH_API_KEY="your_key"
   export LANGSMITH_PROJECT="graphrag-v3-prod"
   ```

### Deployment Steps

#### 1. Backup Existing Data
```bash
# Backup v2.0 graph
docker exec falkordb-gb10 redis-cli SAVE
docker exec falkordb-gb10 redis-cli --rdb /backup/wolbu_v2_$(date +%Y%m%d).rdb

# Export to local
docker cp falkordb-gb10:/backup/wolbu_v2_$(date +%Y%m%d).rdb ./backups/
```

#### 2. Deploy v3.0 Schema
```python
from falkordb import FalkorDB
from graphrag.graph_schema_v3 import GraphSchemaManagerV3

db = FalkorDB()
graph = db.select_graph("wolbu_v3")
manager = GraphSchemaManagerV3(graph)
manager.initialize_schema()

print("✓ v3.0 schema initialized")
```

#### 3. Run Migration
```bash
python3 scripts/migrate_v2_to_v3.py \
  --source-graph wolbu_v2 \
  --target-graph wolbu_v3 \
  --migration-date $(date +%Y-%m) \
  2>&1 | tee logs/migration_$(date +%Y%m%d_%H%M%S).log
```

#### 4. Validate Migration
```bash
python3 scripts/migrate_v2_to_v3.py \
  --source-graph wolbu_v2 \
  --target-graph wolbu_v3 \
  --validate-only
```

#### 5. Update Application
```python
# Update main application to use v3
from graphrag import GraphIngesterV3, HybridRAGEngineV3

# Change graph selection
graph = db.select_graph("wolbu_v3")  # was "wolbu_v2"

# Use v3 components
ingester = GraphIngesterV3(graph)
engine = HybridRAGEngineV3(graph, llm)
```

#### 6. Monitor
```bash
# Check graph statistics
python3 -c "
from falkordb import FalkorDB
from graphrag import HybridRAGEngineV3, GraphIngesterV3
from openai import OpenAI

db = FalkorDB()
graph = db.select_graph('wolbu_v3')
llm = OpenAI(base_url='http://localhost:8000/v1', api_key='EMPTY')
engine = HybridRAGEngineV3(graph, llm)

stats = engine.get_graph_statistics()
print('Graph Statistics:')
for label, count in stats.items():
    print(f'  {label}: {count}')
"
```

### Rollback Plan

If issues occur:

```bash
# 1. Stop application
# 2. Switch back to v2.0
from graphrag import GraphIngesterV2, HybridRAGEngineV2
graph = db.select_graph("wolbu_v2")

# 3. Restore from backup if needed
docker exec -i falkordb-gb10 redis-cli --pipe < backups/wolbu_v2_YYYYMMDD.rdb
```

---

## Performance Monitoring

### Key Metrics

1. **Ingestion Performance:**
   - Entities/second
   - Relationships/second
   - Validation failures

2. **Query Performance:**
   - Cypher execution time
   - LLM response time
   - Result count distribution

3. **Data Quality:**
   - LangSmith trace success rate
   - Confidence score distribution
   - Hallucination detection

### Monitoring Script
```python
import time
from graphrag import GraphIngesterV3, HybridRAGEngineV3

# Ingestion benchmark
start = time.time()
stats = ingester.ingest_from_llm_output(llm_output)
duration = time.time() - start

print(f"Ingestion: {stats['nodes_created']} nodes in {duration:.2f}s")
print(f"Throughput: {stats['nodes_created']/duration:.1f} nodes/sec")

# Query benchmark
queries = [
    "강남역 30분 이내 단지",
    "은마아파트 가격 추이",
    "수지구 백화점 목록",
]

for q in queries:
    start = time.time()
    result = engine.query(q)
    duration = time.time() - start
    print(f"{q}: {duration:.2f}s, {len(result.graph_results)} results")
```

---

## Breaking Changes Summary

### Code Changes Required

1. **Import Changes:**
   ```python
   # Before (v2.0)
   from graphrag import GraphIngester, HybridRAGEngine
   
   # After (v3.0) - automatic
   from graphrag import GraphIngester, HybridRAGEngine  # now v3
   
   # Or explicit (recommended during transition)
   from graphrag import GraphIngesterV3, HybridRAGEngineV3
   ```

2. **Graph Selection:**
   ```python
   # Before
   graph = db.select_graph("wolbu_v2")
   
   # After
   graph = db.select_graph("wolbu_v3")
   ```

3. **Input Format:**
   ```python
   # v2.0 format (nested JSON)
   {
     "district": {...},
     "complexes": [...]
   }
   
   # v3.0 format (entities + relationships)
   {
     "entities": [...],
     "relationships": [...]
   }
   ```

### Data Migration Required

- Region.population → MarketSnapshot.population
- Complex prices → MarketSnapshot nodes
- New nodes required: Neighborhood, Infra, MarketSnapshot

### Feature Additions

- Facility-based queries
- Price trend analysis
- Time-series support
- Named entity extraction
