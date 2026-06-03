"""Herramientas de archivo que el agente puede usar sobre la carpeta gestionada.

Seguridad:
- _safe() encajona rutas EXPLICITAS dentro de MANAGED_DIR (bloquea traversal).
- Los recorridos (list/stats/search) ignoran symlinks que apunten FUERA del
  sandbox, para no filtrar nombre/tamano/existencia de archivos externos.
- Solo lectura por defecto: mover archivos requiere ALLOW_WRITES=true, no
  sobrescribe destinos y tolera cross-filesystem.
- Las tools nunca lanzan: degradan a un string de error (contrato estable
  para el agente).
"""
import fnmatch
import pathlib
import shutil
from collections import Counter

from langchain_core.tools import tool

from app import config

BASE: pathlib.Path = config.MANAGED_DIR


def _within_base(p: pathlib.Path) -> bool:
    """True si la ruta (resuelta, siguiendo symlinks) cae dentro de BASE."""
    try:
        full = p.resolve()
    except OSError:
        return False
    return full == BASE or BASE in full.parents


def _safe(rel: str) -> pathlib.Path:
    """Resuelve una ruta relativa dentro de BASE y bloquea cualquier escape.
    Lanza ValueError si escapa; las tools la capturan."""
    full = (BASE / rel).resolve()
    if full != BASE and BASE not in full.parents:
        raise ValueError(f"Ruta no permitida (fuera de la carpeta gestionada): {rel!r}")
    return full


def _human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def _base_ready() -> str | None:
    """Mensaje de error si BASE no es una carpeta usable, o None si esta OK."""
    if not BASE.exists():
        return f"La carpeta gestionada no existe: {BASE}"
    if not BASE.is_dir():
        return f"La ruta gestionada no es una carpeta: {BASE}"
    return None


def _size(f: pathlib.Path) -> int | None:
    try:
        return f.stat().st_size
    except OSError:
        return None


def _iter_files(root: pathlib.Path):
    """Archivos regulares dentro de root, SIN seguir symlinks que escapen del
    sandbox y tolerando entradas que desaparecen (TOCTOU) o sin permiso."""
    try:
        entries = root.rglob("*")
    except OSError:
        return
    for f in entries:
        try:
            if f.is_symlink() and not _within_base(f):
                continue
            if f.is_file():
                yield f
        except OSError:
            continue


@tool
def list_dir(subpath: str = ".") -> str:
    """Lista archivos y carpetas dentro de la carpeta gestionada. 'subpath' es relativo (ej. '.', '01_categoria')."""
    err = _base_ready()
    if err:
        return err
    try:
        p = _safe(subpath)
    except ValueError as e:
        return str(e)
    if not p.exists():
        return f"No existe: {subpath}"
    if not p.is_dir():
        return f"No es una carpeta: {subpath}"
    rows = []
    for e in sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
        try:
            if e.is_symlink() and not _within_base(e):
                continue  # no exponer metadata de symlinks que escapan
            kind = "DIR " if e.is_dir() else "FILE"
            sz = _size(e) if e.is_file() else None
            size = _human(sz) if sz is not None else ""
        except OSError:
            continue
        rows.append(f"{kind} {size:>9}  {e.name}")
    return "\n".join(rows[:200]) or "(vacio)"


@tool
def folder_stats() -> str:
    """Resumen de la carpeta gestionada: nº de archivos, tamano total, conteo por extension y los 10 archivos mas grandes."""
    err = _base_ready()
    if err:
        return err
    sizes: dict[pathlib.Path, int] = {}
    for f in _iter_files(BASE):
        s = _size(f)
        if s is not None:
            sizes[f] = s
    if not sizes:
        return "La carpeta no tiene archivos legibles."
    total = sum(sizes.values())
    by_ext = Counter((f.suffix.lower() or "(sin ext)") for f in sizes)
    biggest = sorted(sizes, key=lambda f: sizes[f], reverse=True)[:10]

    out = [
        f"Carpeta: {BASE}",
        f"Total archivos: {len(sizes)}",
        f"Tamano total: {_human(total)}",
        "",
        "Por extension (top 12):",
    ]
    for ext, n in by_ext.most_common(12):
        out.append(f"  {ext:<10} {n}")
    out.append("")
    out.append("Mas grandes:")
    for f in biggest:
        out.append(f"  {_human(sizes[f]):>9}  {f.relative_to(BASE)}")
    return "\n".join(out)


@tool
def search_files(query: str) -> str:
    """Busca archivos por NOMBRE en la carpeta gestionada y subcarpetas. Acepta subcadena (ej. 'visa') o patron glob (ej. '*.pdf', 'IMG_*'). Case-insensitive."""
    err = _base_ready()
    if err:
        return err
    q = query.strip().lower()
    is_glob = any(ch in q for ch in "*?[")
    hits = []
    for f in _iter_files(BASE):
        name = f.name.lower()
        if fnmatch.fnmatch(name, q) if is_glob else q in name:
            hits.append(str(f.relative_to(BASE)))
    if not hits:
        return f"0 coincidencias para {query!r}."
    header = f"{len(hits)} coincidencia(s) para {query!r}:"
    extra = "" if len(hits) <= 100 else f"\n... (+{len(hits) - 100} mas)"
    return header + "\n" + "\n".join(hits[:100]) + extra


