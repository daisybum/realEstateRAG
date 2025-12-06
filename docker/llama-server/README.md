# llama.cpp Server for Qwen3-VL-30B (GGUF q4_K_M)

## llama.cpp란?

[llama.cpp](https://github.com/ggerganov/llama.cpp)는 Meta의 LLaMA 모델을 순수 C/C++로 구현한 고성능 LLM 추론 엔진입니다.

### 주요 특징

| 특징 | 설명 |
|------|------|
| **GGUF 양자화** | 4-bit, 8-bit 등 다양한 양자화 지원으로 메모리 사용량 대폭 절감 |
| **크로스 플랫폼** | Linux, macOS, Windows 및 ARM/x86 아키텍처 지원 |
| **GPU 가속** | CUDA, Metal, Vulkan 등 다양한 GPU 백엔드 지원 |
| **OpenAI 호환 API** | `/v1/chat/completions`, `/v1/completions` 등 표준 API 제공 |
| **멀티모달 지원** | Vision 모델(mmproj) 통한 이미지 입력 처리 가능 |
| **낮은 의존성** | PyTorch 없이 독립 실행 가능 |

### 왜 llama.cpp를 사용하는가?

1. **메모리 효율성**: GGUF 양자화로 30B 모델을 ~17GB VRAM으로 실행 가능 (FP16 대비 ~70% 절감)
2. **빠른 시작**: Docker 이미지 기반으로 복잡한 의존성 설치 없이 즉시 실행
3. **API 호환성**: 기존 OpenAI API 클라이언트 코드 재사용 가능
4. **활발한 개발**: 최신 모델 지원 및 성능 최적화 지속 업데이트

## 개요

llama.cpp 기반 GGUF 양자화 모델 서빙 환경입니다.

- **모델**: Qwen3-VL-30B-A3B-Instruct (q4_K_M)
- **백엔드**: llama.cpp (OpenAI 호환 API)
- **메모리**: ~17-20GB GPU VRAM

## 빠른 시작

### 1. 모델 다운로드

```bash
mkdir -p models
huggingface-cli download unsloth/Qwen3-VL-30B-A3B-Instruct-GGUF \
  --include "*UD-Q8_K_XL*" "*mmproj*" \
  --local-dir ./models
```

### 2. 환경 설정

```bash
cp .env.example .env
# 필요시 .env 수정 (모델 파일명 확인)
```

### 3. 서버 실행

```bash
docker-compose up -d
docker-compose logs -f
```

### 4. 테스트

```bash
# 헬스체크
curl http://localhost:8000/health

# 텍스트 추론
curl http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello", "max_tokens": 50}'
```

## 디렉토리 구조

```
docker/llama-server/
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── README.md
└── models/           # 모델 파일 (gitignore)
    ├── Qwen3-VL-30B-A3B-Instruct-UD-Q8_K_XL.gguf
    └── mmproj-F16.gguf
```

## 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `MODEL_DIR` | `./models` | 모델 디렉토리 |
| `CTX_SIZE` | `32768` | 컨텍스트 크기 |
| `N_GPU_LAYERS` | `-1` | GPU 레이어 수 (-1=전체) |
| `THREADS` | `8` | CPU 스레드 수 |

## vLLM 대비 차이점

| 항목 | vLLM | llama.cpp |
|------|------|-----------|
| GPU 메모리 | ~60GB | ~17GB |
| 양자화 | FP16/BF16 | q4_K_M |
| API | OpenAI 호환 | OpenAI 호환 |

## 문제 해결

### 모델 파일명 확인
```bash
ls -la models/
# .env의 MODEL_FILENAME, MMPROJ_FILENAME과 일치해야 함
```

### GPU 메모리 부족
```bash
# .env에서 N_GPU_LAYERS 줄이기
N_GPU_LAYERS=40
```
