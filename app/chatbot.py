"""UI de chatbot (Chainlit) sobre el AGENTE (no el modelo crudo), con MEMORIA
por sesion (cada chat = un thread_id).

Uso:
    uv run chainlit run app/chatbot.py -w
"""
import pathlib
import sys
import uuid

# Asegura que el paquete `app` sea importable sin importar el cwd de chainlit
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import chainlit as cl  # noqa: E402

from app import config  # noqa: E402
from app.agent import get_agent  # noqa: E402


@cl.on_chat_start
async def start() -> None:
    cl.user_session.set("thread_id", str(uuid.uuid4()))
    await cl.Message(
        content=(
            f"Hola 👋 Administro tu carpeta **{config.MANAGED_DIR}** "
            f"(modelo: `{config.active_model()}`, modo: "
            f"{'lectura/escritura' if config.ALLOW_WRITES else 'solo lectura'}).\n\n"
            "Tengo memoria de esta conversación. Prueba: *¿cuántos PDFs hay?* "
            "y luego *¿y cuál de esos es el más grande?*"
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    agent = get_agent()
    cfg = {"configurable": {"thread_id": cl.user_session.get("thread_id")}}
    result = await agent.ainvoke({"messages": [("user", message.content)]}, config=cfg)
    await cl.Message(content=result["messages"][-1].content).send()
