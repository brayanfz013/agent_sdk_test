"""Factory del modelo. Conmuta el backend con la env var LLM_BACKEND sin tocar
el resto del codigo. Si el backend opcional no tiene su dependencia instalada,
falla con un mensaje claro (no con un ModuleNotFoundError crudo)."""
from app import config


def make_llm():
    backend = config.LLM_BACKEND

    # llama.cpp / vLLM / LM Studio: cualquier endpoint OpenAI-compatible
    if backend == "local":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            base_url=config.LOCAL_BASE_URL,
            api_key=config.LOCAL_API_KEY,
            model=config.LOCAL_MODEL,
            temperature=config.LLM_TEMPERATURE,
        )

    if backend == "ollama":
        try:
            from langchain_ollama import ChatOllama
        except ImportError as e:
            raise RuntimeError(
                "Backend 'ollama' requiere langchain-ollama. Instala: uv sync --extra ollama"
            ) from e
        return ChatOllama(
            model=config.OLLAMA_MODEL,
            base_url=config.OLLAMA_BASE_URL,
            temperature=config.LLM_TEMPERATURE,
        )

    if backend == "vertex_gemini":
        try:
            from langchain_google_vertexai import ChatVertexAI
        except ImportError as e:
            raise RuntimeError(
                "Backend 'vertex_gemini' requiere langchain-google-vertexai. "
                "Instala: uv sync --extra vertex"
            ) from e
        return ChatVertexAI(
            model=config.VERTEX_MODEL,
            project=config.VERTEX_PROJECT,
            location=config.VERTEX_LOCATION,
            temperature=config.LLM_TEMPERATURE,
        )

    raise ValueError(f"LLM_BACKEND desconocido: {backend!r}")
