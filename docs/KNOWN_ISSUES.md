# Known Issues - Schema v2.0

## ✅ Resolved Issues

### 1. FalkorDB Cypher Query Compatibility (2025-12-07)
**Status:** **RESOLVED**
- **Issue:** FalkorDB Python client does not support Map parameter binding (e.g., `$properties`).
- **Resolution:** Refactored `graph_schema.py` and `ingester` to use Python string interpolation (`{key}`) instead of Cypher parameters.
- **Verification:** Successfully ingested nested graph data (Reasoning Chain) via `batch_ingest.py`.

### 2. LLM Server ARM64 Build (2025-12-07)
**Status:** **RESOLVED**
- **Issue:** Default `llama.cpp` Docker image incompatible with GB10 (Grace Hopper) ARM64.
- **Resolution:** Created multi-stage Dockerfile compiling `llama.cpp` from source with `CUDA_DOCKER_ARCH=all` and `GGML_CUDA_FORCE_MMQ=1`.
- **Verification:** Server running (`llama-qwen3-vl-30b`), validated via 200 OK responses on `/v1/chat/completions`.

### 3. GraphRAG Package Recognition
**Status:** **RESOLVED**
- **Resolution:** Added `__init__.py` to `graphrag/` and ensured `PYTHONPATH` includes project root.

---

## ⚠️ Current Issues & Limitations

### 1. Qwen3-VL Model Output Quality (Prompt Engineering)
**Status:** **Active**
- **Issue:** "Qwen3-VL-30B-A3B-Instruct-Q8_0" exhibits severe repetition (looping) on some prompts, generating 8k+ tokens of garbage text during `fact_extraction` or `insight_generation`.
- **Observation:** `1000_analysis.json` contained truncated repetitive text ("he-he-he...").
- **Next Steps:**
    - Adjust `temperature` and `repetition_penalty` in `config.yaml`.
    - Refine system prompts to be more explicit for VL models.
    - Validate with `Q4_K_M` quantization if `Q8_0` is too unstable.

## 테스트 현황

### ✅ 완료된 테스트
시작
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
