# Variante con Claude Agent SDK

Misma tarea que la versión LangGraph (administrar la carpeta de Descargas con un
LLM local de tool-calling), pero construida con el **Claude Agent SDK** en vez de
LangGraph.

## La diferencia clave: el "seam" de protocolo

El Claude Agent SDK habla el **formato Anthropic** (`/v1/messages`, bloques
`tool_use`). llama.cpp habla **formato OpenAI** (`/v1/chat/completions`,
`tool_calls`). **No se entienden directamente.** Por eso hace falta un traductor:

```
┌────────────────────┐   Anthropic    ┌──────────────┐   OpenAI      ┌──────────────┐
│ Claude Agent SDK   │  /v1/messages  │   LiteLLM    │ /v1/chat/...  │  llama.cpp   │
│ (spawnea claude CLI)│ ─────────────► │  proxy :4000 │ ────────────► │  :8081 (GPU) │
│  + tools MCP        │ ◄───────────── │ (traductor)  │ ◄──────────── │ Qwen2.5-7B   │
└────────────────────┘                └──────────────┘               └──────────────┘
        ▲
   ANTHROPIC_BASE_URL=http://localhost:4000
```

Ese proxy **es** el seam del que hablábamos: con LangGraph no hace falta (habla
OpenAI nativo); con el Agent SDK + modelo local, sí.

## Qué aporta el Agent SDK (y por qué esta variante existe)

- **Memoria / sesiones / compactación de contexto: de fábrica.** `ClaudeSDKClient`
  mantiene el hilo de conversación entre turnos y el harness compacta el contexto
  solo. En la versión LangGraph eso lo añadimos a mano (checkpointer + thread_id +
  trim). Aquí no hay que montar nada.
- Harness maduro: permisos, sub-agentes, hooks, MCP, etc.

## Componentes

| Archivo | Qué hace |
|---|---|
| `litellm_config.yaml` | Proxy: enruta cualquier modelo al llama.cpp local (`openai/...`) |
| `run_proxy.sh` | Arranca el proxy LiteLLM en `:4000` |
| `tools_sdk.py` | Tools MCP in-process. **Reusan la misma lógica de sandbox de `app/tools.py`** (una sola fuente de verdad). Solo lectura (sin `move_file`) |
| `sdk_agent.py` | `ClaudeAgentOptions`: modelo `claude-local`, system prompt, tools permitidas, `setting_sources=[]` (no carga CLAUDE.md), `env` apuntando al proxy |
| `cli_sdk.py` | CLI one-shot e interactiva (memoria nativa del SDK) |

## Puesta en marcha

```bash
cd /home/bubuntu/demo_agent_automation

# 0) deps de esta variante
uv sync --extra agent-sdk

# 1) el modelo local (igual que la otra versión)
bash docker/01_serve_model.sh        # llama.cpp :8081

# 2) el proxy traductor Anthropic<->OpenAI
bash agent_sdk_version/run_proxy.sh  # LiteLLM :4000   (dejar corriendo)

# 3) el agente
uv run python -m agent_sdk_version.cli_sdk "cuantos PDFs hay?"        # one-shot
uv run python -m agent_sdk_version.cli_sdk                            # interactivo (con memoria)
```

Requisitos extra vs LangGraph: el binario `claude` (Claude Code CLI) y `node`,
porque el SDK spawnea el CLI por debajo.

## Resultado real (probado en este hardware)

Funciona end-to-end con el modelo local:

```
T1  "Cuantos archivos PDF hay?"      -> [tool] mcp__files__search_files  -> "Hay 45 archivos PDF..."
T2  "Y de ESOS, cual es el mas grande?" -> [tool] mcp__files__folder_stats -> "...textile directory.pdf, 170MB"
```

El T2 resuelve "esos" por la **memoria nativa** del SDK (no montamos checkpointer).

## Comparativa honesta vs LangGraph (misma tarea, mismo modelo)

| Eje | LangGraph | Agent SDK |
|---|---|---|
| Habla con llama.cpp | **Directo** (OpenAI nativo) | **Necesita proxy** LiteLLM (seam de traducción) |
| Memoria/sesiones/compactación | Manual (checkpointer + thread_id + trim) | **De fábrica** |
| Dependencias extra | ninguna | `claude` CLI + `node` + proxy |
| Piezas en ejecución | 1 (llama.cpp) + tu app | 2 (llama.cpp + proxy) + CLI spawneado |
| Control del loop | total (tú defines el grafo) | el harness decide |
| Tools | LangChain `@tool` | MCP in-process (`@tool` del SDK) |

**Conclusión:** para un modelo local pequeño y un pipeline propio, LangGraph es
más directo (un seam menos). El Agent SDK gana cuando quieres su gestión de
sesión/contexto y su harness ya hechos, y aceptas el proxy de traducción.
Esta variante demuestra que **se puede**, y a la vez **por qué** la otra es más
simple para este caso.
