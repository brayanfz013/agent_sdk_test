"""El agente: un ReAct de LangGraph con el modelo (factory) + las tools de archivo.

Memoria / sesiones / compactador:
- checkpointer InMemorySaver  -> conserva el historial POR sesion (thread_id).
- pre_model_hook (_compact)   -> recorta a las ultimas N mensajes antes de
  llamar al modelo, sin romper la secuencia tool_call/tool_result y conservando
  el system. Es un compactador por ventana (simple pero correcto); para uno por
  tokens, cambiar token_counter por un tokenizador real.

El historial vive en memoria del proceso: persiste entre turnos de una misma
sesion mientras el proceso siga vivo. Para persistencia en disco, sustituir
InMemorySaver por SqliteSaver.
"""
from langchain_core.messages import SystemMessage, trim_messages
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent

from app import config
from app.llm import make_llm
from app.tools import ALL_TOOLS

_WRITES = "HABILITADAS" if config.ALLOW_WRITES else "DESHABILITADAS (solo lectura)"

SYSTEM_PROMPT = f"""Eres un asistente que administra esta carpeta: {config.MANAGED_DIR}

Guia de herramientas (elige bien):
- CONTAR archivos, ver tamanos o extensiones, o "el mas grande": usa folder_stats (da conteos y tamanos EXACTOS). No cuentes listas a mano.
- BUSCAR archivos por nombre: usa search_files (acepta subcadena 'visa' o glob '*.pdf').
- LEER el contenido de un archivo de texto: usa read_text_file.
- LISTAR una carpeta concreta: usa list_dir.
- ORGANIZAR: usa propose_organization (es un plan en dry-run, no ejecuta).

Reglas:
- Usa las herramientas SOLO cuando haga falta; para numeros exactos confia en folder_stats, nunca cuentes manualmente.
- No inventes nombres de archivo: si no estas seguro, comprueba con una herramienta.
- Aprovecha el historial para entender referencias como "ese archivo", "esos" o "el anterior".
- Responde en espanol, claro y conciso.
- Las escrituras (mover archivos) estan {_WRITES}.
"""


def _compact(state):
    """pre_model_hook: limita el contexto a las ultimas MAX_HISTORY_MESSAGES,
    empezando en un mensaje humano (para no dejar tool_results huerfanos) y
    conservando el system. No muta el historial guardado; solo lo que se envia
    al modelo."""
    trimmed = trim_messages(
        state["messages"],
        max_tokens=config.MAX_HISTORY_MESSAGES,
        token_counter=len,  # cuenta MENSAJES (1 c/u), no tokens reales
        strategy="last",
        start_on="human",
        include_system=False,  # el system lo anteponemos nosotros (abajo)
        allow_partial=False,
    )
    # El system prompt SIEMPRE va primero, en cada turno: el hook reemplaza lo
    # que se envia al modelo, asi que debemos incluirlo aqui (no via prompt=).
    return {"llm_input_messages": [SystemMessage(content=SYSTEM_PROMPT), *trimmed]}


def build_agent():
    """Construye el agente con memoria por sesion. Perezoso para no exigir el
    endpoint del modelo en import-time."""
    return create_react_agent(
        make_llm(),
        tools=ALL_TOOLS,
        checkpointer=InMemorySaver(),
        pre_model_hook=_compact,
    )


_AGENT = None


def get_agent():
    """Singleton del agente (comparte el checkpointer entre sesiones; cada
    sesion se aisla por thread_id)."""
    global _AGENT
    if _AGENT is None:
        _AGENT = build_agent()
    return _AGENT
