"""
Data and error inspection utilities.

Functions for analyzing cell errors and inspecting DataFrames / variables
either statically (from cell outputs) or via a live kernel.
"""

import re
import logging
from typing import Any, Dict, List, Optional

from notebook_mcp.core.notebook_io import get_notebook_content

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Error analysis (static — from stored outputs)
# ---------------------------------------------------------------------------

_ERROR_PATTERNS = {
    "NameError": {
        "pattern": r"NameError: name '(\w+)' is not defined",
        "hint": "Variable '{name}' is used before being assigned. Check if an earlier cell that defines it has been executed.",
    },
    "KeyError": {
        "pattern": r"KeyError: ['\"]?([^'\")\n]+)['\"]?",
        "hint": "Key '{name}' not found in dictionary or DataFrame. Check spelling and available keys.",
    },
    "AttributeError": {
        "pattern": r"AttributeError: '(\w+)' object has no attribute '(\w+)'",
        "hint": "Object of type '{name}' does not have attribute '{attr}'. Check the object type and available methods.",
    },
    "ImportError": {
        "pattern": r"(?:Import|Module)Error.*'([^']+)'",
        "hint": "Module '{name}' not found. Install it with: pip install {name}",
    },
    "IndexError": {
        "pattern": r"IndexError: (.+)",
        "hint": "Index out of range: {name}. Check the size of the list/array.",
    },
    "TypeError": {
        "pattern": r"TypeError: (.+)",
        "hint": "Type mismatch: {name}. Check the types of arguments being passed.",
    },
    "ValueError": {
        "pattern": r"ValueError: (.+)",
        "hint": "Value error: {name}. The value passed is not valid for this operation.",
    },
    "FileNotFoundError": {
        "pattern": r"FileNotFoundError.*'([^']+)'",
        "hint": "File '{name}' not found. Check the path and working directory.",
    },
    "ZeroDivisionError": {
        "pattern": r"ZeroDivisionError",
        "hint": "Division by zero. Check your denominator before dividing.",
    },
    "MemoryError": {
        "pattern": r"MemoryError",
        "hint": "Out of memory. Consider reducing data size, using chunked processing, or freeing unused variables.",
    },
}


def analyze_cell_error(filepath: str, cell_index: int) -> Dict[str, Any]:
    """Analyze the error output of a cell and provide diagnostic information.

    Args:
        filepath:   Path to the notebook.
        cell_index: Zero-based index of the cell to analyze.

    Returns:
        Dict with: has_error, error_type, error_message, traceback_summary,
        hint, source_context, suggested_fix.
    """
    nb = get_notebook_content(filepath)
    n = len(nb.cells)
    if cell_index < 0 or cell_index >= n:
        raise IndexError(f"Cell index {cell_index} out of range (0–{n-1}).")

    cell = nb.cells[cell_index]
    if cell.cell_type != "code":
        return {"has_error": False, "reason": "Not a code cell."}

    # Find error outputs
    error_output = None
    for out in getattr(cell, "outputs", []):
        if out.output_type == "error":
            error_output = out
            break

    if error_output is None:
        return {"has_error": False, "reason": "No error output found in this cell."}

    ename = error_output.ename
    evalue = error_output.evalue
    traceback = getattr(error_output, "traceback", [])

    # Clean ANSI escape codes from traceback
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    clean_tb = [ansi_escape.sub("", line) for line in traceback]
    tb_summary = "\n".join(clean_tb[-10:])  # last 10 lines

    # Match against known error patterns
    hint = None
    full_error = f"{ename}: {evalue}"
    for err_type, info in _ERROR_PATTERNS.items():
        m = re.search(info["pattern"], full_error)
        if m:
            groups = m.groups()
            kwargs: Dict[str, str] = {}
            if groups:
                kwargs["name"] = groups[0]
            if len(groups) > 1:
                kwargs["attr"] = groups[1]
            hint = info["hint"].format(**kwargs)
            break

    # Get context: the 3 cells before this one (to understand what's defined)
    context_cells = []
    for i in range(max(0, cell_index - 3), cell_index):
        c = nb.cells[i]
        if c.cell_type == "code" and c.source.strip():
            context_cells.append({
                "cell_index": i,
                "source_preview": c.source.splitlines()[0][:100] if c.source else "",
                "execution_count": getattr(c, "execution_count", None),
            })

    # Look for the specific line in the cell source that caused the error
    error_line = None
    if clean_tb:
        for line in reversed(clean_tb):
            m = re.search(r"---> (\d+)\s+(.+)", line)
            if m:
                lineno = int(m.group(1))
                lines = cell.source.splitlines()
                if 1 <= lineno <= len(lines):
                    error_line = {"line_number": lineno, "content": lines[lineno - 1]}
                break

    return {
        "has_error": True,
        "error_type": ename,
        "error_message": evalue,
        "traceback_summary": tb_summary,
        "error_line": error_line,
        "hint": hint or f"Review the {ename} traceback above for details.",
        "preceding_context": context_cells,
        "cell_source": cell.source,
    }


# ---------------------------------------------------------------------------
# DataFrame inspection (from static outputs)
# ---------------------------------------------------------------------------

def inspect_dataframe_from_output(filepath: str, cell_index: int) -> Dict[str, Any]:
    """Extract DataFrame information from a cell's stored text/html output.

    This works without a kernel by parsing the HTML table representation
    that pandas generates (e.g. from df.head(), df.describe(), df.info()).

    Returns:
        Dict with available DataFrame metadata, or empty dict if not found.
    """
    nb = get_notebook_content(filepath)
    n = len(nb.cells)
    if cell_index < 0 or cell_index >= n:
        raise IndexError(f"Cell index {cell_index} out of range (0–{n-1}).")

    cell = nb.cells[cell_index]
    result: Dict[str, Any] = {"cell_index": cell_index}

    for out in getattr(cell, "outputs", []):
        if out.output_type not in ("execute_result", "display_data"):
            continue
        data = getattr(out, "data", {})

        # Parse HTML table to extract column names
        if "text/html" in data:
            html_content = data["text/html"]
            # Extract column headers from <th> tags
            headers = re.findall(r"<th>([^<]+)</th>", html_content)
            if headers:
                # First th is usually the index label
                result["columns"] = headers[1:] if len(headers) > 1 else headers

            # Count rows from <tr> tags (subtract header rows)
            rows = html_content.count("<tr>")
            if rows > 0:
                result["visible_rows"] = rows - 1  # subtract header

        # Parse text/plain for shape info from repr
        if "text/plain" in data:
            text = data["text/plain"]
            m = re.search(r"\[(\d+)\s+rows\s+x\s+(\d+)\s+columns\]", text)
            if m:
                result["shape"] = [int(m.group(1)), int(m.group(2))]

    return result
