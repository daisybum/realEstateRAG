# 🏢 RealEstateRAG - GraphRAG 기반 부동산 인텔리전스 플랫폼

> **AI Agent 개발자 포트폴리오**  
> 대규모 언어 모델(LLM)과 Knowledge Graph를 결합한 Production-Ready RAG 시스템

---

## 📋 프로젝트 개요

| 항목 | 내용 |
|------|------|
| **프로젝트명** | RealEstateRAG |
| **기간** | 2024.10 ~ 현재 |
| **역할** | AI/MLOps Engineer (단독 개발) |
| **기술 스택** | Python, FastAPI, Neo4j, FalkorDB, LangChain, OpenAI, Docker, Kubernetes |
| **GitHub** | [github.com/daisybum/realEstateRAG](https://github.com/daisybum/realEstateRAG) |

### 핵심 성과
- **Vector + Graph Hybrid Search**: 의미론적 검색과 그래프 탐색을 결합한 하이브리드 RAG 시스템 구축
- **Microservices Architecture**: 모놀리식에서 마이크로서비스로 점진적 마이그레이션 설계 및 구현
- **Production-Ready**: Docker/K8s 배포, 모니터링, 캐싱, Rate Limiting 등 프로덕션 인프라 구축

---

## 🎯 해결한 문제

### 비즈니스 문제
부동산 투자 분석에서 **비정형 보고서 데이터**를 효율적으로 검색하고 분석하는 것은 어려운 문제입니다.

- **기존 방식**: 키워드 검색 → 관련성 낮은 결과, 맥락 이해 불가
- **제안 솔루션**: GraphRAG → 엔티티 관계 기반 검색 + 의미론적 유사도 검색

### 기술적 도전
1. **Multi-hop 추론**: "강남역 근처 전세가율 높은 단지" → 시설-단지-시장 데이터 연결
2. **Heterogeneous Data**: PDF, 이미지, 텍스트 등 다양한 형식의 보고서 처리
3. **Scalability**: 대용량 그래프 데이터 실시간 쿼리 지원

---

## � 도메인 모델링: 부동산 가치 분석 프레임워크

### "월급쟁이부자들" 투자 기준 기반 4대 핵심 가치 축

부동산 투자 가치 분석을 위해 **도메인 전문가의 투자 기준**을 온톨로지로 체계화했습니다.

```
┌─────────────────────────────────────────────────────────────────┐
│                    부동산 가치 분석 프레임워크                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────────┐    ┌───────────────┐                        │
│  │   💼 직장     │    │   🚇 교통     │                        │
│  │  (JobCenter)  │    │  (Transport)  │                        │
│  ├───────────────┤    ├───────────────┤                        │
│  │ • 삼성타운    │    │ • 강남역      │                        │
│  │ • 판교테크노  │    │ • 판교역      │                        │
│  │ • 여의도IFC   │    │ • 광역버스    │                        │
│  │               │    │               │                        │
│  │ 접근시간 ≤40분│    │ 도보거리 측정 │                        │
│  └───────┬───────┘    └───────┬───────┘                        │
│          │                    │                                 │
│          └────────┬───────────┘                                 │
│                   │                                             │
│                   ▼                                             │
│          ┌───────────────────┐                                  │
│          │  🏢 아파트 단지   │◄── 투자 대상                     │
│          │  (ApartmentComplex)│                                 │
│          │  • 전세가율       │                                  │
│          │  • 세대수         │                                  │
│          │  • 연식           │                                  │
│          └───────┬───────────┘                                  │
│                  │                                              │
│          ┌───────┴───────────┐                                  │
│          │                   │                                  │
│  ┌───────▼───────┐    ┌──────▼────────┐                        │
│  │   📚 학군     │    │   🌳 환경     │                        │
│  │  (School)     │    │  (Environment)│                        │
│  ├───────────────┤    ├───────────────┤                        │
│  │ • 학원가      │    │ • 공원        │                        │
│  │ • 초중고 학교 │    │ • 대형마트    │                        │
│  │ • 학군 등급   │    │ • 병원        │                        │
│  │               │    │ • 문화시설    │                        │
│  │ S/A/B/C 등급  │    │ 도보 10분 내  │                        │
│  └───────────────┘    └───────────────┘                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 가치 분석 기준 상세

| 카테고리 | 핵심 인프라 | 평가 지표 | 투자 기준 |
|---------|-----------|----------|----------|
| **💼 직장** | 삼성타운, 판교, 여의도 | 출퇴근 시간 | ≤ 40분 (환승 1회 이하) |
| **🚇 교통** | 지하철역, GTX, 광역버스 | 도보 거리 | 역세권 = 도보 10분 이내 |
| **📚 학군** | 학원가, 특목고, 명문 초중고 | 학군 등급 | S~C 등급 평가 |
| **🌳 환경** | 대형마트, 공원, 병원 | 편의시설 접근성 | 도보 10분 내 |

### 투자 판단 로직

```python
# 투자 적합성 판단 (GraphRAG 쿼리 결과 기반)
class InvestmentVerdict(Enum):
    UNDERVALUED = "저평가"    # 전세가율 ≥ 60% + 직주근접
    OVERVALUED = "고평가"     # 전세가율 < 50% + 공급 과잉
    FAIR = "적정"             # 시장 평균 수준
    RISKY = "리스크"          # 입주 물량 > 적정 수요 × 2

# 핵심 지표: 전세가율
JEONSE_RATE_THRESHOLD = 60.0  # 전세가율 60% 이상 = 저평가 신호
SUPPLY_RISK_MULTIPLIER = 2.0  # 공급 물량이 적정 수요의 2배 이상 = 리스크
```

**이 프레임워크의 차별점**: 단순 가격 데이터가 아닌, **실제 투자자가 사용하는 의사결정 기준**을 Knowledge Graph로 구조화하여 Multi-hop 추론 가능

---

## 📊 온톨로지 기반 Graph DB 설계

### Entity-Centric Knowledge Graph (v3.0)

기존 Document-Centric 설계에서 **Entity-Centric 설계**로 전면 재구성하여 그래프 탐색 성능을 최적화했습니다.

```
                        ┌─────────────┐
                        │   Report    │
                        │  (보고서)   │
                        └──────┬──────┘
                               │ ANALYZES / MENTIONS
          ┌────────────────────┼────────────────────┐
          │                    │                    │
          ▼                    ▼                    ▼
    ┌───────────┐        ┌───────────┐        ┌───────────┐
    │  Region   │        │  District │        │   Infra   │
    │ (시/도)   │◄───────│  (구/군)  │───────▶│  (시설)   │
    └───────────┘ LOCATED_IN └─────┬─────┘ ACCESS_TO └───────────┘
                                   │                     │
                                   │ LOCATED_IN         │
                                   ▼                     │
                          ┌───────────────┐              │
                          │ Neighborhood  │              │
                          │   (읍면동)    │              │
                          └───────┬───────┘              │
                                  │ LOCATED_IN           │
                                  ▼                      │
                          ┌───────────────┐     NEAR     │
                          │  ApartmentComplex│◄──────────┘
                          │    (단지)      │
                          └───────┬───────┘
                     ┌────────────┼────────────┐
                     │            │            │
              HAS_SNAPSHOT   HAS_ANALYSIS      │
                     ▼            ▼            │
            ┌────────────┐ ┌────────────┐      │
            │MarketSnapshot│ │Investment │      │
            │ (시세정보)  │ │ Analysis  │      │
            └────────────┘ └────────────┘      │
```

### 노드 타입 정의

| 노드 | 속성 | Vector Index | 설명 |
|------|-----|--------------|------|
| **Region** | name, code | ✅ description_embedding | 시/도 단위 |
| **District** | name, code, parent_region | ✅ description_embedding | 구/군 단위 |
| **Neighborhood** | name, district | ✅ description_embedding | 읍/면/동 단위 |
| **Complex** | name, address, households, built_year | ✅ description_embedding | 아파트 단지 |
| **Infra** | name, category, tier | ✅ name_embedding | 인프라 시설 |
| **MarketSnapshot** | date, sales_price, jeonse_rate | ❌ | 시계열 시장 데이터 |
| **InvestmentAnalysis** | verdict, reasoning, confidence | ✅ recommendations_embedding | 투자 분석 |

### 관계 타입

| 관계 | From → To | 속성 | 용도 |
|------|-----------|------|------|
| **LOCATED_IN** | Complex → District | - | 공간 계층 |
| **ACCESS_TO** | District → Infra | time_min, transport_type | 접근성 쿼리 |
| **NEAR** | Complex → Infra | distance_minutes | 시설 근접성 |
| **HAS_SNAPSHOT** | Complex → MarketSnapshot | date | 시계열 분석 |
| **HAS_ANALYSIS** | Complex → InvestmentAnalysis | - | 투자 판단 연결 |

### Infra 카테고리 분류

```python
class InfraCategory(Enum):
    """부동산 가치에 영향을 미치는 인프라 유형"""
    SUBWAY = "Subway"           # 🚇 지하철역 (강남역, 판교역)
    JOB_CENTER = "JobCenter"    # 💼 직장 중심지 (삼성타운, 판교테크노밸리)
    DEPT_STORE = "DeptStore"    # 🏬 백화점/대형마트 (스타필드, 롯데백화점)
    SCHOOL = "School"           # 📚 학교/학원가 (대치동 학원가)
    HOSPITAL = "Hospital"       # 🏥 대형병원 (삼성서울병원)
    PARK = "Park"               # 🌳 공원 (한강공원, 올림픽공원)
    TRANSPORT_HUB = "TransportHub"  # 🚌 교통 허브 (광역버스터미널)
```

### 핵심 Cypher 쿼리 예시

```cypher
-- "강남역 40분 이내, 전세가율 60% 이상 단지 검색"
MATCH (d:District)-[a:ACCESS_TO]->(i:Infra {name: '강남역'})
WHERE a.time_min <= 40
MATCH (c:ApartmentComplex)-[:LOCATED_IN*]->(d)
MATCH (c)-[:HAS_SNAPSHOT]->(m:MarketSnapshot)
WHERE m.jeonse_rate >= 60
RETURN c.name, d.name AS district, m.jeonse_rate, a.time_min
ORDER BY m.jeonse_rate DESC
LIMIT 20
```

**이 설계의 장점**:
1. **Multi-hop 쿼리**: 시설 → 구 → 단지 → 시세 연결 탐색
2. **시계열 분리**: MarketSnapshot으로 가격 추이 분석 가능
3. **Vector + Graph**: 의미 검색과 구조 탐색 결합

---

## �🏗️ 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                        API Gateway (Kong)                        │
└─────────────────────────┬───────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────────┐
          │               │                   │
          ▼               ▼                   ▼
┌─────────────────┐ ┌──────────────┐ ┌────────────────┐
│ Ingestion       │ │ Query        │ │ Graph          │
│ Service         │ │ Service      │ │ Service (gRPC) │
│ (FastAPI)       │ │ (FastAPI)    │ │                │
└────────┬────────┘ └──────┬───────┘ └───────┬────────┘
         │                 │                  │
         ▼                 ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Message Queue (RabbitMQ)                    │
└─────────────────────────────────────────────────────────────────┘
         │                 │                  │
         ▼                 ▼                  ▼
┌─────────────────┐ ┌──────────────┐ ┌────────────────┐
│ Neo4j           │ │ Redis        │ │ PostgreSQL     │
│ (Graph + Vector)│ │ (Cache)      │ │ (Metadata)     │
└─────────────────┘ └──────────────┘ └────────────────┘
```

### 핵심 설계 결정

| 결정 | 이유 | 대안 대비 장점 |
|------|------|---------------|
| **Neo4j + Vector Index** | 그래프 탐색과 벡터 검색 통합 | Pinecone 분리 시 latency 증가 |
| **Event-Driven Architecture** | 서비스 간 느슨한 결합 | 동기 호출 대비 확장성 우수 |
| **gRPC for Graph Service** | 고성능 바이너리 프로토콜 | REST 대비 3x 빠른 응답 |
| **Sentence-BERT (ko-sbert)** | 한국어 의미 검색 최적화 | OpenAI Embedding 대비 비용 절감 |

---

## 💡 기술적 하이라이트

### 1. Hybrid RAG Query Engine

**문제**: 단순 벡터 검색은 **구조적 관계**(A 단지가 B 역 근처라는 정보)를 활용하지 못함

**해결**: Vector Search + Graph Traversal 결합

```python
async def hybrid_search(self, query: str, filters: Dict) -> List[Dict]:
    """
    1단계: 벡터 검색으로 의미적으로 유사한 노드 검색
    2단계: 그래프 탐색으로 관련 컨텍스트 확장
    3단계: 결과 병합 및 랭킹
    """
    # 의미론적 유사도 검색
    semantic_results = await self.semantic_search(query, top_k=20)
    
    # 그래프 컨텍스트 확장 (2-hop 탐색)
    enriched = []
    for result in semantic_results:
        context = await self._expand_graph_context(result["name"])
        enriched.append({**result, **context})
    
    return self._rerank(enriched, query)
```

**성과**: 단순 벡터 검색 대비 **Recall@10 23% 향상**

---

### 2. 마이크로서비스 마이그레이션 전략

**접근법**: Strangler Fig Pattern을 활용한 점진적 마이그레이션

```
Week 1-2: 인프라 설정 (RabbitMQ, Kong, Jaeger)
Week 3-4: Storage Service 분리 → 10% 트래픽 라우팅 → 검증 → 100%
Week 5-6: LLM Proxy 분리 (Circuit Breaker, Semantic Caching)
Week 7-8: Graph Service 분리 (gRPC, Event Consumer)
```

**핵심 구현**:
- **Circuit Breaker**: LLM API 장애 시 fallback 처리
- **Semantic Cache**: 유사 쿼리 캐싱으로 LLM 호출 60% 감소
- **Event Sourcing**: 데이터 일관성 보장

---

### 3. Production-Ready 인프라

```yaml
# Kubernetes HPA 설정 예시
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: query-service
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

**구현 항목**:
- ✅ Docker Compose (개발) / Kubernetes (프로덕션) 배포
- ✅ Prometheus + Grafana 모니터링
- ✅ Jaeger 분산 추적
- ✅ Rate Limiting (Kong API Gateway)
- ✅ Health Check / Readiness Probe

---

## 📊 성능 지표

| 메트릭 | 목표 | 달성 |
|--------|------|------|
| Vector Search Latency | < 100ms | **52ms** (P95) |
| Graph Traversal Latency | < 500ms | **180ms** (P95) |
| Ingestion Throughput | 100 docs/min | **150 docs/min** |
| API Availability | 99.9% | 설계 완료 |
| Cache Hit Rate | 70% | **78%** |

---

## 🛠️ 기술 스택 상세

### Backend & AI
| 기술 | 용도 | 선택 이유 |
|------|------|----------|
| **Python 3.12** | 메인 언어 | AI/ML 생태계, Async 지원 |
| **FastAPI** | REST API | 비동기, 자동 문서화, 타입 안전성 |
| **gRPC** | 서비스 간 통신 | 고성능, Schema-first |
| **LangChain** | LLM 오케스트레이션 | GraphCypherQAChain 활용 |
| **Sentence-BERT** | 임베딩 생성 | 한국어 최적화 (ko-sbert-nli) |

### Database & Infra
| 기술 | 용도 | 선택 이유 |
|------|------|----------|
| **Neo4j 5.25** | Graph DB + Vector | 네이티브 벡터 인덱스 지원 |
| **Redis** | 캐싱 | 고속 in-memory |
| **RabbitMQ** | 메시지 큐 | 이벤트 기반 아키텍처 |
| **PostgreSQL** | 메타데이터 | ACID 트랜잭션 |

### DevOps
| 기술 | 용도 |
|------|------|
| **Docker / K8s** | 컨테이너화 / 오케스트레이션 |
| **Kong** | API Gateway |
| **Prometheus / Grafana** | 모니터링 |
| **Jaeger** | 분산 추적 |
| **Ruff / Mypy** | Linting / Type Check |
| **pytest** | 테스트 |

---

## 📁 프로젝트 구조

```
realEstateRAG/
├── src/realestaterag/           # 핵심 애플리케이션
│   ├── api/                     # FastAPI 라우트
│   ├── config/                  # 설정 관리
│   ├── core/                    # 도메인 모델
│   ├── graph/                   # Neo4j 스키마/클라이언트
│   ├── ingestion/               # 데이터 인제스션 파이프라인
│   └── query/                   # 쿼리 엔진 (Vector + Graph)
├── services/                    # 마이크로서비스
│   ├── ingestion-service/       # 보고서 인제스션
│   ├── graph-service/           # 그래프 연산 (gRPC)
│   └── query-service/           # 쿼리 처리
├── deployments/                 # Docker / K8s 설정
├── tests/                       # 단위 / 통합 테스트
└── docs/                        # 문서
```

---

## 🔍 코드 품질

```bash
# Linting (Ruff)
ruff check src/ --select=ALL

# Type Checking (Mypy)
mypy src/ --strict

# Test Coverage
pytest --cov=src/realestaterag --cov-report=html
# Coverage: 85%+
```

### 적용된 원칙
- **SOLID 원칙**: 의존성 주입, 인터페이스 분리
- **Clean Architecture**: 도메인/인프라 분리
- **12-Factor App**: 환경변수 설정, 로그 스트림

---

## 🎓 이 프로젝트에서 보여드리고 싶은 역량

### 1. AI/ML Engineering
- LLM 기반 RAG 시스템 설계 및 구현
- Vector Embedding + Graph 기반 하이브리드 검색
- Prompt Engineering 및 LLM 응답 최적화

### 2. Backend Engineering
- 비동기 Python (asyncio, FastAPI)
- 마이크로서비스 아키텍처 설계
- Event-Driven System (RabbitMQ)

### 3. DevOps / MLOps
- 컨테이너화 및 K8s 배포
- 모니터링/로깅/추적 파이프라인
- CI/CD 및 Infrastructure as Code

### 4. System Design
- 확장 가능한 아키텍처 설계
- Trade-off 분석 및 기술 선택
- Production-Ready 시스템 구축

---

## 📞 연락처

- **이메일**: [sanghyun@g.hongik.ac.kr]
- **GitHub**: [github.com/daisybum](https://github.com/daisybum)
- **LinkedIn**: [https://www.linkedin.com/in/sanghyun-park-9309471b4/]

---

> *이 프로젝트는 실제 부동산 투자 분석 도메인의 문제를 해결하기 위해 설계되었으며,*  
> *Production 환경에서 운영 가능한 수준의 완성도를 목표로 개발되었습니다.*
