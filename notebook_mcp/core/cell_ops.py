"""
Cell-level manipulation operations for Jupyter notebooks.

All functions load the notebook, perform the requested operation, and
atomically write the result back.
"""

import os
import logging
from typing import Any, Dict, List, Optional

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_raw_cell

from notebook_mcp.security import resolve_path
from notebook_mcp.core.notebook_io import (
    get_notebook_content,
    write_notebook_atomic,
    _cell_to_dict,
)

log = logging.getLogger(__name__)


def _validate_index(nb: nbformat.NotebookNode, index: int, allow_end: bool = False) -> None:
    """Raise IndexError if *index* is out of range for nb.cells."""
    n = len(nb.cells)
    upper = n if allow_end else n - 1
    if n == 0:
        raise IndexError("Notebook has no cells.")
    if index < 0 or index > upper:
        raise IndexError(
            f"Cell index {index} out of range; notebook has {n} cell(s) "
            f"(valid indices: 0–{upper})."
        )


def _make_cell(cell_type: str, content: str) -> nbformat.NotebookNode:
    """Create a new cell node of the given type."""
    ct = cell_type.lower()
    if ct == "code":
        return new_code_cell(content)
    elif ct == "markdown":
        return new_markdown_cell(content)
    elif ct == "raw":
        return new_raw_cell(content)
    else:
        raise ValueError(f"Invalid cell type '{cell_type}'. Must be 'code', 'markdown', or 'raw'.")


# ---------------------------------------------------------------------------
# Cell CRUD
# ---------------------------------------------------------------------------

def delete_cell(filepath: str, cell_index: int) -> str:
    """Delete a cell at *cell_index*."""
    nb = get_notebook_content(filepath)
    _validate_index(nb, cell_index)
    nb.cells.pop(cell_index)
    resolved_path = resolve_path(filepath)
    write_notebook_atomic(nb, resolved_path)
    return f"Deleted cell {cell_index} from {resolved_path}"


def move_cell(filepath: str, from_index: int, to_index: int) -> str:
    """Move a cell from *from_index* to *to_index*."""
    nb = get_notebook_content(filepath)
    n = len(nb.cells)
    if n == 0:
        raise IndexError("Notebook has no cells.")
    if from_index < 0 or from_index >= n:
        raise IndexError(f"from_index {from_index} out of range (0–{n-1}).")
    if to_index < 0 or to_index >= n:
        raise IndexError(f"to_index {to_index} out of range (0–{n-1}).")
    if from_index == to_index:
        return f"Cell {from_index} is already at index {to_index}."

    cell = nb.cells.pop(from_index)
    nb.cells.insert(to_index, cell)
    resolved_path = resolve_path(filepath)
    write_notebook_atomic(nb, resolved_path)
    return f"Moved cell from {from_index} to {to_index} in {resolved_path}"


def duplicate_cell(filepath: str, cell_index: int, count: int = 1) -> str:
    """Duplicate a cell *count* times, inserting copies immediately after it."""
    import copy
    import uuid
    if count < 1:
        raise ValueError("count must be >= 1.")
    nb = get_notebook_content(filepath)
    _validate_index(nb, cell_index)
    cell = nb.cells[cell_index]
    for i in range(count):
        new_cell = copy.deepcopy(cell)
        # Assign a unique ID to avoid nbformat DuplicateCellId warnings
        new_cell.id = uuid.uuid4().hex[:8]
        nb.cells.insert(cell_index + 1 + i, new_cell)
    resolved_path = resolve_path(filepath)
    write_notebook_atomic(nb, resolved_path)
    return f"Duplicated cell {cell_index} {count} time(s) in {resolved_path}"


def change_cell_type(filepath: str, cell_index: int, new_type: str) -> str:
    """Change the type of a cell (code, markdown, raw)."""
    valid = {"code", "markdown", "raw"}
    if new_type.lower() not in valid:
        raise ValueError(f"new_type must be one of {valid}, got '{new_type}'.")
    nb = get_notebook_content(filepath)
    _validate_index(nb, cell_index)
    old_cell = nb.cells[cell_index]
    source = old_cell.source
    new_cell = _make_cell(new_type.lower(), source)
    nb.cells[cell_index] = new_cell
    resolved_path = resolve_path(filepath)
    write_notebook_atomic(nb, resolved_path)
    return f"Changed cell {cell_index} from '{old_cell.cell_type}' to '{new_type.lower()}' in {resolved_path}"


