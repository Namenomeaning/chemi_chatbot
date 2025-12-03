#!/bin/bash
# Download models for Chemistry Chatbot

set -e

echo "Downloading models..."

# TTS Model (61 MB)
mkdir -p models/tts
if [ ! -f models/tts/en_US-lessac-medium.onnx ]; then
    echo "→ TTS model..."
    curl -L -o models/tts/en_US-lessac-medium.onnx \
        https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
    curl -L -o models/tts/en_US-lessac-medium.onnx.json \
        https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
    echo "✓ TTS model downloaded"
else
    echo "✓ TTS model exists"
fi

# Embedding Model (1.2 GB)
if [ ! -d models/embedding/qwen3-embedding-0.6b ]; then
    echo "→ Embedding model (1.2 GB, may take a few minutes)..."
    uv run python -c "from huggingface_hub import snapshot_download; snapshot_download('Qwen/Qwen3-Embedding-0.6B', local_dir='models/embedding/qwen3-embedding-0.6b')"
    echo "✓ Embedding model downloaded"
else
    echo "✓ Embedding model exists"
fi

echo "✓ All models ready"
