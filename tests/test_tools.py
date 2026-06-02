"""Tests de las herramientas y el sandbox. No requieren el LLM (corren sobre la
carpeta gestionada real, en solo lectura)."""
import pytest

from app import config, tools


def test_sandbox_blocks_parent_traversal():
    with pytest.raises(ValueError):
        tools._safe("../../etc/passwd")


def test_sandbox_blocks_absolute_escape():
    with pytest.raises(ValueError):
        tools._safe("/etc/passwd")


def test_sandbox_allows_base():
    assert tools._safe(".") == config.MANAGED_DIR


def test_folder_stats_runs():
    out = tools.folder_stats.invoke({})
    assert "Total archivos" in out


def test_list_dir_runs():
    out = tools.list_dir.invoke({"subpath": "."})
    assert isinstance(out, str) and len(out) > 0


def test_writes_disabled_by_default():
    # Con ALLOW_WRITES=false move_file no debe tocar nada.
    if not config.ALLOW_WRITES:
        out = tools.move_file.invoke({"src": "x.txt", "dest_subdir": "tmp"})
        assert "DESHABILITADAS" in out


def test_human_readable_sizes():
    assert tools._human(512) == "512B"
    assert tools._human(1536).endswith("KB")


def test_read_text_file_traversal_returns_message():
    # Una ruta de escape NO debe reventar la tool: devuelve un string de error.
    out = tools.read_text_file.invoke({"path": "../../etc/passwd"})
    assert isinstance(out, str)
    assert "no permitida" in out.lower() or "fuera" in out.lower()


def test_iter_files_skips_escaping_symlink(tmp_path, monkeypatch):
    # Sandbox temporal (NO toca el Downloads real) con un symlink que escapa.
    base = (tmp_path / "managed").resolve()
    base.mkdir()
    (base / "ok.txt").write_text("hola")
    outside = tmp_path / "secret.txt"
    outside.write_text("SECRETO")
    (base / "leak.txt").symlink_to(outside)

    monkeypatch.setattr(tools, "BASE", base)
    names = [f.name for f in tools._iter_files(base)]
    assert "ok.txt" in names
    assert "leak.txt" not in names  # symlink que apunta fuera: ignorado, no filtra metadata