@tool
def read_text_file(path: str, max_chars: int = 4000) -> str:
    """Lee un archivo de TEXTO (.txt .md .py .ipynb .csv .json .yaml ...), truncado a max_chars. No usar con binarios/PDF/imagenes."""
    try:
        p = _safe(path)
    except ValueError as e:
        return str(e)
    if not p.is_file():
        return f"No es un archivo: {path}"
    try:
        if p.stat().st_size > 5_000_000:
            return "Archivo demasiado grande para leer como texto (>5MB)."
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError as e:  # noqa: BLE001
        return f"No se pudo leer el archivo ({e})."
    return text[:max_chars] + ("\n...[truncado]" if len(text) > max_chars else "")


_GROUPS = {
    "Imagenes": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"},
    "PDFs": {".pdf"},
    "Notebooks": {".ipynb"},
    "Datos": {".csv", ".json", ".xlsx", ".xls", ".parquet", ".tsv"},
    "Comprimidos": {".zip", ".rar", ".7z", ".gz", ".tar"},
    "Documentos": {".doc", ".docx", ".txt", ".md", ".pptx"},
    "Codigo": {".py", ".js", ".ts", ".sh", ".sql"},
}


def _category(suffix: str) -> str:
    for cat, exts in _GROUPS.items():
        if suffix.lower() in exts:
            return cat
    return "Otros"


@tool
def propose_organization() -> str:
    """Propone como organizar la carpeta agrupando por tipo de archivo. DRY-RUN: solo describe el plan, NO mueve nada."""
    err = _base_ready()
    if err:
        return err
    try:
        entries = list(BASE.iterdir())
    except OSError as e:  # noqa: BLE001
        return f"No se pudo leer la carpeta ({e})."
    plan: dict[str, list[str]] = {}
    for f in entries:
        try:
            if f.is_symlink() and not _within_base(f):
                continue
            if f.is_file():
                plan.setdefault(_category(f.suffix), []).append(f.name)
        except OSError:
            continue
    if not plan:
        return "No hay archivos sueltos que organizar."
    out = ["PLAN propuesto (DRY-RUN, no se movio nada):"]
    for cat in sorted(plan):
        names = plan[cat]
        out.append(f"\n{cat}/  ({len(names)} archivos)")
        out += [f"  - {n}" for n in names[:6]]
        if len(names) > 6:
            out.append(f"  ... +{len(names) - 6} mas")
    out.append("\nPara ejecutar el plan necesitarias ALLOW_WRITES=true y usar move_file por archivo.")
    return "\n".join(out)


@tool
def move_file(src: str, dest_subdir: str) -> str:
    """Mueve un archivo a un subdirectorio DENTRO de la carpeta gestionada. Requiere ALLOW_WRITES=true; no sobrescribe destinos existentes."""
    if not config.ALLOW_WRITES:
        return (
            "Escrituras DESHABILITADAS (ALLOW_WRITES=false). No se movio nada. "
            "El agente esta en modo solo-lectura por seguridad."
        )
    try:
        s = _safe(src)
        d = _safe(dest_subdir)
    except ValueError as e:
        return str(e)
    if not s.is_file():
        return f"No es un archivo: {src}"
    try:
        d.mkdir(parents=True, exist_ok=True)
        target = d / s.name
        if not _within_base(target.parent):  # defensa TOCTOU post-mkdir
            return "Destino fuera de la carpeta gestionada."
        if target.exists():
            return f"Ya existe {dest_subdir}/{s.name}; no se sobrescribe."
        shutil.move(str(s), str(target))  # maneja cross-filesystem (copy+delete)
    except OSError as e:  # noqa: BLE001
        return f"No se pudo mover ({e})."
    return f"Movido: {src} -> {dest_subdir}/{s.name}"


@tool
def retrieve(query: str, source: str = "ambos") -> str:
    """Busca SEMANTICAMENTE en el CONTENIDO de los documentos indexados (RAG) y devuelve fragmentos con su fuente. Usar para preguntas sobre lo que DICEN los documentos (no para contar/listar archivos). 'source': 'carpeta' | 'kb' | 'ambos'."""
    src = source if source in ("carpeta", "kb", "ambos") else "ambos"
    try:
        from app import rag

        res = rag.search(query, k=4, source=src)
    except ModuleNotFoundError as e:
        return (
            f"RAG no instalado ({e.name}). Ejecuta: uv sync --extra rag  "
            "y luego indexa: uv run python -m app.rag"
        )
    except Exception as e:  # noqa: BLE001
        return f"No se pudo recuperar ({e})."
    if not res:
        return (
            "Sin contexto relevante en los documentos indexados. Reformula la "
            "consulta o indica que no hay informacion (no inventes)."
        )
    return res


ALL_TOOLS = [
    list_dir,
    folder_stats,
    search_files,
    read_text_file,
    propose_organization,
    move_file,
    retrieve,
]
