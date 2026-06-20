"""
Notebook search, outline, info, validation, and export utilities.
"""

import ast
import logging
import os
import re
from typing import Any, Dict, List, Optional

import nbformat

from notebook_mcp.security import resolve_path
from notebook_mcp.core.notebook_io import get_notebook_content

log = logging.getLogger(__name__)


def notebook_search(
    filepath: str,
    query: str,
    case_sensitive: bool = False,
    context_lines: int = 2,
) -> List[Dict[str, Any]]:
    """Search all cells for *query*, returning matches with context snippets.

    Args:
        filepath:       Path to the notebook.
        query:          Search string (plain text, not regex).
        case_sensitive: Whether the search is case-sensitive.
        context_lines:  How many surrounding lines to include in snippets.

    Returns:
        List of match dicts with keys: cell_index, cell_type, line_number,
        snippet, match_count.
    """
    nb = get_notebook_content(filepath)
    results = []
    flags = 0 if case_sensitive else re.IGNORECASE
    pattern = re.compile(re.escape(query), flags)

    for idx, cell in enumerate(nb.cells):
        lines = cell.source.splitlines()
        cell_matches = []
        for lineno, line in enumerate(lines):
            if pattern.search(line):
                start = max(0, lineno - context_lines)
                end = min(len(lines), lineno + context_lines + 1)
                snippet_lines = []
                for i, sl in enumerate(lines[start:end], start=start):
                    marker = ">>>" if i == lineno else "   "
                    snippet_lines.append(f"{marker} {i+1:3d}: {sl}")
                cell_matches.append({
                    "line_number": lineno + 1,
                    "snippet": "\n".join(snippet_lines),
                })

        if cell_matches:
            results.append({
                "cell_index": idx,
                "cell_type": cell.cell_type,
                "match_count": len(cell_matches),
                "matches": cell_matches,
            })

    return results


def notebook_outline(filepath: str) -> List[Dict[str, Any]]:
    """Generate a structural outline of the notebook.

    For markdown cells: extracts headings (# H1, ## H2, etc.).
    For code cells: extracts top-level function/class definitions.

    Returns:
        List of dicts with: cell_index, cell_type, kind, name, line_number,
        line_count.
    """
    nb = get_notebook_content(filepath)
    outline = []

    for idx, cell in enumerate(nb.cells):
        lines = cell.source.splitlines()
        line_count = len(lines)

        if cell.cell_type == "markdown":
            for lineno, line in enumerate(lines):
                m = re.match(r"^(#{1,6})\s+(.*)", line)
                if m:
                    outline.append({
                        "cell_index": idx,
                        "cell_type": "markdown",
                        "kind": f"h{len(m.group(1))}",
                        "name": m.group(2).strip(),
                        "line_number": lineno + 1,
                        "line_count": line_count,
                    })

        elif cell.cell_type == "code":
            # Try AST parsing for accurate function/class extraction
            try:
                tree = ast.parse(cell.source)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        kind = "class" if isinstance(node, ast.ClassDef) else "function"
                        outline.append({
                            "cell_index": idx,
                            "cell_type": "code",
                            "kind": kind,
                            "name": node.name,
                            "line_number": node.lineno,
                            "line_count": line_count,
                        })
            except SyntaxError:
                # Fall back to regex for cells with syntax errors or magics
                for lineno, line in enumerate(lines):
                    m = re.match(r"^(def|async def|class)\s+(\w+)", line)
                    if m:
                        outline.append({
                            "cell_index": idx,
                            "cell_type": "code",
                            "kind": "class" if m.group(1) == "class" else "function",
                            "name": m.group(2),
                            "line_number": lineno + 1,
                            "line_count": line_count,
                        })

    return outline


def notebook_info(filepath: str) -> Dict[str, Any]:
    """Return general information about the notebook.

    Returns:
        Dict with: cell_count, code_cells, markdown_cells, raw_cells,
        cells_with_output, total_output_count, kernel_name, language,
        nbformat_version, has_errors, file_size_bytes.
    """
    nb = get_notebook_content(filepath)
    resolved_path = resolve_path(filepath)

    code_cells = sum(1 for c in nb.cells if c.cell_type == "code")
    markdown_cells = sum(1 for c in nb.cells if c.cell_type == "markdown")
    raw_cells = sum(1 for c in nb.cells if c.cell_type == "raw")

    cells_with_output = 0
    total_outputs = 0
    has_errors = False
    for cell in nb.cells:
        if cell.cell_type == "code" and hasattr(cell, "outputs") and cell.outputs:
            cells_with_output += 1
            total_outputs += len(cell.outputs)
            for out in cell.outputs:
                if out.output_type == "error":
                    has_errors = True

    kernel_name = nb.metadata.get("kernelspec", {}).get("name", "unknown")
    language = nb.metadata.get("kernelspec", {}).get("language", "unknown")

    file_size = os.path.getsize(resolved_path) if os.path.exists(resolved_path) else 0

    return {
        "cell_count": len(nb.cells),
        "code_cells": code_cells,
        "markdown_cells": markdown_cells,
        "raw_cells": raw_cells,
        "cells_with_output": cells_with_output,
        "total_output_count": total_outputs,
        "has_errors": has_errors,
        "kernel_name": kernel_name,
        "language": language,
        "nbformat_version": f"{nb.nbformat}.{nb.nbformat_minor}",
        "file_size_bytes": file_size,
        "filepath": resolved_path,
    }


def notebook_validate(filepath: str) -> Dict[str, Any]:
    """Validate the notebook structure against the nbformat schema.

    Returns:
        Dict with: valid (bool), errors (list of strings).
    """
    nb = get_notebook_content(filepath)
    errors = []
    try:
        nbformat.validate(nb)
        valid = True
    except nbformat.ValidationError as e:
        valid = False
        errors.append(str(e))
    except Exception as e:
        valid = False
        errors.append(f"Unexpected validation error: {e}")

    return {"valid": valid, "errors": errors, "error_count": len(errors)}


def notebook_export(filepath: str, export_format: str = "python") -> Dict[str, Any]:
    """Export the notebook to another format using nbconvert.

    Args:
        filepath:      Path to the notebook.
        export_format: Target format: 'python', 'html', 'markdown', 'rst',
                       'latex', 'slides'. Defaults to 'python'.

    Returns:
        Dict with: output_path, format, success, message.
    """
    try:
        import nbconvert
        from nbconvert import get_exporter
    except ImportError:
        return {
            "success": False,
            "message": "nbconvert is not installed. Run: pip install nbconvert",
            "output_path": None,
            "format": export_format,
        }

    resolved_path = resolve_path(filepath)
    nb = get_notebook_content(filepath)

    format_map = {
        "python": ("script", ".py"),
        "html": ("html", ".html"),
        "markdown": ("markdown", ".md"),
        "rst": ("rst", ".rst"),
        "latex": ("latex", ".tex"),
        "slides": ("slides", ".html"),
    }

    if export_format not in format_map:
        return {
            "success": False,
            "message": f"Unknown format '{export_format}'. Supported: {list(format_map.keys())}",
            "output_path": None,
            "format": export_format,
        }

    exporter_name, ext = format_map[export_format]
    output_path = os.path.splitext(resolved_path)[0] + ext

    try:
        exporter_class = get_exporter(exporter_name)
        exporter = exporter_class()
        body, resources = exporter.from_notebook_node(nb)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(body)
        return {
            "success": True,
            "message": f"Exported to {export_format}",
            "output_path": output_path,
            "format": export_format,
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Export failed: {e}",
            "output_path": None,
            "format": export_format,
        }
