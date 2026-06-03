"""Tools del Claude Agent SDK (in-process MCP).

REUSAN exactamente la logica de sandbox/seguridad de app/tools.py (misma fuente
de verdad: los fixes de symlink, read-only, degradacion sin crash aplican a las
dos versiones). Aqui solo se envuelven en el decorador del Agent SDK.

Nota: NO se expone move_file -> esta variante es de solo lectura.
"""
from claude_agent_sdk import create_sdk_mcp_server, tool

from app import tools as lt  # logica compartida y testeada


def _text(s: str) -> dict:
    return {"content": [{"type": "text", "text": s}]}


@tool("list_dir", "Lista archivos y carpetas de la carpeta gestionada. 'subpath' relativo (ej '.', 'sub').", {"subpath": str})
async def list_dir(args):
    return _text(lt.list_dir.invoke({"subpath": args.get("subpath", ".")}))


@tool("folder_stats", "Resumen: conteo de archivos, tamano total, por extension y los 10 mas grandes. USAR para contar o 'el mas grande'.", {})
async def folder_stats(args):
    return _text(lt.folder_stats.invoke({}))


@tool("search_files", "Busca archivos por nombre. Acepta subcadena ('visa') o patron glob ('*.pdf').", {"query": str})
async def search_files(args):
    return _text(lt.search_files.invoke({"query": args["query"]}))


@tool("read_text_file", "Lee un archivo de TEXTO (truncado). No usar con binarios/PDF/imagenes.", {"path": str})
async def read_text_file(args):
    return _text(lt.read_text_file.invoke({"path": args["path"]}))


@tool("propose_organization", "Propone (DRY-RUN) como organizar la carpeta por tipo. No mueve nada.", {})
async def propose_organization(args):
    return _text(lt.propose_organization.invoke({}))


@tool("retrieve", "Busqueda SEMANTICA en el CONTENIDO de los documentos indexados (RAG). Para preguntas sobre lo que DICEN los documentos. source: 'carpeta'|'kb'|'ambos'.", {"query": str, "source": str})
async def retrieve(args):
    return _text(lt.retrieve.invoke({"query": args["query"], "source": args.get("source", "ambos")}))


_TOOLS = [list_dir, folder_stats, search_files, read_text_file, propose_organization, retrieve]
_NAMES = ["list_dir", "folder_stats", "search_files", "read_text_file", "propose_organization", "retrieve"]

FILE_SERVER = create_sdk_mcp_server(name="files", version="1.0.0", tools=_TOOLS)

# El SDK referencia las tools como mcp__<server>__<tool>
TOOL_NAMES = [f"mcp__files__{n}" for n in _NAMES]
