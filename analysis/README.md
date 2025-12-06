# Real Estate Analysis Pipeline

이 프로젝트는 **Qwen3-VL** 멀티모달 모델을 활용하여 부동산 임장 보고서를 분석하는 파이프라인입니다. 텍스트, 이미지, PDF, PPTX 등 다양한 형태의 자료를 통합하여 분석하고, 투자 인사이트를 도출합니다.

## 📂 1. 다중 파일 처리 방식 (Multi-modal Data Processing)

이 파이프라인의 핵심은 **`DataLoader`** 클래스를 통해 이종(Heterogeneous) 데이터들을 하나의 '보고서(Report)' 단위로 묶어서 처리하는 것입니다.

### 데이터 구조 (Directory Structure)
분석기는 `data_dir` 내의 **폴더명**을 `report_id`로 인식합니다. 각 폴더 안에는 해당 보고서와 관련된 모든 파일이 위치해야 합니다.

```
data_dir/
├── 3635564/              # Report ID
│   ├── 3635564.txt       # [필수] 보고서 텍스트 본문
│   ├── image_1.png       # [선택] 임장 사진, 차트, 지도 등
│   ├── image_2.png
│   ├── report.pdf        # [선택] PDF 원본 (DataLoader가 경로 로드)
│   └── presentation.pptx # [선택] 발표 자료 (DataLoader가 경로 로드)
└── 3635565/
    ├── ...
```

---

## 🏗️ 2. 코드 구조 (Code Structure)

```
analysis/
├── main_analysis.py     # Entry Point - 파이프라인 조율
├── config_loader.py     # 공유 설정 (싱글톤 패턴)
├── config.yaml          # 시스템 설정
├── secrets_manager.py   # 🆕 시크릿 관리 (AWS/GCP/dotenv)
├── data_loader.py       # 데이터 로드 (파일 시스템)
├── prompt_manager.py    # 호환성 래퍼
├── qwen_analyzer.py     # vLLM API 클라이언트
└── prompts/             # 엔터프라이즈 프롬프트 시스템
    ├── manager.py       # 통합 인터페이스
    ├── loaders.py       # YAML/JSON 직렬화
    ├── templates.py     # Few-shot, History 지원
    ├── registry.py      # 로컬 버전 관리
    ├── langsmith_hub.py # LangSmith 연동
    └── templates/       # YAML 프롬프트 파일 (v2.0)
        ├── base_system.yaml
        ├── fact_extraction.yaml
        ├── visual_verification.yaml
        ├── sentiment_analysis.yaml
        └── insight_generation.yaml
```

### 핵심 모듈

| 모듈 | 역할 |
|------|------|
| `main_analysis.py` | 전체 분석 파이프라인 조율 |
| `config_loader.py` | 환경변수 > YAML > 기본값 우선순위 설정 관리 |
| `secrets_manager.py` | 🆕 다중 백엔드 시크릿 관리 (AWS/GCP/dotenv) |
| `data_loader.py` | 파일 시스템에서 보고서 데이터 로드 |
| `qwen_analyzer.py` | vLLM API 통신 및 멀티모달 추론 |
| `prompts/` | 온톨로지 기반 프롬프트 관리 ([상세 문서](prompts/README.md)) |

---

## 🔐 3. 시크릿 관리 (Secrets Management)

`secrets_manager.py`는 다중 백엔드를 지원하는 엔터프라이즈급 시크릿 관리자입니다.

### 지원 백엔드

| 백엔드 | 설정 | 필요 패키지 |
|--------|------|------------|
| **환경변수** | 기본 (항상 최우선) | 없음 |
| **AWS Secrets Manager** | `SecretBackend.AWS` | `boto3` |
| **GCP Secret Manager** | `SecretBackend.GCP` | `google-cloud-secret-manager` |
| **로컬 .env** | `SecretBackend.DOTENV` | 없음 |

### 우선순위
```
1. 환경변수 (os.environ)
2. 설정된 백엔드 (AWS/GCP/dotenv)
3. 기본값
```

### 사용 예시
```python
from secrets_manager import get_secret, get_langsmith_config

# 개별 시크릿 조회
api_key = get_secret("LANGSMITH_API_KEY")

# LangSmith 전체 설정 (API 키 없으면 자동 비활성화)
config = get_langsmith_config()
```

---

## 🤖 4. 프롬프트 시스템 v2.0

온톨로지 기반의 부동산 투자 분석 프롬프트:

