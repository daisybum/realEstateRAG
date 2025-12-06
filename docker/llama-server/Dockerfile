# =================================================================================
# Dockerfile for llama.cpp Server (GGUF Multimodal)
# =================================================================================
# Supports: Qwen3-VL-30B-A3B-Instruct GGUF (q4_K_M quantization)
# Features: CUDA GPU acceleration, OpenAI-compatible API
# =================================================================================

FROM ghcr.io/ggml-org/llama.cpp:server-cuda-b5490

# Environment variables
ENV LLAMA_CUDA=1
ENV LLAMA_CURL=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5m --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default port
EXPOSE 8000
