"""Configuracion del agente con Claude Agent SDK, apuntando al modelo LOCAL a
traves del proxy LiteLLM (que traduce Anthropic <-> OpenAI/llama.cpp).

Memoria / sesiones / compactacion de contexto: las gestiona el PROPIO SDK
(ClaudeSDKClient mantiene el hilo; el harness compacta solo). A diferencia de la
version LangGraph, aqui NO montamos checkpointer ni trim manual: viene de fabrica.
"""
import os

from claude_agent_sdk import ClaudeAgentOptions

from app import config
from agent_sdk_version.tools_sdk import FILE_SERVER, TOOL_NAMES

SYSTEM_PROMPT = f"""Administras la carpeta: {config.MANAGED_DIR}

Guia de herramientas:
- CONTAR archivos / ver tamanos / "el mas grande": usa folder_stats (exacto, no cuentes a mano).
- BUSCAR por nombre: search_files (subcadena 'visa' o glob '*.pdf').
- LEER texto: read_text_file. LISTAR carpeta: list_dir. ORGANIZAR: propose_organization (dry-run).

Responde en espanol, claro y conciso. Entorno de SOLO LECTURA: no se mueven ni borran archivos.
Aprovecha el historial de la conversacion para resolver referencias ("esos", "el anterior").
"""


def build_options() -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        model=os.getenv("SDK_MODEL", "claude-local"),
        system_prompt=SYSTEM_PROMPT,
        mcp_servers={"files": FILE_SERVER},
        allowed_tools=TOOL_NAMES,
        permission_mode="bypassPermissions",  # tools propias y de solo lectura
        setting_sources=[],  # NO cargar CLAUDE.md/settings del repo: prompt limpio para el modelo chico
        cwd=str(config.MANAGED_DIR),
        # El CLI 'claude' que lanza el SDK debe apuntar al proxy local, no a la nube:
        env={
            "ANTHROPIC_BASE_URL": os.getenv("ANTHROPIC_BASE_URL", "http://localhost:4000"),
            "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY", "sk-anything"),
            "CLAUDE_CODE_ATTRIBUTION_HEADER": "0",  # fix KV-cache del modelo local
        },
    )
