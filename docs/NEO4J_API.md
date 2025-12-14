# Neo4j API Usage Guide

## Endpoints

### 1. Semantic Search (Vector Search)
의미론적 유사도 기반 검색

```bash
POST /api/v1/neo4j/semantic
```

**Request:**
```json
{
  "query": "전세가율 높은 아파트",
  "node_type": "Complex",
  "top_k": 10
}
```

**Response:**
```json
{
  "query": "전세가율 높은 아파트",
  "results": [
    {
      "name": "래미안수지",
      "address": "경기도 용인시 수지구",
      "description": "래미안수지 경기도 용인시 수지구 1000세대",
      "score": 0.89
    }
  ],
  "count": 10
}
```

---

### 2. Facility-Based Search
시설 기반 그래프 탐색

```bash
POST /api/v1/neo4j/facility
```

**Request:**
```json
{
  "facility": "강남역",
  "max_distance": 30,
  "jeonse_ratio": 60.0,
  "min_price": 50000,
  "max_price": 150000
}
```

**Response:**
```json
{
  "facility": "강남역",
  "results": [
    {
      "complex_name": "래미안수지",
      "address": "경기도 용인시",
      "distance": 25,
      "price": 120000,
      "jeonse_ratio": 65.5
    }
  ],
  "count": 5
}
```

---

### 3. Hybrid Search
벡터 + 그래프 결합 검색

```bash
POST /api/v1/neo4j/hybrid
```

**Request:**
```json
{
  "query": "판교 근처 투자 가치 높은 단지",
  "filters": {
    "jeonse_ratio": 60
  },
  "top_k": 10
}
```

---

### 4. Graph Statistics
그래프 통계 정보

```bash
GET /api/v1/neo4j/statistics
```

**Response:**
```json
{
  "statistics": {
    "complex_count": 150,
    "marketsnapshot_count": 450,
    "facility_count": 80,
    "district_count": 25,
    "relationship_count": 680
  }
}
```

---

### 5. Health Check
Neo4j 연결 상태 확인

```bash
GET /api/v1/neo4j/health
```

---

## Python Client Example

```python
import httpx

async def search_complexes():
    async with httpx.AsyncClient() as client:
        # Semantic search
        response = await client.post(
            "http://localhost:8000/api/v1/neo4j/semantic",
            json={
                "query": "전세가율 높은 아파트",
                "top_k": 5
            }
        )
        results = response.json()
        print(f"Found {results['count']} results")
        
        # Facility search
        response = await client.post(
            "http://localhost:8000/api/v1/neo4j/facility",
            json={
                "facility": "강남역",
                "max_distance": 30
            }
        )
        results = response.json()
        for item in results['results']:
            print(f"{item['complex_name']}: {item['distance']}분")
```

---

## Setup

1. **Start Neo4j**
```bash
docker-compose up -d neo4j
```

2. **Run Migration**
```bash
python scripts/migrate_to_neo4j.py
```

3. **Start API**
```bash
python -m realestaterag.api.main
```

4. **Test Endpoints**
```bash
# Visit OpenAPI docs
open http://localhost:8000/docs

# Or test with curl
curl -X POST http://localhost:8000/api/v1/neo4j/semantic \
  -H "Content-Type: application/json" \
  -d '{"query": "투자 가치 좋은 단지", "top_k": 5}'
```

---

## Notes

- Vector search requires Neo4j 5.11+ with vector index support
- Falls back to text-based search if vector indexes unavailable
- All endpoints support async operations
- Results include similarity scores for semantic search
