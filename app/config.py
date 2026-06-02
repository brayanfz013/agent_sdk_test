"""Configuracion central, leida de variables de entorno (.env)."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Backend del modelo: "local" | "ollama" | "vertex_gemini"
LLM_BACKEND = os.getenv("LLM_BACKEND", "local")

# Endpoint local (llama.cpp OpenAI-compatible)
LOCAL_BASE_URL = os.getenv("LOCAL_BASE_URL", "http://localhost:8081/v1")
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "qwen2.5-7b-instruct")
LOCAL_API_KEY = os.getenv("LOCAL_API_KEY", "sk-no-key-required")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))

# Carpeta que administra el agente (Windows Downloads vista desde WSL)
MANAGED_DIR = Path(os.getenv("MANAGED_DIR", "/mnt/c/Users/bwindows/Downloads")).resolve()

# Seguridad: escrituras deshabilitadas por defecto (solo lectura)
ALLOW_WRITES = os.getenv("ALLOW_WRITES", "false").lower() in ("1", "true", "yes")

# Ollama (opcional) - ojo: el tag de Ollama difiere del nombre local
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Vertex (opcional)
VERTEX_PROJECT = os.getenv("VERTEX_PROJECT", "")
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")
VERTEX_MODEL = os.getenv("VERTEX_MODEL", "gemini-2.0-flash")

# Cuantos mensajes de historial conserva el agente por sesion (compactador simple)
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "24"))


def active_model() -> str:
    """Nombre del modelo realmente en uso segun el backend activo."""
    if LLM_BACKEND == "vertex_gemini":
        return VERTEX_MODEL
    if LLM_BACKEND == "ollama":
        return OLLAMA_MODEL
    return LOCAL_MODEL
