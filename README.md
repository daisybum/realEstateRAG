# Real Estate RAG (부동산 임장 보고서 분석 및 RAG 시스템)

**Real Estate RAG**는 부동산 임장 보고서(텍스트, 이미지 등)를 멀티모달 LLM(Qwen3-VL)으로 심층 분석하고, 이를 지식 그래프(Knowledge Graph)로 구축하여 투자 인사이트를 도출하고 질의응답할 수 있는 시스템입니다.

## 🌟 주요 기능 (Key Features)

1.  **멀티모달 AI 분석 (Multimodal Analysis)**
    *   **Qwen3-VL-30B** 모델을 활용하여 텍스트뿐만 아니라 차트, 지도, 현장 사진 등 시각 정보를 통합 분석합니다.
    *   **분석 파이프라인**: 팩트 추출(Fact Extraction) → 시각적 검증(Visual Verification) → 감성 분석(Sentiment Analysis) → 최종 인사이트 생성(Insight Generation)

2.  **지식 그래프 구축 (GraphRAG)**
    *   **FalkorDB**(Redis 기반 Graph DB)를 사용하여 부동산 데이터를 온톨로지 기반으로 구조화합니다.
    *   **Entity**: 리포트, 지역(District), 아파트 단지(Complex), 지표(Indicator), 등급(Grade), 투자 분석(Analysis) 등
    *   **Relation**: `LOCATED_IN`, `HAS_GRADE`, `SUPPORTS`, `MENTIONS` 등 데이터 간의 연관 관계 표현

3.  **투자 인사이트 및 챗봇 (Insights & Chat Interface)**
    *   객관적인 데이터와 AI의 추론을 결합하여 저평가 여부, 투자 적합성 등을 판단합니다.
    *   **Streamlit 챗봇**을 통해 자연어로 복잡한 투자 질문(예: "전세가율 60% 이상인 저평가 단지는?")을 수행하고 근거를 확인할 수 있습니다.

## 📂 프로젝트 구조 (Project Structure)

```bash
.
├── analysis/               # 🏗️ 분석 파이프라인
│   ├── main_analysis.py    # 분석 메인 실행 파일
│   ├── data_loader.py      # 멀티모달 데이터 로더
│   ├── qwen_analyzer.py    # Qwen3-VL 모델 연동 (vLLM)
│   ├── prompt_manager.py   # 프롬프트 관리자
│   └── config.yaml         # 분석 설정 파일
├── graphrag/               # 🕸️ GraphRAG 모듈
│   ├── graph_ingester.py   # FalkorDB 데이터 적재
│   ├── query_engine.py     # 자연어 → Cypher 변환 및 질의
│   └── graph_schema.py     # 온톨로지 스키마 정의
├── streamlit/              # 💬 웹 인터페이스
│   └── app.py              # 챗봇 UI 애플리케이션
├── scripts/                # 🛠️ 유틸리티
│   ├── ingest_existing_results.py # 기존 분석 결과 일괄 적재
│   └── generate_evaluation_reports.py # 평가 리포트 생성
└── docker/                 # 🐳 인프라 구성
    └── ...
```

## 🚀 시작하기 (Getting Started)

### 1. 필수 요구 사항 (Prerequisites)

*   **Python 3.12+**
*   **Docker & Docker Compose** (FalkorDB 및 vLLM 실행용)
*   **GPU** (Qwen3-VL-30B 로컬 구동 시 필요, API 모드 사용 시 불필요)

### 2. 설치 (Installation)

```bash
# 저장소 클론
git clone https://github.com/daisybum/realEstateRAG.git
cd realEstateRAG

# Python 패키지 설치
pip install -r requirements.txt
```

### 3. 환경 설정 (Configuration)

`analysis/config.yaml` 파일에서 주요 설정을 변경할 수 있습니다.

```yaml
system:
  data_dir: "/workspace/data"          # 임장 보고서 데이터 경로
  api_url: "http://localhost:8000/v1"  # vLLM API 엔드포인트
  model_name: "Qwen/Qwen3-VL-30B-A3B-Instruct"

falkordb:
  url: "redis://localhost:6379"        # FalkorDB 접속 주소
```

### 4. 실행 방법 (Usage)

#### 1) 분석 파이프라인 실행 (Analysis)

임장 보고서 데이터를 분석하여 JSON 결과를 생성합니다. 선택적으로 그래프 DB에 바로 적재할 수 있습니다.

```bash
# 단일 보고서 분석
python analysis/main_analysis.py --report_id <REPORT_ID>

# 전체 분석 및 그래프 적재 활성화
python analysis/main_analysis.py --enable-graph
```

#### 2) 기존 결과 그래프 적재 (Graph Ingestion)

이미 생성된 JSON 분석 결과가 있다면 배치를 통해 적재할 수 있습니다.

```bash
python scripts/ingest_existing_results.py
```

#### 3) 챗봇 인터페이스 실행 (Chatbot)

GraphRAG 기반의 대화형 인터페이스를 실행합니다.

```bash
streamlit run streamlit/app.py
```

브라우저에서 `http://localhost:8501`로 접속하여 질문할 수 있습니다.

## 🛠️ 기술 스택 (Tech Stack)

*   **LLM**: Qwen3-VL-30B (Vision Language Model)
*   **Serving**: vLLM (High-throughput LLM Serving)
*   **Graph DB**: FalkorDB (Low-latency Graph Database)
*   **UI Framework**: Streamlit
*   **Tracing**: LangSmith (Optional)
