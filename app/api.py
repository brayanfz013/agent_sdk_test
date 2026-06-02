"""Endpoint de API (FastAPI) que expone el AGENTE para que otras apps lo consuman,
con MEMORIA por sesion via 'session_id'.

Uso:
    uv run uvicorn app.api:app --host 127.0.0.1 --port 8080
    curl -s localhost:8080/health
    curl -s -X POST localhost:8080/chat -H 'content-type: application/json' \\
         -d '{"message":"cuantos PDFs hay?", "session_id":"u1"}'

Nota: /chat NO tiene autenticacion. Sirvelo en 127.0.0.1 (default). Solo expon
en red (0.0.0.0) detras de un proxy con auth.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from fastapi import FastAPI  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from app import config  # noqa: E402
from app.agent import get_agent  # noqa: E402

app = FastAPI(title="Demo Agent Automation", version="1.1.0")
# Construido en import-time (sin red): elimina la race del lazy-init.
agent = get_agent()


class ChatIn(BaseModel):
    message: str
    session_id: str = "default"


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "managed_dir": str(config.MANAGED_DIR),
        "backend": config.LLM_BACKEND,
        "model": config.active_model(),
        "allow_writes": config.ALLOW_WRITES,
    }


@app.post("/chat")
async def chat(body: ChatIn) -> dict:
    cfg = {"configurable": {"thread_id": body.session_id}}
    result = await agent.ainvoke({"messages": [("user", body.message)]}, config=cfg)
    return {"answer": result["messages"][-1].content, "session_id": body.session_id}
