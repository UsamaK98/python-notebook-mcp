"""
Notebook file I/O helpers.

Handles reading, writing (atomic), and converting notebook objects to
JSON-serialisable dicts.
"""

import os
import tempfile
import logging
from pathlib import Path
from typing import Any, Dict, List

import nbformat
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

from notebook_mcp.security import resolve_path

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output processing
# ---------------------------------------------------------------------------

def process_cell_output(output: Any) -> Dict[str, Any]:
    """Convert a single cell output object to a JSON-serialisable dict.

    Handles all standard Jupyter MIME types:
    - stream (stdout / stderr)
    - execute_result / display_data with full MIME data
    - error (ename / evalue / traceback)

    Images (PNG/JPEG) are summarised as placeholder strings by default to
    avoid passing massive base64 blobs in regular tool responses. Use the
    visualization tools to get actual image data.
    """
    otype = output.output_type

    if otype == "stream":
        return {
            "type": "stream",
            "name": output.name,
            "text": output.text,
        }

    if otype in ("execute_result", "display_data"):
        result: Dict[str, Any] = {"type": otype, "data": {}}
        if otype == "execute_result":
            result["execution_count"] = output.execution_count

        if hasattr(output, "data"):
            for mime, value in output.data.items():
                if mime in ("image/png", "image/jpeg"):
                    result["data"][mime] = f"[Base64 encoded image: {len(value)} chars — use describe_visualization or get_visualization_image to access]"
                else:
                    result["data"][mime] = value

        if hasattr(output, "metadata"):
            result["metadata"] = dict(output.metadata)
        return result

    if otype == "error":
        return {
            "type": "error",
            "ename": output.ename,
            "evalue": output.evalue,
            "traceback": output.traceback,
        }

    return {"type": otype, "raw": str(output)}


def process_cell_output_with_images(output: Any) -> Dict[str, Any]:
    """Like process_cell_output but returns full base64 image data."""
    result = process_cell_output(output)
    if result.get("type") in ("execute_result", "display_data"):
        if hasattr(output, "data"):
            for mime in ("image/png", "image/jpeg"):
                if mime in output.data:
                    result["data"][mime] = output.data[mime]
    return result


def _cell_to_dict(cell: Any) -> Dict[str, Any]:
    """Convert a single NotebookNode cell to a serialisable dict."""
    cell_dict: Dict[str, Any] = {
        "cell_type": cell.cell_type,
        "source": cell.source,
        "metadata": dict(cell.metadata),
    }
    if cell.cell_type == "code":
        cell_dict["execution_count"] = cell.execution_count
        cell_dict["outputs"] = [
            process_cell_output(o)
            for o in (cell.outputs if hasattr(cell, "outputs") else [])
        ]
    return cell_dict


def notebook_to_dict(nb: nbformat.NotebookNode) -> Dict[str, Any]:
    """Convert an entire NotebookNode to a serialisable dict."""
    return {
        "cells": [_cell_to_dict(cell) for cell in nb.cells],
        "metadata": dict(nb.metadata),
        "nbformat": nb.nbformat,
        "nbformat_minor": nb.nbformat_minor,
    }


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

def get_notebook_content(filepath: str) -> nbformat.NotebookNode:
    """Read and return a notebook from *filepath*.

    Raises:
        FileNotFoundError: if the file does not exist.
    """
    resolved_path = resolve_path(filepath)
    if not os.path.exists(resolved_path):
        raise FileNotFoundError(f"Notebook file not found: {resolved_path}")
    with open(resolved_path, "r", encoding="utf-8") as f:
        nb = nbformat.read(f, as_version=4)
    return nb


def write_notebook_atomic(nb: nbformat.NotebookNode, resolved_path: str) -> None:
    """Write *nb* to *resolved_path* atomically via tmp + os.replace().

    Ensures a crash during serialisation does not leave a partial .ipynb.
    """
    parent = os.path.dirname(resolved_path) or "."
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=parent,
        suffix=".tmp",
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp_path = tmp.name
        try:
            nbformat.write(nb, tmp)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    try:
        os.replace(tmp_path, resolved_path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def create_new_notebook(filepath: str, title: str = "New Notebook") -> nbformat.NotebookNode:
    """Create a new notebook at *filepath* and return the NotebookNode."""
    resolved_path = resolve_path(filepath)
    Path(resolved_path).parent.mkdir(parents=True, exist_ok=True)
    nb = new_notebook()
    nb.cells.append(new_markdown_cell(f"# {title}"))
    nb.cells.append(new_code_cell("# Your code here"))
    write_notebook_atomic(nb, resolved_path)
    log.info("Created new notebook at: %s", resolved_path)
    return nb
