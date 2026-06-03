# Guía del proyecto demo_agent_automation

Documento de ejemplo de la **base de conocimiento (KB)**. Deja aquí tus
documentos de referencia (`.md`, `.txt`, `.pdf`, `.csv`, `.ipynb`) y luego
indexa con `uv run python -m app.rag kb`.

## Puertos del sistema

- El **modelo** (llama.cpp) se sirve en el puerto **8081** (endpoint OpenAI-compatible).
- El **proxy LiteLLM** de la variante Agent SDK corre en el puerto **4000**.
- El **chatbot Chainlit** se publica en el puerto **8000**.
- La **API FastAPI** se publica en el puerto **8080**.

## Modelo

El modelo local es **Qwen2.5-7B-Instruct** en formato GGUF, cuantización Q4_K_M.
Se sirve con la bandera `--jinja`, imprescindible para habilitar el tool-calling.
Está fijado a la GPU RTX 5070.

## Decisiones de diseño

- Para un modelo local pequeño se eligió **LangGraph** sobre el Claude Agent SDK,
  porque habla el formato OpenAI nativo con llama.cpp y evita el proxy traductor.
- La seguridad es **solo lectura por defecto**: el agente está encajonado en la
  carpeta gestionada y no mueve ni borra archivos salvo que se habilite ALLOW_WRITES.

## RAG agéntico

Se añadió **Agentic RAG** con embeddings locales (sentence-transformers,
multilingüe) y vector store **Chroma**. El agente decide cuándo llamar a la
herramienta `retrieve`. Hay dos colecciones: `carpeta` (la carpeta gestionada)
y `kb` (esta base de conocimiento).