def split_cell(filepath: str, cell_index: int, line_number: int) -> str:
    """Split a cell at *line_number* (1-based, first line goes into the first cell)."""
    nb = get_notebook_content(filepath)
    _validate_index(nb, cell_index)
    cell = nb.cells[cell_index]
    lines = cell.source.splitlines(keepends=True)
    if line_number < 1 or line_number >= len(lines):
        raise ValueError(
            f"line_number {line_number} out of range; cell has {len(lines)} line(s) "
            f"(split must be between line 1 and {len(lines) - 1})."
        )
    top = "".join(lines[:line_number])
    bottom = "".join(lines[line_number:])
    second_cell = _make_cell(cell.cell_type, bottom)
    cell.source = top
    nb.cells.insert(cell_index + 1, second_cell)
    resolved_path = resolve_path(filepath)
    write_notebook_atomic(nb, resolved_path)
    return f"Split cell {cell_index} at line {line_number} into cells {cell_index} and {cell_index + 1} in {resolved_path}"


def merge_cells(filepath: str, cell_index: int, separator: str = "\n\n") -> str:
    """Merge cell at *cell_index* with the next cell."""
    nb = get_notebook_content(filepath)
    if len(nb.cells) < 2:
        raise ValueError("Notebook must have at least 2 cells to merge.")
    _validate_index(nb, cell_index)
    if cell_index >= len(nb.cells) - 1:
        raise IndexError(f"Cell {cell_index} is the last cell; no next cell to merge with.")
    cell_a = nb.cells[cell_index]
    cell_b = nb.cells[cell_index + 1]
    if cell_a.cell_type != cell_b.cell_type:
        log.warning(
            "Merging cells of different types ('%s' and '%s'); result keeps type '%s'.",
            cell_a.cell_type, cell_b.cell_type, cell_a.cell_type,
        )
    cell_a.source = cell_a.source + separator + cell_b.source
    nb.cells.pop(cell_index + 1)
    resolved_path = resolve_path(filepath)
    write_notebook_atomic(nb, resolved_path)
    return f"Merged cells {cell_index} and {cell_index + 1} in {resolved_path}"


def bulk_add_cells(
    filepath: str,
    cells: List[Dict[str, str]],
    index: Optional[int] = None,
) -> str:
    """Add multiple cells at once.

    Args:
        filepath: Path to the notebook.
        cells:    List of dicts, each with 'content' and optionally 'cell_type'
                  (default 'code').
        index:    Insertion position. None appends all cells.

    Returns:
        Confirmation with count of cells added.
    """
    if not cells:
        raise ValueError("cells list must not be empty.")
    nb = get_notebook_content(filepath)

    if index is None:
        insert_at = len(nb.cells)
    else:
        if index < 0 or index > len(nb.cells):
            raise IndexError(
                f"index {index} out of range (0–{len(nb.cells)} inclusive)."
            )
        insert_at = index

    new_cells = []
    for i, spec in enumerate(cells):
        if "content" not in spec:
            raise ValueError(f"Cell spec at position {i} missing required 'content' key.")
        cell_type = spec.get("cell_type", "code")
        new_cells.append(_make_cell(cell_type, spec["content"]))

    for i, cell in enumerate(new_cells):
        nb.cells.insert(insert_at + i, cell)

    resolved_path = resolve_path(filepath)
    write_notebook_atomic(nb, resolved_path)
    return f"Added {len(new_cells)} cell(s) starting at index {insert_at} in {resolved_path}"


def clear_cell_outputs(filepath: str, cell_index: int) -> str:
    """Clear outputs and execution count from a specific code cell."""
    nb = get_notebook_content(filepath)
    _validate_index(nb, cell_index)
    cell = nb.cells[cell_index]
    if cell.cell_type != "code":
        return f"Cell {cell_index} is a '{cell.cell_type}' cell; only code cells have outputs."
    cell.outputs = []
    cell.execution_count = None
    resolved_path = resolve_path(filepath)
    write_notebook_atomic(nb, resolved_path)
    return f"Cleared outputs from cell {cell_index} in {resolved_path}"


def clear_all_outputs(filepath: str) -> str:
    """Clear outputs and execution counts from all code cells."""
    nb = get_notebook_content(filepath)
    count = 0
    for cell in nb.cells:
        if cell.cell_type == "code":
            cell.outputs = []
            cell.execution_count = None
            count += 1
    resolved_path = resolve_path(filepath)
    write_notebook_atomic(nb, resolved_path)
    return f"Cleared outputs from {count} code cell(s) in {resolved_path}"
