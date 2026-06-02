"""Ejecuta el agente desde la terminal.

One-shot:
    uv run python -m app.cli "cuantos PDFs hay y cual es el mas grande?"

Interactivo (con memoria de sesion, para ver el historial en accion):
    uv run python -m app.cli
    > cuantos PDFs hay?
    > y de esos cual es el mas grande?     # entiende "esos" por el historial
"""
import sys

from app.agent import build_agent

THREAD = "cli-session"


def _run(agent, query: str, show_tools: bool) -> None:
    cfg = {"configurable": {"thread_id": THREAD}}
    result = agent.invoke({"messages": [("user", query)]}, config=cfg)
    if show_tools:
        for m in result["messages"]:
            for c in getattr(m, "tool_calls", None) or []:
                print(f"  [tool] {c['name']}({c.get('args', {})})", flush=True)
    print(result["messages"][-1].content)


def main() -> None:
    agent = build_agent()
    args = sys.argv[1:]
    if args:
        query = " ".join(args)
        print(f"\n>>> {query}\n", flush=True)
        _run(agent, query, show_tools=True)
        return

    print("Modo interactivo (memoria por sesion). Ctrl-D para salir.")
    while True:
        try:
            q = input("\n> ").strip()
        except EOFError:
            print()
            break
        if q:
            _run(agent, q, show_tools=False)


if __name__ == "__main__":
    main()
