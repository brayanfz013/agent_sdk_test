#!/usr/bin/env bash
# Fase 1 - Sirve un modelo pequeno con tool-calling via llama.cpp en Docker.
# Reusa la imagen ya probada en esta maquina (server-cuda13) y la fija a la
# GPU 0 (RTX 5070, 12GB), que sobra para un 7B Q4. --jinja habilita tool calling.
set -euo pipefail

MODEL_DIR="/home/bubuntu/models/qwen2.5-7b-instruct"
MODEL_FILE="Qwen2.5-7B-Instruct-Q4_K_M.gguf"
PORT="${PORT:-8081}"

docker rm -f demo-llm 2>/dev/null || true

docker run -d --rm \
  --name demo-llm \
  --gpus '"device=0"' \
  -p "${PORT}:8081" \
  -v "${MODEL_DIR}:/models" \
  ghcr.io/ggml-org/llama.cpp:server-cuda13 \
  -m "/models/${MODEL_FILE}" \
  --alias qwen2.5-7b-instruct \
  --jinja \
  --host 0.0.0.0 --port 8081 \
  -c 32768 \
  -ngl 99 \
  --flash-attn on \
  -np 1

echo "Contenedor 'demo-llm' lanzado en puerto ${PORT}."
echo "Logs:   docker logs -f demo-llm"
echo "Health: curl -s http://localhost:${PORT}/health"
