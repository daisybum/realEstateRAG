# Known Issues - Schema v2.0

## 미해결 이슈

### 1. FalkorDB Cypher 쿼리 호환성 문제 ⚠️

**증상:**
- `$properties` 파라미터 전달 시 "Encountered unhandled type" 에러
- UNIQUE constraint 문법 오류 (`CREATE CONSTRAINT FOR` vs `CREATE CONSTRAINT ON`)

**영향:**
- Report, Indicator, InvestmentAnalysis 노드 생성 실패
- 데이터 적재 불가

**임시 해결책:**
- FalkorDB 버전 확인 필요 (현재: 사용 중인 버전 미확인)
- Cypher 쿼리를 문자열 보간 방식으로 변경 고려

**상세:**
```python
# 실패하는 쿼리
self.graph.query(
    "CREATE (r:Report $properties)",
    {"properties": {...}}  # ❌ Unhandled type error
)

# 대안
query = f"CREATE (r:Report {{report_id: '{id}', confidence: {score}}})"
self.graph.query(query)  # ✅ 작동 가능
```

---

### 2. LLM 서버 아키텍처 불일치 🐛

**증상:**
- `exec /app/llama-server: exec format error`
- Docker 이미지: linux/amd64
- 호스트: linux/arm64 (GB10)

**영향:**
- llama.cpp 서버 실행 불가
- 멀티모달 분석 (이미지 처리) 실패

**해결 방법:**
```bash
# Dockerfile에서 ARM64 빌드 설정 필요
FROM --platform=linux/arm64 ...

# 또는 qemu를 사용한 에뮬레이션 (성능 저하)
docker run --platform linux/amd64 ...
```

---

### 3. GraphRAG 패키지 인식 실패 ⚠️

**증상:**
```
WARNING - GraphRAG not available (falkordb package not installed)
```

**원인:**
- `main_analysis.py`에서 falkordb import 실패
- 실제로는 설치되어 있으나 conda 환경 인식 문제

**영향:**
- `--enable-graph` 옵션 무시됨
- 분석 후 그래프 자동 적재 안 됨

**임시 해결책:**
```bash
# 수동 적재
python test_v2_ingestion.py
```

---

## 테스트 현황

### ✅ 완료된 테스트
- [x] FalkorDB Docker 시작
- [x] Schema v2.0 클래스 정의
- [x] GraphIngesterV2 초기화
- [x] 분석 파이프라인 실행 (텍스트 기반)

### ❌ 실패한 테스트
- [ ] 멀티모달 분석 (이미지)
- [ ] v2.0 그래프로 실제 데이터 적재
- [ ] 추론 체인 E2E 검증

### 🔄 부분 성공
- [~] 모의 데이터 생성 (완료)
- [~] Cypher 쿼리 실행 (일부 실패)

---

## 다음 단계 (우선순위)

### P0 - 필수
1. **Cypher 쿼리 수정**
   - FalkorDB 공식 문서 참조
   - `$properties` 파라미터 방식 제거
   - 문자열 보간으로 전환

2. **LLM 서버 ARM64 빌드**
   - Dockerfile 수정
   - ARM64 이미지 재빌드
   - `--media-path` 옵션 검증

### P1 - 중요
3. **통합 테스트**
   - 전체 워크플로우 검증
   - 추론 체인 조회 확인
   - 성능 측정

### P2 - 개선
4. **에러 핸들링 강화**
   - 실패 시 롤백 로직
   - 상세 로깅
   - 검증 스크립트

---

## 참고 자료

- FalkorDB 공식 문서: https://docs.falkordb.com/
- llama.cpp 멀티모달 가이드: https://github.com/ggerganov/llama.cpp
- Qwen3-VL 모델 카드: https://huggingface.co/Qwen/Qwen3-VL-30B-A3B-Instruct
