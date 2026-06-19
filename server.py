"""
MIT License

Copyright (c) 2024 Usama Khatab

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import os
import sys
import logging
import tempfile
import nbformat
from contextlib import closing
from functools import wraps
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell
from pathlib import Path
from typing import Dict, List, Optional, Any
from mcp.server.fastmcp import FastMCP, Context

# ---------------------------------------------------------------------------
# Logging — write to stderr so stdout stays clean for the MCP stdio transport
# ---------------------------------------------------------------------------
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(levelname)s [notebook-mcp] %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Workspace state
# ---------------------------------------------------------------------------

# Uninitialized default — tools will refuse to run until initialize_workspace()
# has been called explicitly.
WORKSPACE_DIR: str = os.getcwd()
WORKSPACE_INITIALIZED: bool = False

log.info("Default workspace directory (uninitialized): %s", WORKSPACE_DIR)

# Create an MCP server
mcp = FastMCP("Jupyter Notebook MCP")


# ---------------------------------------------------------------------------
# Phase 2.1 — @require_workspace decorator
# ---------------------------------------------------------------------------

def require_workspace(func):
    """Decorator that ensures the workspace has been initialized before a tool runs.

    Raises ValueError with a user-friendly message when the workspace has not
    yet been set via initialize_workspace().  Using a decorator rather than a
    per-tool guard call keeps the contract visible at the function signature and
    avoids re-indenting every tool body.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not WORKSPACE_INITIALIZED:
            raise ValueError(
                "ERROR: Workspace not initialized. Please call "
                "initialize_workspace() first with the FULL ABSOLUTE PATH "
                "to the directory where your notebook files are located."
            )
        return func(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Phase 1 — Path helpers (security)
# ---------------------------------------------------------------------------

def convert_unix_path(path: str) -> str:
    """Convert Unix-style Git-Bash paths (e.g. /d/Projects) to Windows paths.

    Only active on win32; a no-op on every other platform.
    """
    if sys.platform != "win32":
        return path

    import re
    # Match /d/... or /D/... style paths produced by Git-Bash / WSL on Windows
    match = re.match(r"^/([a-zA-Z])(/.*)?$", path)
    if match:
        drive_letter = match.group(1).upper()
        remainder = (match.group(2) or "").replace("/", "\\")
        return f"{drive_letter}:{remainder}"
    return path


def resolve_path(path: str) -> str:
    """Resolve *path* against WORKSPACE_DIR and enforce the workspace jail.

    Steps:
    1. Convert Git-Bash / Unix-style drive paths on Windows.
    2. If the path is relative, join it against WORKSPACE_DIR.
    3. Canonicalise with Path.resolve() so that ``../`` sequences and symlinks
       are fully expanded.
    4. Assert the result sits inside the canonical workspace root.

    Raises:
        PermissionError: if the resolved path escapes the workspace root.
    """
    # Phase 1.1: single definition that always calls convert_unix_path
    path = convert_unix_path(path)

    if os.path.isabs(path):
        candidate = Path(path).resolve()
    else:
        candidate = Path(WORKSPACE_DIR, path).resolve()

    # Phase 1.2: enforce workspace jail after initialization
    # Only active once initialize_workspace() has been called — before that,
    # initialize_workspace() validates the directory directly without going
    # through resolve_path.
    if WORKSPACE_INITIALIZED:
        workspace_root = Path(WORKSPACE_DIR).resolve()
        try:
            candidate.relative_to(workspace_root)
        except ValueError:
            raise PermissionError(
                f"Path '{path}' resolves to '{candidate}' which is outside "
                f"the workspace root '{workspace_root}'. "
                "Absolute paths and traversal sequences (../) that escape the "
                "workspace are not permitted. "
                "(Fixes issue #5 — CWE-22 Path Traversal.)"
            )

    return str(candidate)


# ---------------------------------------------------------------------------
# Notebook I/O helpers
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


def _write_notebook_atomic(nb: nbformat.NotebookNode, resolved_path: str) -> None:
    """Write *nb* to *resolved_path* atomically.

    Writes to a sibling temporary file first, then uses os.replace() for an
    atomic rename.  On POSIX this is guaranteed atomic; on Windows it is
    best-effort (os.replace replaces atomically on NTFS for same-volume moves).

    Phase 2.2: ensures a crash or exception during serialisation does not
    leave a partially-written .ipynb file on disk.
    """
    parent = os.path.dirname(resolved_path) or "."
    # NamedTemporaryFile used as a context manager — real resource management
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=parent,
        suffix=".tmp",
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp_path = tmp.name
        nbformat.write(nb, tmp)

    # Atomic replace: tmp_path is only promoted to the target once fully written
    os.replace(tmp_path, resolved_path)


def create_new_notebook(filepath: str, title: str = "New Notebook") -> nbformat.NotebookNode:
    """Create a new notebook at *filepath* and return the NotebookNode.

    Parent directories are created automatically.  The file is written
    atomically via a temporary file + os.replace() so a crash mid-write
    cannot leave a corrupt .ipynb on disk (Phase 2.2).
    """
    resolved_path = resolve_path(filepath)

    Path(resolved_path).parent.mkdir(parents=True, exist_ok=True)

    nb = new_notebook()
    nb.cells.append(new_markdown_cell(f"# {title}"))
    nb.cells.append(new_code_cell("# Your code here"))

    _write_notebook_atomic(nb, resolved_path)
    log.info("Created new notebook at: %s", resolved_path)
    return nb


# ---------------------------------------------------------------------------
# Output / cell conversion helpers  (Phase 4)
# ---------------------------------------------------------------------------

def process_cell_output(output: Any) -> Dict[str, Any]:
    """Convert a single cell output object to a serialisable dict.

    Handles all standard Jupyter MIME types:
    - stream (stdout / stderr)
    - execute_result / display_data  — text/plain, text/html, image/png,
                                        image/jpeg, image/svg+xml,
                                        application/json  (Phase 4.2)
    - error (ename / evalue / traceback)
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
                    # Large binary blobs — report size rather than dumping bytes
                    result["data"][mime] = f"[Base64 encoded image: {len(value)} bytes]"
                else:
                    # text/plain, text/html, text/latex, image/svg+xml,
                    # application/json, and any future MIME types
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

    # Unknown / future output type — preserve whatever is there
    return {"type": otype, "raw": str(output)}


def _cell_to_dict(cell: Any) -> Dict[str, Any]:
    """Convert a single NotebookNode cell to a serialisable dict.

    Phase 4.1: replaces the duplicated cell_to_dict / notebook_to_dict output
    loops with a single implementation that delegates to process_cell_output().
    """
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
    """Convert an entire NotebookNode to a serialisable dict.

    Phase 4.1: delegates per-cell conversion to _cell_to_dict() to avoid the
    previous duplication between notebook_to_dict and cell_to_dict.
    """
    return {
        "cells": [_cell_to_dict(cell) for cell in nb.cells],
        "metadata": dict(nb.metadata),
        "nbformat": nb.nbformat,
        "nbformat_minor": nb.nbformat_minor,
    }


# ---------------------------------------------------------------------------
# MCP Tool implementations
# ---------------------------------------------------------------------------

@mcp.tool()
def initialize_workspace(directory: str) -> str:
    """IMPORTANT: Call this first! Initialize the workspace directory for this session.

    This must be called before using any other tools to ensure notebooks are
    created in the correct location.  You must provide a FULL ABSOLUTE PATH to
    your project folder where notebooks should be stored.  Relative paths are
    rejected.

    Args:
        directory: The FULL ABSOLUTE PATH to set as the workspace (required).

    Returns:
        Confirmation message with list of any notebooks found.

    Raises:
        ValueError: If directory is not provided, doesn't exist, is not a
                    directory, or is a relative path.
    """
    global WORKSPACE_DIR, WORKSPACE_INITIALIZED

    if not directory or not directory.strip():
        raise ValueError(
            "ERROR: You must provide a directory path. Please provide the "
            "FULL ABSOLUTE PATH to your project directory where notebook "
            "files are located."
        )

    # Normalise Git-Bash / Unix-style drive paths on Windows
    directory = convert_unix_path(directory)

    # Phase 1.3: use os.path.isabs — the prior string comparison missed many
    # relative path forms ("notebooks", "sub/dir", ".\\foo", "..\\bar", etc.)
    if not os.path.isabs(directory):
        raise ValueError(
            "ERROR: Relative paths are not allowed. Please provide the "
            f"FULL ABSOLUTE PATH to your project directory (got: '{directory}')."
        )

    if not os.path.exists(directory):
        raise ValueError(f"ERROR: Directory does not exist: {directory}")

    if not os.path.isdir(directory):
        raise ValueError(f"ERROR: Not a directory: {directory}")

    WORKSPACE_DIR = directory
    WORKSPACE_INITIALIZED = True
    log.info("Workspace initialized at: %s", WORKSPACE_DIR)

    # Phase 2.3: wrap rglob in contextlib.closing to guarantee the underlying
    # OS directory handle is released even if an exception occurs mid-iteration.
    notebooks: List[str] = []
    with closing(Path(WORKSPACE_DIR).rglob("*.ipynb")) as it:
        for path in it:
            notebooks.append(os.path.relpath(path, WORKSPACE_DIR))

    if notebooks:
        notebook_list = "\n- " + "\n- ".join(notebooks)
        return f"Workspace initialized at: {WORKSPACE_DIR}\nNotebooks found:{notebook_list}"
    return f"Workspace initialized at: {WORKSPACE_DIR}\nNo notebooks found."


@mcp.tool()
@require_workspace
def list_notebooks(directory: str = ".") -> List[str]:
    """List all notebook files in the specified directory.

    Note: You must call initialize_workspace() first.
    """
    resolved_directory = resolve_path(directory)

    # Phase 2.3: closing() ensures the rglob generator's OS handle is cleaned up
    notebook_files: List[str] = []
    with closing(Path(resolved_directory).rglob("*.ipynb")) as it:
        for path in it:
            notebook_files.append(str(path))

    return notebook_files


@mcp.tool()
@require_workspace
def create_notebook(filepath: str, title: str = "New Notebook") -> str:
    """Create a new Jupyter notebook.

    Note: You must call initialize_workspace() first with your project directory.

    Args:
        filepath: Path where the notebook should be created.
        title:    Title for the notebook (used in the first markdown cell).

    Returns:
        Path to the created notebook.
    """
    resolved_path = resolve_path(filepath)

    if os.path.exists(resolved_path):
        return f"Notebook already exists at {resolved_path}"

    create_new_notebook(filepath, title)
    return f"Created notebook at {resolved_path}"


@mcp.tool()
@require_workspace
def read_notebook(filepath: str) -> Dict[str, Any]:
    """Read the contents of a notebook.

    Note: You must call initialize_workspace() first with your project directory.

    Args:
        filepath: Path to the notebook file.

    Returns:
        The notebook content as a dictionary.

    Raises:
        FileNotFoundError: if the notebook does not exist.
    """
    # Phase 3: removed the silent create-on-read side effect.
    # A read operation must never create files on disk.
    nb = get_notebook_content(filepath)
    return notebook_to_dict(nb)


@mcp.tool()
@require_workspace
def read_cell(filepath: str, cell_index: int) -> Dict[str, Any]:
    """Read a specific cell from a notebook.

    Note: You must call initialize_workspace() first with your project directory.

    Args:
        filepath:   Path to the notebook file.
        cell_index: Zero-based index of the cell to read.

    Returns:
        The cell content as a dictionary.

    Raises:
        FileNotFoundError: if the notebook does not exist.
        IndexError:        if cell_index is out of range.
    """
    # Phase 3: removed the silent create-on-read side effect.
    nb = get_notebook_content(filepath)

    if cell_index < 0 or cell_index >= len(nb.cells):
        raise IndexError(
            f"Cell index {cell_index} is out of range; "
            f"notebook has {len(nb.cells)} cell(s) "
            f"(valid indices: 0\u2013{len(nb.cells) - 1})."
        )

    return _cell_to_dict(nb.cells[cell_index])


@mcp.tool()
@require_workspace
def edit_cell(filepath: str, cell_index: int, content: str) -> str:
    """Edit a specific cell in a notebook.

    Note: You must call initialize_workspace() first with your project directory.

    Args:
        filepath:   Path to the notebook file.
        cell_index: Zero-based index of the cell to edit.
        content:    New source content for the cell.

    Returns:
        Confirmation message.

    Raises:
        FileNotFoundError: if the notebook does not exist.
        IndexError:        if cell_index is out of range.
    """
    # Phase 3: removed the silent create-on-read side effect.
    nb = get_notebook_content(filepath)

    if cell_index < 0 or cell_index >= len(nb.cells):
        raise IndexError(
            f"Cell index {cell_index} is out of range; "
            f"notebook has {len(nb.cells)} cell(s) "
            f"(valid indices: 0\u2013{len(nb.cells) - 1})."
        )

    nb.cells[cell_index]["source"] = content

    # Phase 2.2: atomic write — no partial file on crash
    resolved_path = resolve_path(filepath)
    try:
        _write_notebook_atomic(nb, resolved_path)
    except Exception as e:
        raise RuntimeError(f"Failed to update notebook: {e}") from e

    return f"Updated cell {cell_index} in {resolved_path}"


@mcp.tool()
@require_workspace
def read_notebook_outputs(filepath: str) -> List[Dict[str, Any]]:
    """Read all outputs from a notebook.

    Note: You must call initialize_workspace() first with your project directory.

    Args:
        filepath: Path to the notebook file.

    Returns:
        List of dicts, one per code cell that has outputs, each containing
        ``cell_index`` and ``outputs``.

    Raises:
        FileNotFoundError: if the notebook does not exist.
    """
    # Phase 3: removed the silent create-on-read side effect.
    nb = get_notebook_content(filepath)

    outputs = []
    for i, cell in enumerate(nb.cells):
        if cell.cell_type == "code" and hasattr(cell, "outputs") and cell.outputs:
            outputs.append({
                "cell_index": i,
                "outputs": [process_cell_output(o) for o in cell.outputs],
            })

    return outputs


@mcp.tool()
@require_workspace
def read_cell_output(filepath: str, cell_index: int) -> List[Dict[str, Any]]:
    """Read output from a specific cell.

    Note: You must call initialize_workspace() first with your project directory.

    Args:
        filepath:   Path to the notebook file.
        cell_index: Zero-based index of the cell.

    Returns:
        List of output dicts for the cell, or an empty list if the cell has
        no outputs or is not a code cell.

    Raises:
        FileNotFoundError: if the notebook does not exist.
        IndexError:        if cell_index is out of range.
    """
    # Phase 3: removed the silent create-on-read side effect.
    nb = get_notebook_content(filepath)

    if cell_index < 0 or cell_index >= len(nb.cells):
        raise IndexError(
            f"Cell index {cell_index} is out of range; "
            f"notebook has {len(nb.cells)} cell(s) "
            f"(valid indices: 0\u2013{len(nb.cells) - 1})."
        )

    cell = nb.cells[cell_index]
    if cell.cell_type != "code" or not hasattr(cell, "outputs") or not cell.outputs:
        return []

    return [process_cell_output(o) for o in cell.outputs]


@mcp.tool()
@require_workspace
def add_cell(
    filepath: str,
    content: str,
    cell_type: str = "code",
    index: Optional[int] = None,
) -> str:
    """Add a new cell to a notebook.

    Note: You must call initialize_workspace() first with your project directory.

    Args:
        filepath:  Path to the notebook file.
        content:   Source content for the new cell.
        cell_type: ``'code'`` or ``'markdown'``.
        index:     Position at which to insert the cell.  ``None`` appends.
                   Valid values are 0 through len(cells) inclusive.

    Returns:
        Confirmation message.

    Raises:
        FileNotFoundError: if the notebook does not exist.
        ValueError:        if cell_type is unrecognised.
        IndexError:        if index is out of range.
    """
    # Phase 3: removed the silent create-on-read side effect.
    nb = get_notebook_content(filepath)

    cell_type_lower = cell_type.lower()
    if cell_type_lower == "code":
        new_cell = new_code_cell(content)
    elif cell_type_lower == "markdown":
        new_cell = new_markdown_cell(content)
    else:
        raise ValueError(
            f"Invalid cell type '{cell_type}'. Must be 'code' or 'markdown'."
        )

    if index is None:
        nb.cells.append(new_cell)
        position = len(nb.cells) - 1
    else:
        # Valid insertion positions: 0 … len(cells) (append-after-last included)
        if index < 0 or index > len(nb.cells):
            raise IndexError(
                f"Cell index {index} is out of range; notebook has "
                f"{len(nb.cells)} cell(s) — valid insertion indices are "
                f"0 through {len(nb.cells)} inclusive."
            )
        nb.cells.insert(index, new_cell)
        position = index

    # Phase 2.2: atomic write
    resolved_path = resolve_path(filepath)
    try:
        _write_notebook_atomic(nb, resolved_path)
    except Exception as e:
        raise RuntimeError(f"Failed to update notebook: {e}") from e

    return f"Added {cell_type_lower} cell at position {position} in {resolved_path}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Start the MCP server."""
    log.info("Starting Notebook MCP Server...")
    log.info("Working directory: %s", os.getcwd())

    try:
        mcp.run()
    except AttributeError:
        # Fallback for older fastmcp builds that expose .start() or .serve()
        # instead of .run().  Log a warning so version mismatches are visible.
        log.warning(
            "mcp.run() not found — trying legacy entry points "
            "(mcp.start / mcp.serve). Consider upgrading fastmcp."
        )
        try:
            mcp.start()
        except AttributeError:
            try:
                mcp.serve()
            except Exception as e:
                log.error("Failed to start server: %s", e)
                sys.exit(1)
    except Exception as e:
        log.error("Error starting server: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
