# ARM64 (NVIDIA GB10) 환경 설정 가이드

## 개요
본 프로젝트는 **NVIDIA GB10 (Grace Blackwell)** 환경에서 최적화된 성능을 발휘하도록 설계되었습니다. GB10은 **ARM64** 아키텍처(Grace CPU)를 기반으로 하므로, 일반적인 x86_64(AMD64) 환경과는 다른 설정이 필요합니다.

## 주요 이슈 및 해결책

### 1. Docker 이미지 호환성 (`exec format error`)
x86_64용으로 빌드된 Docker 이미지를 실행하면 아키텍처 불일치로 인해 컨테이너가 즉시 종료됩니다.

**해결책:** **Native Build (소스 빌드)**
- `llama.cpp` 등 핵심 컴포넌트는 소스 코드에서 직접 빌드하여 ARM64 바이너리를 생성해야 합니다.
- Dockerfile을 수정하여 `git clone` 및 `cmake` 빌드 과정을 포함시킵니다.

### 2. CUDA 버전 및 베이스 이미지
GB10 환경의 CUDA 드라이버 버전과 호환되는 Docker 베이스 이미지를 사용해야 합니다.
- 추천: `nvidia/cuda:12.4.1-devel-ubuntu22.04` (ARM64 지원)

## Llama Server (llama.cpp) 설정

### Dockerfile 수정 (Multi-stage Build)
```dockerfile
# Builder Stage
FROM nvidia/cuda:12.4.1-devel-ubuntu22.04 AS builder
RUN apt-get update && apt-get install -y git cmake build-essential
WORKDIR /src
RUN git clone https://github.com/ggerganov/llama.cpp.git .
RUN mkdir build && cd build && \
    cmake .. -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=90;80 \
    && cmake --build . --target llama-server

# Runtime Stage
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04
COPY --from=builder /src/build/bin/llama-server /app/llama-server
ENTRYPOINT ["/app/llama-server"]
```

### Docker Compose 설정
`docker-compose.yml`에서 이미지 이름 대신 빌드 컨텍스트를 지정합니다.
```yaml
services:
  llama-server:
    build:
      context: .
      dockerfile: Dockerfile
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

## FalkorDB 설정
FalkorDB 공식 이미지는 ARM64를 지원하지 않을 수 있습니다. 만약 문제가 발생한다면 Redis Stack ARM64 이미지를 사용하거나 소스 빌드가 필요할 수 있습니다. (현재 테스트 중)

## Python 환경 (Miniconda)
Miniconda 설치 시 **Linux-aarch64** 버전을 다운로드해야 합니다.
- 파일명 예: `Miniconda3-latest-Linux-aarch64.sh`
- 가상환경 패키지들도 `aarch64` 또는 `noarch` 버전을 확인합니다.

---

> **Note:** GB10의 Grace CPU는 매우 강력한 72코어 ARM 프로세서입니다. Native Build를 통해 이 성능을 온전히 활용할 수 있습니다.
