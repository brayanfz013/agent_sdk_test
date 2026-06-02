# demo_agent_automation

Demo de un **agente local que administra una carpeta** (por defecto el
**Downloads de Windows** visto desde WSL) usando un **modelo pequeño open-source
con tool-calling** servido en **Docker con GPU** (llama.cpp).

La misma tarea está implementada con **dos stacks** para compararlos:

| Versión | Dónde | Stack | Memoria de conversación |
|---|---|---|---|
| **LangGraph** (principal) | `app/` (raíz) | LangGraph `create_react_agent`, habla OpenAI nativo con llama.cpp | Manual: checkpointer + `thread_id` + compactador |
| **Claude Agent SDK** | [`agent_sdk_version/`](agent_sdk_version/README.md) | Agent SDK + proxy LiteLLM (traduce Anthropic↔OpenAI) | **De fábrica** (el SDK la gestiona) |

> Por qué dos: el modelo es pequeño, así que el formato de tool-calling importa.
> LangGraph habla **OpenAI nativo** con llama.cpp (sin traducción). El Agent SDK
> habla **Anthropic** y necesita un **proxy traductor** — ver
> [`agent_sdk_version/`](agent_sdk_version/README.md). Esta repo muestra ambos y
> el porqué del trade-off.

## Modelo

`Qwen2.5-7B-Instruct` (GGUF Q4_K_M, ~4.7GB) en `llama.cpp:server-cuda13`,
pineado a la GPU 0, con `--jinja` para tool-calling. Conmutable sin tocar código
vía `LLM_BACKEND`: `local` (llama.cpp) · `ollama` · `vertex_gemini`.

## Cómo se generó el modelo y el endpoint (Docker)

Esta es la pieza que alimenta a **las dos versiones**: un endpoint local
OpenAI-compatible servido por llama.cpp en Docker sobre GPU.

### 1. Qué modelo y por qué

- **`Qwen2.5-7B-Instruct`**, formato **GGUF**, cuantización **Q4_K_M** (~4.7 GB).
- Elegido por **tool-calling fiable** (lo que decide que un agente funcione) y
  porque a Q4 entra de sobra en una sola GPU de 12 GB dejando espacio para 32K
  de contexto. Repo HF: `bartowski/Qwen2.5-7B-Instruct-GGUF`.

### 2. Descarga del modelo

```bash
# scripts/download_model.sh
hf download bartowski/Qwen2.5-7B-Instruct-GGUF \
  Qwen2.5-7B-Instruct-Q4_K_M.gguf \
  --local-dir /home/bubuntu/models/qwen2.5-7b-instruct
```

### 3. Despliegue del endpoint con Docker (GPU)

Se reutiliza la imagen oficial de llama.cpp con CUDA (ya probada en este
hardware: RTX 5070 + RTX 3070). El contenedor expone un endpoint
**OpenAI-compatible** en `:8081/v1`.

```bash
# docker/01_serve_model.sh
docker run -d --rm \
  --name demo-llm \
  --gpus '"device=0"' \                 # pin a la RTX 5070 (12GB); un 7B cabe entero
  -p 8081:8081 \
  -v /home/bubuntu/models/qwen2.5-7b-instruct:/models \
  ghcr.io/ggml-org/llama.cpp:server-cuda13 \
  -m /models/Qwen2.5-7B-Instruct-Q4_K_M.gguf \
  --alias qwen2.5-7b-instruct \
  --jinja \                             # ← IMPRESCINDIBLE: habilita tool-calling
  --host 0.0.0.0 --port 8081 \
  -c 32768 \                            # contexto 32K
  -ngl 99 \                             # todas las capas a GPU
  --flash-attn on \
  -np 1
```

Qué hace cada flag clave:

| Flag | Para qué |
|---|---|
| `--gpus '"device=0"'` | Fija el modelo a la GPU 0 (RTX 5070). Un 7B Q4 cabe completo |
| `--jinja` | Activa el chat template con soporte de **tools**. Sin esto, el function-calling NO funciona |
| `-c 32768` | Ventana de contexto (suficiente para leer archivos + historial) |
| `-ngl 99` | Offload de todas las capas a GPU |

Verificar:

```bash
curl -s http://localhost:8081/health          # {"status":"ok"}
uv run python scripts/raw_toolcall_test.py     # confirma tool-calling formato OpenAI
```

### 4. Cómo lo consume la app

- **Versión LangGraph**: `app/llm.py` crea `ChatOpenAI(base_url="http://localhost:8081/v1", ...)`.
  Habla OpenAI **directo** con llama.cpp. Sin traducción.
