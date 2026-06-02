#!/usr/bin/env bash
# Inicia el proxy LiteLLM que traduce Anthropic (/v1/messages) <-> el llama.cpp
# local (OpenAI-compatible en :8081). El Claude Agent SDK apunta aqui.
set -euo pipefail
cd "$(dirname "$0")/.."
# litellm corre AISLADO con uvx (su propio entorno, version parcheada), para no
# chocar con uvicorn de chainlit en el entorno del proyecto. Solo es el binario.
exec uvx --from 'litellm[proxy]>=1.83.11' litellm \
  --config agent_sdk_version/litellm_config.yaml --port "${PORT:-4000}"
