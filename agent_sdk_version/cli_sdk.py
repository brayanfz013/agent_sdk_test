"""CLI del agente con Claude Agent SDK. La memoria de conversacion la mantiene
el propio SDK (ClaudeSDKClient), sin checkpointer manual.

One-shot:
    uv run python -m agent_sdk_version.cli_sdk "cuantos PDFs hay?"

Interactivo (memoria nativa del SDK):
    uv run python -m agent_sdk_version.cli_sdk
    > cuantos PDFs hay?
    > y de esos cual es el mas grande?

Requiere: llama.cpp en :8081 y el proxy LiteLLM en :4000 (bash agent_sdk_version/run_proxy.sh).
"""
import sys

import anyio
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)

from agent_sdk_version.sdk_agent import build_options


async def _show(client) -> None:
    async for msg in client.receive_response():
        if isinstance(msg, AssistantMessage):
            for b in msg.content:
                if isinstance(b, ToolUseBlock):
                    print(f"  [tool] {b.name}({b.input})", flush=True)
                elif isinstance(b, TextBlock):
                    print(b.text, flush=True)
        elif isinstance(msg, ResultMessage):
            break


async def main() -> None:
    args = sys.argv[1:]
    async with ClaudeSDKClient(options=build_options()) as client:
        if args:
            await client.query(" ".join(args))
            await _show(client)
            return
        print("Agent SDK interactivo (memoria nativa). Ctrl-D para salir.")
        while True:
            try:
                q = input("\n> ").strip()
            except EOFError:
                print()
                break
            if q:
                await client.query(q)
                await _show(client)


if __name__ == "__main__":
    anyio.run(main)
