"""RAG agentico (Agentic RAG): ingesta -> embeddings locales -> Chroma -> search.

Dos colecciones:
  - "carpeta": contenido de MANAGED_DIR (la carpeta que administra el agente)
  - "kb":      contenido de KB_DIR (base de conocimiento aparte)

Embeddings: sentence-transformers multilingue (local, GPU si hay). Vector store:
Chroma persistente (embeddings PRECOMPUTADOS, no usa el embedder por defecto de
Chroma). El agente decide cuando llamar a la tool retrieve (de ahi "agentico");
si el contexto no basta, el prompt le pide reformular o avisar (toque CRAG).

Indexar:
    uv run python -m app.rag            # ambas colecciones
    uv run python -m app.rag kb         # solo la KB
    uv run python -m app.rag carpeta    # solo la carpeta gestionada
"""
from __future__ import annotations

import json
import pathlib
import sys

from app import config

# Solo DOCUMENTOS (no codigo/binarios). El contenido se indexa por significado.
_DOC_EXT = {".pdf", ".txt", ".md", ".markdown", ".csv", ".tsv", ".ipynb"}
_SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "dist", "build", ".rag_db"}

_COLLECTIONS = {"carpeta": config.MANAGED_DIR, "kb": config.KB_DIR}
# Chroma exige nombres de coleccion de 3-512 chars: mapeamos los logicos a fisicos
_COLNAME = {"carpeta": "rag_carpeta", "kb": "rag_kb"}

_embedder = None
_client = None


def _emb():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer

        _embedder = SentenceTransformer(config.EMBED_MODEL)
    return _embedder


def _client_():
    global _client
    if _client is None:
        import chromadb

        config.RAG_DB_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(config.RAG_DB_DIR))
    return _client


def _embed(texts: list[str]) -> list[list[float]]:
    return _emb().encode(texts, normalize_embeddings=True, show_progress_bar=False).tolist()


# ---------- ingesta ----------

def _read(path: pathlib.Path) -> list[tuple[int | None, str]]:
    """Devuelve [(pagina|None, texto)] del documento, o [] si no se puede leer."""
    suf = path.suffix.lower()
    if suf == ".pdf":
        try:
            from pypdf import PdfReader

            out = []
            for i, pg in enumerate(PdfReader(str(path)).pages):
                t = (pg.extract_text() or "").strip()
                if t:
                    out.append((i + 1, t))
            return out
        except Exception:  # noqa: BLE001
            return []
    if suf == ".ipynb":
        try:
            nb = json.loads(path.read_text("utf-8", "replace"))
            cells = ["".join(c.get("source", [])) for c in nb.get("cells", [])]
            txt = "\n\n".join(c for c in cells if c.strip())
            return [(None, txt)] if txt else []
        except Exception:  # noqa: BLE001
            return []
    try:
        txt = path.read_text("utf-8", "replace")
        return [(None, txt)] if txt.strip() else []
    except Exception:  # noqa: BLE001
        return []


def _chunk(text: str) -> list[str]:
    size, ov = config.RAG_CHUNK_CHARS, config.RAG_CHUNK_OVERLAP
    text = text.strip()
    if len(text) <= size:
        return [text] if text else []
    chunks, i = [], 0
    while i < len(text):
        chunks.append(text[i : i + size])
        i += max(1, size - ov)
    return chunks


def _iter_docs(folder: pathlib.Path):
    for p in folder.rglob("*"):
        if any(d in p.parts for d in _SKIP_DIRS):
            continue
        if not p.is_file() or p.suffix.lower() not in _DOC_EXT:
            continue
        try:
            if p.stat().st_size > config.RAG_MAX_FILE_MB * 1_000_000:
                continue
        except OSError:
            continue
        yield p


def index(source: str = "ambos") -> dict[str, str]:
    """(Re)indexa una o ambas colecciones. Recrea la coleccion para un index limpio."""
    targets = _COLLECTIONS if source == "ambos" else {source: _COLLECTIONS[source]}
    client = _client_()
    report: dict[str, str] = {}

    for name, folder in targets.items():
        if not folder.exists():
            report[name] = f"(no existe la carpeta: {folder})"
            continue
        try:
            client.delete_collection(_COLNAME[name])
        except Exception:  # noqa: BLE001
            pass
        col = client.create_collection(_COLNAME[name], metadata={"hnsw:space": "cosine"})

        ids: list[str] = []
        docs: list[str] = []
        metas: list[dict] = []
        for p in _iter_docs(folder):
            rel = str(p.relative_to(folder))
            for page, text in _read(p):
                for j, ch in enumerate(_chunk(text)):
                    ids.append(f"{rel}::{page}::{j}::{len(ids)}")
                    docs.append(ch)
                    metas.append({"source": rel, "page": page if page else -1})

        for s in range(0, len(docs), 64):  # embeddings por lotes
            col.add(
                ids=ids[s : s + 64],
                documents=docs[s : s + 64],
                embeddings=_embed(docs[s : s + 64]),
                metadatas=metas[s : s + 64],
            )
        n_docs = len({m["source"] for m in metas})
        report[name] = f"{len(docs)} fragmentos de {n_docs} documentos"
    return report


# ---------- recuperacion ----------

def search(query: str, k: int = 4, source: str = "ambos") -> str | None:
    """Top-k fragmentos relevantes (cosine) con su fuente. None si no hay nada."""
    names = ["carpeta", "kb"] if source == "ambos" else [source]
    client = _client_()
    qvec = _embed([query])[0]
    rows = []
    for name in names:
        try:
            col = client.get_collection(_COLNAME[name])
        except Exception:  # noqa: BLE001
            continue
        n = col.count()
        if not n:
            continue
        res = col.query(query_embeddings=[qvec], n_results=min(k, n))
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        for doc, meta, dist in zip(docs, metas, dists):
            rows.append((dist, name, meta, doc))
    if not rows:
        return None
    rows.sort(key=lambda r: r[0])
    out = []
    for dist, name, meta, doc in rows[:k]:
        pg = meta.get("page", -1)
        loc = meta.get("source", "?") + (f" (p.{pg})" if isinstance(pg, int) and pg > 0 else "")
        out.append(f"[{name} · {loc} · sim={1 - dist:.2f}]\n{doc.strip()[:800]}")
    return "\n\n---\n\n".join(out)


def main() -> None:
    args = [a for a in sys.argv[1:] if a in ("carpeta", "kb", "ambos")]
    source = args[0] if args else "ambos"
    print(f"Indexando coleccion(es): {source} ...", flush=True)
    for name, info in index(source).items():
        print(f"  {name}: {info}")
    print(f"Vector store en {config.RAG_DB_DIR}")


if __name__ == "__main__":
    main()
