"""Prueba de bajo nivel: confirma que el endpoint local hace tool-calling bien
(formato OpenAI), independiente de LangGraph. Si esto falla, el problema es el
modelo/--jinja, no el agente.

    uv run python scripts/raw_toolcall_test.py
"""
import json
import os

import httpx

BASE = os.getenv("LOCAL_BASE_URL", "http://localhost:8081/v1")

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Obtiene el clima de una ciudad",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    }
]


def main() -> None:
    r = httpx.post(
        f"{BASE}/chat/completions",
        json={
            "model": "qwen2.5-7b-instruct",
            "messages": [{"role": "user", "content": "Que clima hace en Medellin?"}],
            "tools": TOOLS,
            "tool_choice": "auto",
            "temperature": 0,
        },
        timeout=120,
    )
    r.raise_for_status()
    msg = r.json()["choices"][0]["message"]
    calls = msg.get("tool_calls")
    print("tool_calls:", json.dumps(calls, indent=2, ensure_ascii=False))
    assert calls, "El modelo NO emitio un tool_call -> revisar --jinja / modelo"
    assert calls[0]["function"]["name"] == "get_weather"
    print("\nOK: el endpoint emite tool-calls en formato OpenAI.")


if __name__ == "__main__":
    main()
