# =================================================================================
# Dockerfile for llama.cpp Server (arm64/aarch64 + CUDA)
# =================================================================================
# Build from source for NVIDIA Blackwell/Grace support
# =================================================================================

# Build stage - use CUDA 12.8 for Blackwell support
FROM nvidia/cuda:12.8.0-devel-ubuntu22.04 AS builder

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    cmake \
    build-essential \
    ccache \
    libcurl4-openssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Clone llama.cpp
WORKDIR /build
RUN git clone --depth 1 https://github.com/ggml-org/llama.cpp.git

# Build with CUDA support
# Create symlink for libcuda.so to use stub during build
WORKDIR /build/llama.cpp
RUN ln -s /usr/local/cuda/lib64/stubs/libcuda.so /usr/lib/libcuda.so.1
RUN cmake -B build \
    -DGGML_CUDA=ON \
    -DLLAMA_CURL=ON \
    -DCMAKE_BUILD_TYPE=Release \
    && cmake --build build --config Release -j$(nproc) --target llama-server llama-cli

# Runtime stage
FROM nvidia/cuda:12.8.0-runtime-ubuntu22.04

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgomp1 \
    libcurl4 \
    && rm -rf /var/lib/apt/lists/*

# Copy binaries and libraries
COPY --from=builder /build/llama.cpp/build/bin/llama-server /app/llama-server
COPY --from=builder /build/llama.cpp/build/bin/llama-cli /app/llama-cli
COPY --from=builder /build/llama.cpp/build/bin/*.so* /app/

WORKDIR /app
ENV LD_LIBRARY_PATH=/app:${LD_LIBRARY_PATH}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5m --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default entrypoint
ENTRYPOINT ["/app/llama-server"]

EXPOSE 8000
