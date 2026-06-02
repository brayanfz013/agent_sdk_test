#!/usr/bin/env bash
# Verifica que el endpoint del modelo responde.
set -euo pipefail
PORT="${PORT:-8081}"
echo "=== /health ==="
curl -s "http://localhost:${PORT}/health" && echo
echo "=== /v1/models ==="
curl -s "http://localhost:${PORT}/v1/models"
echo
