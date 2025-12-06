# FalkorDB for Real Estate GraphRAG

GB10 ARM64 환경에 최적화된 FalkorDB 그래프 데이터베이스 서버

## 빠른 시작

```bash
# 서버 시작
docker compose up -d

# 로그 확인
docker compose logs -f

# 서버 중지
docker compose down
```

## 접속 정보

| 항목 | 값 |
|------|-----|
| **Redis Protocol** | `redis://localhost:6379` |
| **Browser UI** | http://localhost:3000 |

## 리소스 할당

| 항목 | 값 | 비고 |
|------|-----|------|
| 메모리 제한 | 16GB | LLM 메모리 여유 확보 |
| CPU 스레드 | 16개 | GB10 20코어 중 16개 |

## 테스트

```bash
# Redis CLI로 연결
docker exec -it falkordb-gb10 redis-cli

# 그래프 생성 테스트
127.0.0.1:6379> GRAPH.QUERY real_estate "CREATE (:Region {name: 'test'})"
```

## Python 연결

```python
from falkordb import FalkorDB

db = FalkorDB(host='localhost', port=6379)
graph = db.select_graph('real_estate')

# Cypher 쿼리 실행
result = graph.query("MATCH (r:Region) RETURN r.name")
```
