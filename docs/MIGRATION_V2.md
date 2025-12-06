# Schema v2.0 Migration Guide

## 개요

v2.0 스키마는 **추론 가능한(Inference-ready)** 그래프 구조를 제공합니다.

### 주요 변경사항

| 항목 | v1.0 | v2.0 |
|------|------|------|
| Report 추적 | ❌ | ✅ Report 노드 |
| 투자 판단 | Complex 속성 | ✅ InvestmentAnalysis 노드 |
| 정량 지표 | Region 속성 | ✅ Indicator 노드 |
| 추론 체인 | ❌ | ✅ Grade → Analysis |

---

## 새로운 노드

### 1. Report
```python
Report {
    report_id: "3667403",
    title: "부산진구 임장보고서",
    confidence_score: 0.85,
    analysis_date: "2025-12-06"
}
```

**관계:**
- `(Report)-[:ANALYZES]->(Region)`
- `(Report)-[:MENTIONS]->(Complex)`

### 2. InvestmentAnalysis
```python
InvestmentAnalysis {
    verdict: "Undervalued",  # Undervalued | Fair | Risky
    reasoning: "전세가율 64%, 저평가 구간",
    confidence: 0.82
}
```

**관계:**
- `(Complex)-[:HAS_ANALYSIS]->(Analysis)`
- `(Grade)-[:SUPPORTS]->(Analysis)` ⚡ 추론 체인

### 3. Indicator
```python
Indicator {
    type: "population",
    value: 44035,
    unit: "명"
}
```

**관계:**
- `(Region)-[:HAS_INDICATOR]->(Indicator)`

---

## 마이그레이션

### 자동 마이그레이션 (권장)

```bash
# 미리보기 (변경 없음)
python scripts/migrate_to_v2.py --dry-run

# 실제 적용
python scripts/migrate_to_v2.py --backup
```

### 변환 로직

**1. Region.population → Indicator**
```cypher
// Before
(r:Region {population: 44035})

// After
(r:Region)-[:HAS_INDICATOR]->(i:Indicator {type: 'population', value: 44035})
```

**2. Complex.is_undervalued → InvestmentAnalysis**
```cypher
// Before
(c:Complex {is_undervalued: true})

// After
(c:Complex)-[:HAS_ANALYSIS]->(a:InvestmentAnalysis {verdict: 'Undervalued'})
```

**3. Report 노드 생성**
```cypher
// 각 Region마다 하나의 Report 생성
CREATE (rep:Report {report_id: 'migrated_부산진구'})
CREATE (rep)-[:ANALYZES]->(r:Region {name: '부산진구'})
```

---

## Breaking Changes

### Region 노드
```python
# ❌ v1.0 (제거)
region.population
region.appropriate_demand
region.supply_risk_status

# ✅ v2.0 (대체)
(region)-[:HAS_INDICATOR]->(i:Indicator {type: 'population'})
(region)-[:HAS_INDICATOR]->(i:Indicator {type: 'appropriate_demand'})
```

### ApartmentComplex 노드
```python
# ❌ v1.0 (제거)
complex.is_undervalued
complex.investment_comment

# ✅ v2.0 (대체)
(complex)-[:HAS_ANALYSIS]->(a:InvestmentAnalysis {verdict: 'Undervalued'})
```

---

## 새로운 쿼리 예시

### 추론 체인 조회
```cypher
MATCH path = (c:ApartmentComplex {name: '가야롯데캐슬골드아너'})
             -[:HAS_ANALYSIS]->(a:InvestmentAnalysis)
             <-[:SUPPORTS]-(g:GradeMetric)
RETURN a.verdict, a.reasoning, 
       collect({category: g.category, grade: g.grade}) as supporting_evidence
```

### 저평가 단지 (v2.0)
```cypher
MATCH (c:ApartmentComplex)-[:HAS_ANALYSIS]->(a:InvestmentAnalysis {verdict: 'Undervalued'})
MATCH (c)-[:LOCATED_IN]->(r:Region)
WHERE c.jeonse_rate >= 60
RETURN c.name, c.jeonse_rate, a.reasoning, r.name
ORDER BY c.jeonse_rate DESC
```

### 지표 기반 리스크 분석
```cypher
MATCH (r:Region)-[:HAS_INDICATOR]->(i1:Indicator {type: 'supply_volume_3yr'})
MATCH (r)-[:HAS_INDICATOR]->(i2:Indicator {type: 'appropriate_demand'})
WHERE toFloat(i1.value) > toFloat(i2.value) * 2
RETURN r.name, i1.value as supply, i2.value as demand,
       toFloat(i1.value) / toFloat(i2.value) as risk_ratio
ORDER BY risk_ratio DESC
```

---

## 검증

마이그레이션 후 검증:

```bash
# Python으로 통계 확인
python -c "
from falkordb import FalkorDB
from graphrag.graph_schema import GraphSchemaManager

db = FalkorDB.from_url('redis://localhost:6379')
graph = db.select_graph('real_estate')

manager = GraphSchemaManager(graph)
stats = manager.get_statistics()
print(stats)
"
```

**예상 결과:**
```python
{
    'Report': 50,           # 지역당 1개
    'Region': 50,
    'ApartmentComplex': 200,
    'InvestmentAnalysis': 200,  # Complex당 1개
    'Indicator': 150,       # Region당 2-3개
    'GradeMetric': 200,     # Region당 4개
}
```

---

## Rollback

문제 발생 시 v1.0으로 복구:

```bash
# 1. 백업에서 복원 (권장)
# (백업 파일로 복원 로직)

# 2. 수동 복구
python scripts/rollback_v2.py  # TODO: 구현 필요
```
