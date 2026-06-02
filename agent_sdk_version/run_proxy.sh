#!/usr/bin/env bash
# Inicia el proxy LiteLLM que traduce Anthropic (/v1/messages) <-> el llama.cpp
# local (OpenAI-compatible en :8081). El Claude Agent SDK apunta aqui.
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run litellm --config agent_sdk_version/litellm_config.yaml --port "${PORT:-4000}"
