#!/usr/bin/env bash
# Detiene el contenedor del modelo.
docker rm -f demo-llm 2>/dev/null && echo "demo-llm detenido." || echo "demo-llm no estaba corriendo."
