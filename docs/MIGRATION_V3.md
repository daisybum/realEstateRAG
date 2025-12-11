# GraphRAG v3.0 Migration Guide

v2.0에서 v3.0으로 마이그레이션하기 위한 완벽한 가이드

---

## 📋 Table of Contents

1. [왜 v3.0인가?](#왜-v30인가)
2. [주요 변경사항](#주요-변경사항)
3. [마이그레이션 전 체크리스트](#마이그레이션-전-체크리스트)
4. [단계별 마이그레이션](#단계별-마이그레이션)
5. [v2 vs v3 비교](#v2-vs-v3-비교)
6. [롤백 절차](#롤백-절차)
7. [FAQ](#faq)

---

## 왜 v3.0인가?

### v2.0의 한계

**1. 검색 정밀도 부족**
```cypher
# v2.0: 교통 등급만 검색 가능
MATCH (r:Region)-[:HAS_GRADE]->(g:GradeMetric {category: 'Transport', grade: 'S'})

# 문제: "신분당선 라인"이나 "강남역 접근성" 검색 불가
```

**2. 시계열 분석 어려움**
```cypher
# v2.0: 가격이 Complex 속성에 고정
MATCH (c:ApartmentComplex)
WHERE c.jeonse_price > 80000

# 문제: 과거 가격 추이 분석 불가, 단일 스냅샷만 가능
```

**3. 투자 근거 추적 불가**
- "왜 이 단지가 좋은가?" → 모호한 등급만 제공
- 구체적 시설명 없음 → 설명 가능성 낮음

### v3.0의 개선점

✅ **Named Entity 기반 검색**
```cypher
# "강남역 30분 이내 단지" 검색 가능
MATCH (d:District)-[r:ACCESS_TO]->(i:Infra {name: '강남역'})
WHERE r.time_min <= 30
```

✅ **시계열 분석**
```cypher
# 가격 추이 분석 가능
MATCH (c:Complex)-[:HAS_SNAPSHOT]->(m:MarketSnapshot)
RETURN m.date, m.jeonse_price
ORDER BY m.date
```

✅ **명확한 투자 근거**
- "강남역 접근성" + "전세가율 63%" → 구체적 투자 판단 가능

---

## 주요 변경사항

### 1. 새로운 노드 타입

| 노드 | 설명 | 예시 |
|------|------|------|
| `Infra` | 구체적 시설 | "강남역", "Starfield Hanam" |
| `MarketSnapshot` | 시계열 데이터 | {date: "2024-12", price: 150000} |
| `Neighborhood` | 읍/면/동 | "풍덕천동" |

### 2. 데이터 재구조화

**Region (v2 → v3):**
```diff
# v2.0
Region {
  name: "용인시 수지구",
- population: 450000,
- supply_volume: 5000
}

# v3.0
Region {
  name: "용인시 수지구"
}
+ MarketSnapshot {
+   date: "2024-12",
+   population: 450000,
+   supply_volume: 5000
+ }
```

**Complex (v2 → v3):**
```diff
# v2.0
Complex {
  name: "은마아파트",
- sales_price: 150000,
- jeonse_price: 95000,
- jeonse_rate: 63.3
}

# v3.0
Complex {
  name: "은마아파트",
+ built_year: 1995
}
+ MarketSnapshot {
+   date: "2024-12",
+   sales_price: 150000,
+   jeonse_price: 95000,
+   jeonse_rate: 63.3
+ }
```

### 3. 새로운 관계

```cypher
# ACCESS_TO: 시설 접근성
(District)-[ACCESS_TO {time_min: 40}]->(Infra)

# CONTAINS_FACILITY: 지역 내 시설
(District)-[CONTAINS_FACILITY]->(Infra)

# HAS_SNAPSHOT: 시계열 연결
(Complex)-[HAS_SNAPSHOT]->(MarketSnapshot)
```

### 4. 코드 변경사항

**Import 변경:**
```python
# v2.0
from graphrag import GraphIngester, HybridRAGEngine

# v3.0 (자동)
from graphrag import GraphIngester, HybridRAGEngine  # 이제 v3를 가리킴

# v3.0 (명시적 - 권장)
from graphrag import GraphIngesterV3, HybridRAGEngineV3
```

**Graph 선택:**
```python
# v2.0
graph = db.select_graph("wolbu_v2")

# v3.0
graph = db.select_graph("wolbu_v3")
```

**LLM 출력 형식:**
```python
# v2.0 (nested JSON)
{
  "district": {...},
  "complexes": [...]
}

# v3.0 (entities + relationships)
{
  "entities": [
    {"id": "INFRA_GANGNAM_STATION", "type": "Infra", ...},
    {"id": "MARKET_EUNMA_202412", "type": "MarketSnapshot", ...}
  ],
  "relationships": [
    {"source": "...", "target": "...", "type": "ACCESS_TO"}
  ]
}
```

---

## 마이그레이션 전 체크리스트

### Prerequisites

- [ ] FalkorDB 컨테이너 실행 중
- [ ] v2.0 그래프 데이터 존재 (`wolbu_v2`)
- [ ] 디스크 공간 충분 (기존 데이터 2배 이상 권장)
- [ ] Python 3.8+ 설치
- [ ] `falkordb` 패키지 설치

### 백업 확인

```bash
# v2.0 그래프 백업
docker exec falkordb-gb10 redis-cli SAVE
docker exec falkordb-gb10 redis-cli --rdb /backup/wolbu_v2_backup.rdb

# 로컬로 복사
docker cp falkordb-gb10:/backup/wolbu_v2_backup.rdb ./backups/

# 백업 확인
ls -lh ./backups/wolbu_v2_backup.rdb
```

### 의존성 설치

```bash
pip install falkordb pydantic
```

---

## 단계별 마이그레이션

### Step 1: Dry Run 테스트

실제 데이터 쓰기 없이 시뮬레이션:

```bash
python3 scripts/migrate_v2_to_v3.py \
  --source-graph wolbu_v2 \
  --target-graph test_v3_migration \
  --dry-run \
  --migration-date 2024-12
```

**예상 출력:**
```
INFO: Starting migration (dry_run=True)...
INFO: Migrating Regions...
INFO: Migrating ApartmentComplexes...
INFO: Converting GradeMetrics to Infra...
INFO: Migration complete! Stats: {
  'regions_migrated': 25,
  'complexes_migrated': 150,
  'market_snapshots_created': 175,
  'infra_created': 12,
  'relationships_created': 187,
  'skipped': 0
}
```

### Step 2: 실제 마이그레이션

```bash
python3 scripts/migrate_v2_to_v3.py \
  --source-graph wolbu_v2 \
  --target-graph wolbu_v3 \
  --migration-date $(date +%Y-%m) \
  2>&1 | tee logs/migration_$(date +%Y%m%d_%H%M%S).log
```

**소요 시간:**
- 소규모 (< 100 노드): 1-2분
- 중규모 (100-1000 노드): 5-10분
- 대규모 (> 1000 노드): 15-30분

### Step 3: 검증

```bash
python3 scripts/migrate_v2_to_v3.py \
  --source-graph wolbu_v2 \
  --target-graph wolbu_v3 \
  --validate-only
```

**성공 예시:**
```
✅ Validation PASSED
  ✅ regions_count_match: True
  ✅ complexes_count_match: True
  ✅ market_snapshots_exist: True
```

**실패 시:**
```
❌ Validation FAILED
  ✅ regions_count_match: True
  ❌ complexes_count_match: False  # 25 != 23
  ✅ market_snapshots_exist: True
```
→ 로그 확인 후 재시도

### Step 4: 수동 검증

**그래프 통계 확인:**
```python
from falkordb import FalkorDB
from graphrag import HybridRAGEngineV3
from openai import OpenAI

db = FalkorDB()
graph = db.select_graph("wolbu_v3")
llm = OpenAI(base_url="http://localhost:8000/v1", api_key="EMPTY")
engine = HybridRAGEngineV3(graph, llm)

stats = engine.get_graph_statistics()
print("v3.0 Graph Statistics:")
for label, count in stats.items():
    print(f"  {label}: {count}")
```

**예상 출력:**
```
v3.0 Graph Statistics:
  Region: 25
  Neighborhood: 0  # (v2에서는 없었음)
  ApartmentComplex: 150
  Infra: 12
  MarketSnapshot: 175
  Report: 0
  InvestmentAnalysis: 0
```

**샘플 쿼리 테스트:**
```python
# Infra 노드 확인
result = graph.query("MATCH (i:Infra) RETURN i.name, i.category LIMIT 5")
for row in result.result_set:
    print(f"  {row[0]} ({row[1]})")

# MarketSnapshot 확인
result = graph.query("""
  MATCH (c:ApartmentComplex)-[:HAS_SNAPSHOT]->(m:MarketSnapshot)
  RETURN c.name, m.date, m.jeonse_rate
  LIMIT 5
""")
for row in result.result_set:
    print(f"  {row[0]}: {row[2]}% (as of {row[1]})")
```

### Step 5: 애플리케이션 업데이트

**코드 변경:**
```python
# Before (v2.0)
from graphrag import GraphIngester, HybridRAGEngine
graph = db.select_graph("wolbu_v2")
ingester = GraphIngester(graph)
engine = HybridRAGEngine(graph, llm)

# After (v3.0)
from graphrag import GraphIngesterV3, HybridRAGEngineV3
graph = db.select_graph("wolbu_v3")
ingester = GraphIngesterV3(graph)
engine = HybridRAGEngineV3(graph, llm)
```

**프롬프트 변경:**
```python
# v3.0 프롬프트 사용
from analysis.prompt_manager import PromptManager
pm = PromptManager()
prompt = pm.get_prompt("graph_construction_v3")  # v2 대신 v3
```

### Step 6: 모니터링

첫 24시간 동안:
- 쿼리 성능 모니터링
- 에러 로그 확인
- LangSmith 트레이스 검토

---

## v2 vs v3 비교

### 데이터 모델

| 측면 | v2.0 | v3.0 |
|------|------|------|
| **Region** | population, supply 포함 | 정적 정보만 |
| **Complex** | 가격 정보 포함 | 정적 정보만 |
| **시계열** | 불가능 | MarketSnapshot |
| **시설** | 등급만 (S/A/B/C) | 구체적 이름 (Infra) |
| **공간 계층** | Region → Complex | Region → District → Neighborhood → Complex |

### 쿼리 기능

| 쿼리 타입 | v2.0 | v3.0 |
|-----------|------|------|
| 전세가율 검색 | ✅ | ✅ |
| 등급 기반 검색 | ✅ | ✅ (개선) |
| 시설명 검색 | ❌ | ✅ **NEW** |
| 접근성 검색 | ❌ | ✅ **NEW** |
| 가격 추이 | ❌ | ✅ **NEW** |
| 시계열 분석 | ❌ | ✅ **NEW** |

### 성능

| 지표 | v2.0 | v3.0 |
|------|------|------|
| 노드 수 | 100% | ~115% (+Infra, +Snapshot) |
| 엣지 수 | 100% | ~120% (추가 관계) |
| 쿼리 속도 | 기준 | 유사 (~5% slower for complex queries) |
| 스토리지 | 기준 | ~130% (MarketSnapshot 복제) |

---

## 롤백 절차

### 즉시 롤백 (애플리케이션만)

```python
# v2.0으로 되돌리기
from graphrag import GraphIngesterV2, HybridRAGEngineV2
graph = db.select_graph("wolbu_v2")  # v2 그래프 사용
ingester = GraphIngesterV2(graph)
engine = HybridRAGEngineV2(graph, llm)
```

### 전체 롤백 (데이터 복원)

```bash
# 1. FalkorDB 중지
docker-compose down

# 2. 백업 복원
docker cp ./backups/wolbu_v2_backup.rdb falkordb-gb10:/data/dump.rdb

# 3. 재시작
docker-compose up -d

# 4. 확인
redis-cli
> SELECT 0
> KEYS *
```

---

## FAQ

### Q1: v2와 v3를 동시에 사용할 수 있나요?
**A:** 네, 가능합니다.
```python
# v2 사용
from graphrag import GraphIngesterV2, HybridRAGEngineV2
graph_v2 = db.select_graph("wolbu_v2")
engine_v2 = HybridRAGEngineV2(graph_v2, llm)

# v3 사용
from graphrag import GraphIngesterV3, HybridRAGEngineV3
graph_v3 = db.select_graph("wolbu_v3")
engine_v3 = HybridRAGEngineV3(graph_v3, llm)
```

### Q2: 마이그레이션 중 v2 데이터가 삭제되나요?
**A:** 아니요. v2 그래프(`wolbu_v2`)는 그대로 유지되며, v3는 새 그래프(`wolbu_v3`)에 생성됩니다.

### Q3: 마이그레이션 실패 시 어떻게 하나요?
**A:** 
1. 로그 확인: `logs/migration_*.log`
2. v3 그래프 삭제: `graph.delete()`
3. 문제 해결 후 재시도

### Q4: Infra 노드가 예상보다 적게 생성됩니다.
**A:** v2.0 GradeMetric의 `evidence_text`에 구체적 시설명이 없으면 Infra로 변환되지 않습니다. 이는 정상입니다. v3.0 프롬프트로 새 데이터를 수집하면 Infra 노드가 자동 생성됩니다.

### Q5: MarketSnapshot이 모든 Complex에 생성되지 않습니다.
**A:** v2.0에서 가격 정보가 없던 Complex는 MarketSnapshot이 생성되지 않습니다. 이는 의도된 동작입니다.

### Q6: 마이그레이션 후 스토리지가 많이 증가했습니다.
**A:** MarketSnapshot 노드로 인한 증가입니다. 예상 증가량은 약 30%입니다. 필요시 오래된 스냅샷 정리:
```cypher
MATCH (m:MarketSnapshot)
WHERE m.date < '2024-01'
DETACH DELETE m
```

### Q7: v3.0으로 마이그레이션해야 하나요?
**A:** 
- **필수**: 시설 기반 검색, 가격 추이 분석이 필요한 경우
- **선택**: 현재 v2.0으로 충분한 경우 (v2.0도 계속 지원됨)

### Q8: 프로덕션 환경에서 마이그레이션 시 주의사항은?
**A:**
1. 트래픽이 적은 시간대 선택
2. 반드시 백업 먼저
3. Staging 환경에서 먼저 테스트
4. 모니터링 준비 (LangSmith, 로그)
5. 롤백 계획 수립

---

## 추가 리소스

- [v3.0 Testing & Deployment Guide](./graphrag_v3_testing_deployment.md)
- [Implementation Plan](../brain/implementation_plan.md)
- [Migration Script](../scripts/migrate_v2_to_v3.py)
- [GitHub PR](https://github.com/daisybum/realEstateRAG/pull/new/schema-v3)

---

**마지막 업데이트:** 2024-12-11  
**버전:** v3.0.0