- **Versión Agent SDK**: el SDK habla Anthropic, así que `agent_sdk_version/`
  levanta un **proxy LiteLLM** (`:4000`) que traduce Anthropic↔OpenAI hacia el
  mismo `:8081`. Ver [`agent_sdk_version/README.md`](agent_sdk_version/README.md).

> 📐 Diagrama visual de toda la arquitectura: [`docs/arquitectura.html`](docs/arquitectura.html) (ábrelo en el navegador).

## Arquitectura — versión LangGraph (3 fases)

```
FASE 1  Modelo en Docker      llama.cpp + Qwen2.5-7B  --jinja  ->  OpenAI-compatible :8081/v1
           │
FASE 2  Agente LangGraph      create_react_agent + tools de archivo (sandbox, read-only)
        app/agent.py          + MEMORIA por sesión (checkpointer + thread_id + compactador)
           │
FASE 3  Caras de consumo      Chainlit (chatbot)   ·   FastAPI (API :8080)
```

## Memoria / sesiones / compactación de contexto

- **Memoria por sesión**: `InMemorySaver` (checkpointer) + `thread_id`. El chatbot
  usa un `thread_id` por sesión; la API lo recibe en `session_id`; la CLI tiene
  modo interactivo.
- **Compactador de contexto**: `pre_model_hook` recorta a las últimas
  `MAX_HISTORY_MESSAGES` (default 24), empezando en un mensaje humano (sin dejar
  `tool_result` huérfanos) y conservando el system prompt. Es por ventana de
  mensajes; para uno por tokens, cambiar `token_counter`.
- Persistencia: en memoria del proceso. Para disco, sustituir `InMemorySaver` por
  `SqliteSaver`.

## Seguridad (importante: opera sobre tu Downloads real)

- Agente **encajonado** en `MANAGED_DIR` (`app/tools.py::_safe`): bloquea path
  traversal, rutas absolutas y **symlinks que escapan** (no filtra metadata de
  archivos externos).
- **Solo lectura por defecto** (`ALLOW_WRITES=false`): `move_file` no hace nada.
  Con escritura, **no sobrescribe** destinos existentes y maneja cross-filesystem.
- Las tools **nunca crashean**: degradan a un mensaje de error (contrato estable).
- API `/chat` **sin auth** → sírvela en `127.0.0.1` (default). No la expongas en
  `0.0.0.0` sin un proxy con auth.

## Puesta en marcha

```bash
cd /home/bubuntu/demo_agent_automation
cp .env.example .env            # ajusta MANAGED_DIR si tu usuario Windows difiere

uv sync                         # entorno + dependencias (gestor: uv)

# Fase 1 - modelo
bash scripts/download_model.sh  # si no está descargado
bash docker/01_serve_model.sh
bash docker/healthcheck.sh
uv run python scripts/raw_toolcall_test.py     # confirma tool-calling

# Fase 2 - agente
uv run python -m app.cli "cuantos PDFs hay y cual es el mas grande?"   # one-shot
uv run python -m app.cli                                               # interactivo (memoria)
uv run pytest -q                                                       # 12 tests

# Fase 3 - caras
uv run chainlit run app/chatbot.py -w                                  # chatbot  :8000
uv run uvicorn app.api:app --host 127.0.0.1 --port 8080                # API      :8080
curl -s -X POST localhost:8080/chat -H 'content-type: application/json' \
     -d '{"message":"propon como organizar la carpeta", "session_id":"u1"}'
```

## Conmutar de modelo (sin tocar código)

```bash
# en .env
LLM_BACKEND=ollama          # requiere:  uv sync --extra ollama   (+ OLLAMA_MODEL, OLLAMA_BASE_URL)
LLM_BACKEND=vertex_gemini   # requiere:  uv sync --extra vertex   (+ VERTEX_PROJECT)
```

`make_llm()` (`app/llm.py`) resuelve el backend; si falta su dependencia, falla
con un mensaje claro indicando qué instalar.

## Variante Claude Agent SDK

Ver [`agent_sdk_version/README.md`](agent_sdk_version/README.md): misma tarea con
el Agent SDK + proxy LiteLLM, memoria nativa del SDK, y una comparativa honesta.

## Estructura

```
app/            config · llm(factory) · tools(sandbox) · agent(memoria) · cli · chatbot · api
docker/         01_serve_model.sh · stop_model.sh · healthcheck.sh
scripts/        download_model.sh · raw_toolcall_test.py
tests/          test_tools.py · test_llm.py        (12 tests)
agent_sdk_version/   variante con Claude Agent SDK (+ su README)
README.md · pyproject.toml (uv) · uv.lock
```
