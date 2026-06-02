"""Tests de la factory de modelo. No hacen llamadas de red (solo construyen)."""
import pytest

from app import config, llm


def test_local_backend_builds(monkeypatch):
    monkeypatch.setattr(config, "LLM_BACKEND", "local")
    assert llm.make_llm() is not None


def test_unknown_backend_raises(monkeypatch):
    monkeypatch.setattr(config, "LLM_BACKEND", "no-existe")
    with pytest.raises(ValueError):
        llm.make_llm()


def test_optional_backend_missing_dep_is_clear(monkeypatch):
    """Si langchain-ollama no esta instalado, make_llm debe fallar con un
    RuntimeError claro (con instrucciones), no con ModuleNotFoundError crudo."""
    try:
        import langchain_ollama  # noqa: F401

        pytest.skip("langchain-ollama instalado; el caso de error no aplica")
    except ImportError:
        pass
    monkeypatch.setattr(config, "LLM_BACKEND", "ollama")
    with pytest.raises(RuntimeError, match="ollama"):
        llm.make_llm()