| 템플릿 | 역할 |
|--------|------|
| `base_system.yaml` | 온톨로지 스키마, 등급 기준, 계산 공식 |
| `fact_extraction.yaml` | JSON 구조화 엔티티 추출 |
| `visual_verification.yaml` | 차트/지도 멀티모달 분석 |
| `sentiment_analysis.yaml` | 시장 심리 분석 |
| `insight_generation.yaml` | 최종 투자 인사이트 |

### Wolbu 등급 체계

| Factor | S | A | B | C |
|--------|---|---|---|---|
| 직장 | >30만명 | >20만명 | >10만명 | <10만명 |
| 교통 | 강남 30분 | 강남 60분 | 도심 60분 | 열악 |
| 학군 | >95% | >90% | >85% | <85% |

---

## 🚀 5. 사용 방법 (Usage)

### 환경 설정
```bash
# .env.example 복사
cp .env.example .env

# API 키 설정 (LangSmith는 선택사항)
nano .env
```

### Docker 실행
```bash
cd docker/vllm-blackwell
docker compose up -d

# 분석 실행
docker exec vllm-qwen3-vl-30b python3 /workspace/app/realEstateAnalyzer/analysis/main_analysis.py --report_id 3189054
```

### 옵션 지정
```bash
# 특정 리포트 ID만 분석
python analysis/main_analysis.py --report_id 3635564

# 데이터 경로 변경
python analysis/main_analysis.py --data_dir /path/to/custom/data

# 최대 샘플 수 제한
python analysis/main_analysis.py --max_samples 5
```

---

## 🔄 6. 청킹 처리 (Chunked Image Processing)

대용량 이미지(15장 이상)를 처리하기 위한 청킹 전략입니다.

### 문제 상황

```
vLLM 모델 제한: MAX_MODEL_LEN = 32,768 토큰
이미지당 토큰: ~2,000 토큰
안전 이미지 수: ~12개 (여유 공간 포함)
실제 보고서: 60+ 이미지 발생
```

### 청킹 전략

```python
# 12개씩 청크로 분할
MAX_IMAGES_PER_CHUNK = 12

# 예: 64개 이미지 → 6개 청크
chunks = [
    images[0:12],   # Chunk 1
    images[12:24],  # Chunk 2
    images[24:36],  # Chunk 3
    images[36:48],  # Chunk 4
    images[48:60],  # Chunk 5
    images[60:64],  # Chunk 6 (4장)
]
```

### 병합 규칙 (Deep Merge)

| 데이터 타입 | 병합 전략 |
|------------|----------|
| **딕셔너리** | 재귀적 병합 |
| **리스트** | 중복 제거 후 연결 |
| **스칼라** | null이 아닌 마지막 값 |

#### 병합 예시

```json
// Chunk 1 결과
{
  "district": {"name": "인천시 연수구"},
  "complexes": [{"name": "송도자이", "price": 80000}]
}

// Chunk 2 결과
{
  "district": {"name": "인천시 연수구", "population": 350000},
  "complexes": [{"name": "송도푸르지오", "price": 75000}]
}

// 병합 결과
{
  "district": {"name": "인천시 연수구", "population": 350000},
  "complexes": [
    {"name": "송도자이", "price": 80000},
    {"name": "송도푸르지오", "price": 75000}
  ],
  "_chunk_info": {"total_chunks": 2, "merged": true}
}
```

### 인사이트 생성 시 스마트 요약

병합된 결과가 너무 크면 핵심 필드만 추출:

```python
MAX_CHARS = 6000  # ~2000 토큰

priority_keys = ["district", "grades", "properties", 
                 "investment_comment", "sentiment_score"]
```

### 성능 벤치마크

| 이미지 수 | 청크 수 | 처리 시간 |
|----------|--------|----------|
| 3개 | 1 | ~2분 |
| 12개 | 1 | ~4분 |
| 64개 | 6 | **~22분** |

---

## 📊 7. 출력 형식

분석 결과는 `analysis_results/{report_id}_analysis.json`에 저장됩니다:

```json
{
  "report_id": "3189054",
  "input_quality": {
    "confidence_score": 0.75,
    "text_length": 1500,
    "image_count": 64,
    "data_sources": ["full_text", "images_64"],
    "hallucination_warnings": []
  },
  "facts": { /* JSON 구조화 엔티티 */ },
  "verification": { /* 시각적 검증 결과 */ },
  "sentiment": { /* 시장 심리 분석 */ },
  "insight": "# 🏠️ **용인시 수지구** 지역 분석 보고서..."
}
```
