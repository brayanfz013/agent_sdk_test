#!/usr/bin/env bash
# Descarga el modelo pequeno con tool-calling (Qwen2.5-7B-Instruct, GGUF Q4_K_M, ~4.7GB).
set -euo pipefail
DEST="/home/bubuntu/models/qwen2.5-7b-instruct"
mkdir -p "${DEST}"
hf download bartowski/Qwen2.5-7B-Instruct-GGUF \
  Qwen2.5-7B-Instruct-Q4_K_M.gguf \
  --local-dir "${DEST}"
echo "Modelo en ${DEST}"
