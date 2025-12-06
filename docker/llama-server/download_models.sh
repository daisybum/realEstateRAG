#!/bin/bash

# =================================================================================
# Model Download Script for RealEstateRAG (Llama.cpp / Qwen3-VL)
# =================================================================================

# Set strict error handling
set -e

# Configuration
REPO_ID="Qwen/Qwen3-VL-30B-A3B-Instruct-GGUF"
MODEL_FILE="Qwen3VL-30B-A3B-Instruct-Q8_0.gguf"
MMPROJ_FILE="mmproj-Qwen3VL-30B-A3B-Instruct-F16.gguf"

# Determine paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MODELS_DIR="$PROJECT_ROOT/models"

echo "========================================================================="
echo " 📥 RealEstateRAG Model Downloader"
echo "========================================================================="
echo " • Repository:  $REPO_ID"
echo " • Model File:  $MODEL_FILE"
echo " • Projector:   $MMPROJ_FILE"
echo " • Destination: $MODELS_DIR"
echo "========================================================================="

# Check requirements
if ! command -v huggingface-cli &> /dev/null; then
    echo "❌ Error: 'huggingface-cli' is not installed."
    echo "💡 Please install it via: pip install huggingface_hub"
    exit 1
fi

# Create directory
mkdir -p "$MODELS_DIR"

# Download Projector (MMProj)
echo ""
echo "⬇️  Downloading Multimodal Projector (mmproj)..."
if [ -f "$MODELS_DIR/$MMPROJ_FILE" ]; then
    echo "✅ File already exists: $MMPROJ_FILE"
else
    huggingface-cli download "$REPO_ID" "$MMPROJ_FILE" \
        --local-dir "$MODELS_DIR" \
        --local-dir-use-symlinks False
    echo "✅ Download complete: $MMPROJ_FILE"
fi

# Download Model (GGUF)
echo ""
echo "⬇️  Downloading Main Model (Q8_0 GGUF)..."
echo "⚠️  This is a large file (~33GB). Please be patient."

if [ -f "$MODELS_DIR/$MODEL_FILE" ]; then
    echo "✅ File already exists: $MODEL_FILE"
else
    huggingface-cli download "$REPO_ID" "$MODEL_FILE" \
        --local-dir "$MODELS_DIR" \
        --local-dir-use-symlinks False
    echo "✅ Download complete: $MODEL_FILE"
fi

echo ""
echo "========================================================================="
echo "🎉 All files are ready!"
echo "👉 You can now start the server with:"
echo "   docker compose -f docker/llama-server/docker-compose.yml up -d"
echo "========================================================================="
