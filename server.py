"""
MIT License — Copyright (c) 2024 Usama Khatab

Python Notebook MCP — Advanced AI-powered Jupyter notebook interaction server.

Exposes 43 MCP tools across 5 categories:
  - Workspace & Navigation (3 tools)
  - Notebook CRUD (6 tools)
  - Cell Management (14 tools)
  - Execution Engine (7 tools) — requires: pip install jupyter_client ipykernel
  - Visualization Intelligence (5 tools)
  - Notebook Intelligence (6 tools)

Start with: uv run python server.py
"""

import os
import sys
import logging
from contextlib import closing
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(levelname)s [notebook-mcp] %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal modules
# ---------------------------------------------------------------------------
from notebook_mcp import config
from notebook_mcp.security import resolve_path, require_workspace, convert_unix_path
from notebook_mcp.core.notebook_io import (
    get_notebook_content,
    write_notebook_atomic,
    notebook_to_dict,
    _cell_to_dict,
    process_cell_output,
    create_new_notebook,
)
from notebook_mcp.core import cell_ops
from notebook_mcp.core import search as nb_search
from notebook_mcp.visualization import detector as viz_detector
from notebook_mcp.visualization import describer as viz_describer
from notebook_mcp.visualization import image_handler as img_handler
from notebook_mcp.visualization import viz_server
from notebook_mcp.intelligence import summarizer as nb_summarizer
from notebook_mcp.intelligence import pipeline as nb_pipeline
from notebook_mcp.intelligence import data_inspector

log.info("Default workspace directory (uninitialized): %s", config.get_workspace())

# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------
mcp = FastMCP("Jupyter Notebook MCP")


# ===========================================================================
# CATEGORY 1: Workspace & Navigation
# ===========================================================================

@mcp.tool()
def initialize_workspace(directory: str) -> str:
    """IMPORTANT: Call this first! Initialize the workspace directory for this session.

    Must be called before using any other tools. Provide a FULL ABSOLUTE PATH
    to your project folder where notebooks are stored.

    Args:
        directory: The FULL ABSOLUTE PATH to set as the workspace (required).

    Returns:
        Confirmation message with list of any notebooks found.
    """
    if not directory or not directory.strip():
        raise ValueError(
            "ERROR: You must provide a directory path. Please provide the "
            "FULL ABSOLUTE PATH to your project directory."
        )

    directory = convert_unix_path(directory)

    if not os.path.isabs(directory):
        raise ValueError(
            f"ERROR: Relative paths are not allowed. Provide the FULL ABSOLUTE "
            f"PATH (got: '{directory}')."
        )
    if not os.path.exists(directory):
        raise ValueError(f"ERROR: Directory does not exist: {directory}")
    if not os.path.isdir(directory):
        raise ValueError(f"ERROR: Not a directory: {directory}")

    config.set_workspace(directory)
    log.info("Workspace initialized at: %s", directory)

    notebooks: List[str] = []
    with closing(Path(directory).rglob("*.ipynb")) as it:
        for path in it:
            notebooks.append(os.path.relpath(path, directory))

    if notebooks:
        notebook_list = "\n- " + "\n- ".join(notebooks)
        return f"Workspace initialized at: {directory}\nNotebooks found:{notebook_list}"
    return f"Workspace initialized at: {directory}\nNo notebooks found."


@mcp.tool()
@require_workspace
def list_notebooks(directory: str = ".") -> List[str]:
    """List all notebook files (.ipynb) in the given directory (recursive).

    Note: Call initialize_workspace() first.

    Args:
        directory: Subdirectory to search (default: workspace root).
    """
    resolved_directory = resolve_path(directory)
    notebook_files: List[str] = []
    with closing(Path(resolved_directory).rglob("*.ipynb")) as it:
        for path in it:
            notebook_files.append(str(path))
    return notebook_files


@mcp.tool()
@require_workspace
def rename_notebook(filepath: str, new_filepath: str) -> str:
    """Rename or move a notebook file.

    Args:
        filepath:     Current path to the notebook.
        new_filepath: New path for the notebook.
    """
    import shutil
    src = resolve_path(filepath)
    dst = resolve_path(new_filepath)
    if not os.path.exists(src):
        raise FileNotFoundError(f"Notebook not found: {src}")
    if os.path.exists(dst):
        raise FileExistsError(f"Destination already exists: {dst}")
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    shutil.move(src, dst)
    return f"Renamed {src} -> {dst}"


@mcp.tool()
@require_workspace
def delete_notebook(filepath: str) -> str:
    """Permanently delete a notebook file.

    Args:
        filepath: Path to the notebook to delete.
    """
    resolved = resolve_path(filepath)
    if not os.path.exists(resolved):
        raise FileNotFoundError(f"Notebook not found: {resolved}")
    os.remove(resolved)
    return f"Deleted notebook: {resolved}"


# ===========================================================================
# CATEGORY 2: Notebook CRUD (original + new)
# ===========================================================================

@mcp.tool()
@require_workspace
def create_notebook(filepath: str, title: str = "New Notebook") -> str:
    """Create a new Jupyter notebook with a title cell and starter code cell.

    Args:
        filepath: Path where the notebook should be created.
        title:    Title for the notebook (used in the first markdown cell).
    """
    resolved_path = resolve_path(filepath)
    if os.path.exists(resolved_path):
        return f"Notebook already exists at {resolved_path}"
    create_new_notebook(filepath, title)
    return f"Created notebook at {resolved_path}"


@mcp.tool()
@require_workspace
def read_notebook(filepath: str) -> Dict[str, Any]:
    """Read the complete contents of a notebook (all cells, metadata, outputs).

    Args:
        filepath: Path to the notebook file.
    """
    nb = get_notebook_content(filepath)
    return notebook_to_dict(nb)


@mcp.tool()
@require_workspace
def read_cell(filepath: str, cell_index: int) -> Dict[str, Any]:
    """Read a specific cell from a notebook.

    Args:
        filepath:   Path to the notebook file.
        cell_index: Zero-based index of the cell to read.
    """
    nb = get_notebook_content(filepath)
    if cell_index < 0 or cell_index >= len(nb.cells):
        raise IndexError(
            f"Cell index {cell_index} is out of range; "
            f"notebook has {len(nb.cells)} cell(s)."
        )
    return _cell_to_dict(nb.cells[cell_index])


@mcp.tool()
@require_workspace
def edit_cell(filepath: str, cell_index: int, content: str) -> str:
    """Replace the source content of a specific cell.

    Args:
        filepath:   Path to the notebook file.
        cell_index: Zero-based index of the cell to edit.
        content:    New source content for the cell.
    """
    nb = get_notebook_content(filepath)
    if cell_index < 0 or cell_index >= len(nb.cells):
        raise IndexError(
            f"Cell index {cell_index} is out of range; "
            f"notebook has {len(nb.cells)} cell(s)."
        )
    nb.cells[cell_index]["source"] = content
    resolved_path = resolve_path(filepath)
    try:
        write_notebook_atomic(nb, resolved_path)
    except Exception as e:
        raise RuntimeError(f"Failed to update notebook: {e}") from e
    return f"Updated cell {cell_index} in {resolved_path}"


@mcp.tool()
@require_workspace
def add_cell(
    filepath: str,
    content: str,
    cell_type: str = "code",
    index: Optional[int] = None,
) -> str:
    """Add a new cell to a notebook.

    Args:
        filepath:  Path to the notebook file.
        content:   Source content for the new cell.
        cell_type: 'code', 'markdown', or 'raw'.
        index:     Insertion position. None appends at the end.
    """
    from nbformat.v4 import new_code_cell, new_markdown_cell, new_raw_cell
    nb = get_notebook_content(filepath)

    ct = cell_type.lower()
    if ct == "code":
        new_cell = new_code_cell(content)
    elif ct == "markdown":
        new_cell = new_markdown_cell(content)
    elif ct == "raw":
        new_cell = new_raw_cell(content)
    else:
        raise ValueError(f"Invalid cell_type '{cell_type}'. Use 'code', 'markdown', or 'raw'.")

    if index is None:
        nb.cells.append(new_cell)
        position = len(nb.cells) - 1
    else:
        if index < 0 or index > len(nb.cells):
            raise IndexError(
                f"index {index} out of range (0–{len(nb.cells)} inclusive)."
            )
        nb.cells.insert(index, new_cell)
        position = index

    resolved_path = resolve_path(filepath)
    write_notebook_atomic(nb, resolved_path)
    return f"Added {ct} cell at position {position} in {resolved_path}"


@mcp.tool()
@require_workspace
def read_notebook_outputs(filepath: str) -> List[Dict[str, Any]]:
    """Read all outputs from all code cells in a notebook.

    Returns list of dicts with cell_index and outputs.
    """
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
    """Read the output(s) of a specific code cell.

    Args:
        filepath:   Path to the notebook file.
        cell_index: Zero-based index of the cell.
    """
    nb = get_notebook_content(filepath)
    if cell_index < 0 or cell_index >= len(nb.cells):
        raise IndexError(f"Cell index {cell_index} out of range.")
    cell = nb.cells[cell_index]
    if cell.cell_type != "code" or not hasattr(cell, "outputs") or not cell.outputs:
        return []
    return [process_cell_output(o) for o in cell.outputs]


# ===========================================================================
# CATEGORY 3: Cell Management
# ===========================================================================

@mcp.tool()
@require_workspace
def delete_cell(filepath: str, cell_index: int) -> str:
    """Delete a cell from a notebook.

    Args:
        filepath:   Path to the notebook.
        cell_index: Zero-based index of the cell to delete.
    """
    return cell_ops.delete_cell(filepath, cell_index)


@mcp.tool()
@require_workspace
def move_cell(filepath: str, from_index: int, to_index: int) -> str:
    """Move a cell from one position to another.

    Args:
        filepath:   Path to the notebook.
        from_index: Current zero-based index of the cell.
        to_index:   Target zero-based index for the cell.
    """
    return cell_ops.move_cell(filepath, from_index, to_index)


@mcp.tool()
@require_workspace
def duplicate_cell(filepath: str, cell_index: int, count: int = 1) -> str:
    """Duplicate a cell one or more times, inserting copies immediately after it.

    Args:
        filepath:   Path to the notebook.
        cell_index: Zero-based index of the cell to duplicate.
        count:      Number of copies to insert (default 1).
    """
    return cell_ops.duplicate_cell(filepath, cell_index, count)


@mcp.tool()
@require_workspace
def change_cell_type(filepath: str, cell_index: int, new_type: str) -> str:
    """Change the type of a cell (code, markdown, or raw).

    Args:
        filepath:   Path to the notebook.
        cell_index: Zero-based index of the cell.
        new_type:   'code', 'markdown', or 'raw'.
    """
    return cell_ops.change_cell_type(filepath, cell_index, new_type)


@mcp.tool()
@require_workspace
def split_cell(filepath: str, cell_index: int, line_number: int) -> str:
    """Split a cell into two at the specified line number (1-based).

    Lines 1..line_number go into the first cell; remaining lines into the second.

    Args:
        filepath:    Path to the notebook.
        cell_index:  Zero-based index of the cell to split.
        line_number: Line at which to split (1-based; must be 1..n-1).
    """
    return cell_ops.split_cell(filepath, cell_index, line_number)


@mcp.tool()
@require_workspace
def merge_cells(filepath: str, cell_index: int) -> str:
    """Merge a cell with the cell immediately following it.

    Args:
        filepath:   Path to the notebook.
        cell_index: Zero-based index of the first cell to merge.
    """
    return cell_ops.merge_cells(filepath, cell_index)


@mcp.tool()
@require_workspace
def bulk_add_cells(
    filepath: str,
    cells: List[Dict[str, str]],
    index: Optional[int] = None,
) -> str:
    """Add multiple cells to a notebook in a single operation.

    Args:
        filepath: Path to the notebook.
        cells:    List of cell specs. Each spec is a dict with:
                    - 'content' (required): the cell source
                    - 'cell_type' (optional): 'code' | 'markdown' | 'raw'
                                              (default 'code')
        index:    Insertion position. None appends all cells at the end.
    """
    return cell_ops.bulk_add_cells(filepath, cells, index)


@mcp.tool()
@require_workspace
def clear_cell_outputs(filepath: str, cell_index: int) -> str:
    """Clear outputs and execution count from a specific code cell.

    Args:
        filepath:   Path to the notebook.
        cell_index: Zero-based index of the cell.
    """
    return cell_ops.clear_cell_outputs(filepath, cell_index)


@mcp.tool()
@require_workspace
def clear_all_outputs(filepath: str) -> str:
    """Clear outputs and execution counts from all code cells in a notebook.

    Args:
        filepath: Path to the notebook.
    """
    return cell_ops.clear_all_outputs(filepath)


@mcp.tool()
@require_workspace
def notebook_search(
    filepath: str,
    query: str,
    case_sensitive: bool = False,
    context_lines: int = 2,
) -> List[Dict[str, Any]]:
    """Search all cells in a notebook for a keyword with context snippets.

    Args:
        filepath:       Path to the notebook.
        query:          Search string.
        case_sensitive: Whether the search is case-sensitive (default False).
        context_lines:  Surrounding lines to show per match (default 2).

    Returns:
        List of match dicts: cell_index, cell_type, match_count, matches.
    """
    return nb_search.notebook_search(filepath, query, case_sensitive, context_lines)


@mcp.tool()
@require_workspace
def notebook_outline(filepath: str) -> List[Dict[str, Any]]:
    """Get a structural outline of the notebook.

    For markdown cells: extracts headings (H1–H6).
    For code cells: extracts top-level function and class definitions.

    Returns:
        List of outline entries: cell_index, cell_type, kind, name,
        line_number, line_count.
    """
    return nb_search.notebook_outline(filepath)


@mcp.tool()
@require_workspace
def notebook_info(filepath: str) -> Dict[str, Any]:
    """Get general information and statistics about a notebook.

    Returns:
        Dict with: cell_count, code_cells, markdown_cells, raw_cells,
        cells_with_output, total_output_count, has_errors, kernel_name,
        language, nbformat_version, file_size_bytes.
    """
    return nb_search.notebook_info(filepath)


@mcp.tool()
@require_workspace
def notebook_validate(filepath: str) -> Dict[str, Any]:
    """Validate a notebook against the nbformat schema.

    Returns:
        Dict with: valid (bool), errors (list), error_count.
    """
    return nb_search.notebook_validate(filepath)


@mcp.tool()
@require_workspace
def notebook_export(filepath: str, export_format: str = "python") -> Dict[str, Any]:
    """Export a notebook to another format using nbconvert.

    Requires: pip install nbconvert

    Args:
        filepath:      Path to the notebook.
        export_format: 'python', 'html', 'markdown', 'rst', 'latex', 'slides'.

    Returns:
        Dict with: success, output_path, format, message.
    """
    return nb_search.notebook_export(filepath, export_format)


# ===========================================================================
# CATEGORY 4: Execution Engine
# ===========================================================================

@mcp.tool()
@require_workspace
def execute_cell(
    filepath: str,
    cell_index: int,
    timeout: float = 60.0,
    save_outputs: bool = True,
) -> Dict[str, Any]:
    """Execute a single code cell using the associated Jupyter kernel.

    Requires: pip install jupyter_client ipykernel

    Starts a kernel automatically if one isn't already running for this notebook.
    Outputs are captured and returned, and optionally saved back to the .ipynb file.

    Args:
        filepath:     Path to the notebook.
        cell_index:   Zero-based index of the cell to execute.
        timeout:      Execution timeout in seconds (default 60).
        save_outputs: Write execution outputs back to the notebook (default True).

    Returns:
        Dict with: cell_index, execution_count, outputs, timed_out,
        error_message, duration_ms.
    """
    from notebook_mcp.execution.executor import execute_cell as _exec
    return _exec(filepath, cell_index, timeout=timeout, save_outputs=save_outputs)


@mcp.tool()
@require_workspace
def execute_range(
    filepath: str,
    start_index: int,
    end_index: int,
    timeout: float = 60.0,
    stop_on_error: bool = True,
) -> List[Dict[str, Any]]:
    """Execute a range of cells [start_index, end_index] inclusive.

    Requires: pip install jupyter_client ipykernel

    Args:
        filepath:      Path to the notebook.
        start_index:   First cell to execute (0-based).
        end_index:     Last cell to execute (0-based, inclusive).
        timeout:       Per-cell execution timeout in seconds (default 60).
        stop_on_error: Stop on first cell error (default True).

    Returns:
        List of per-cell result dicts.
    """
    from notebook_mcp.execution.executor import execute_range as _exec_range
    return _exec_range(filepath, start_index, end_index, timeout=timeout, stop_on_error=stop_on_error)


@mcp.tool()
@require_workspace
def execute_all(
    filepath: str,
    timeout: float = 60.0,
    stop_on_error: bool = True,
) -> Dict[str, Any]:
    """Execute all cells in a notebook from top to bottom.

    Requires: pip install jupyter_client ipykernel

    Args:
        filepath:      Path to the notebook.
        timeout:       Per-cell execution timeout in seconds (default 60).
        stop_on_error: Stop on first cell error (default True).

    Returns:
        Dict with: total_cells, executed, skipped, errored,
        total_duration_ms, results.
    """
    from notebook_mcp.execution.executor import execute_all as _exec_all
    return _exec_all(filepath, timeout=timeout, stop_on_error=stop_on_error)


@mcp.tool()
@require_workspace
def restart_kernel(filepath: str) -> str:
    """Restart the Jupyter kernel for a notebook, clearing all in-memory state.

    Requires: pip install jupyter_client ipykernel

    Args:
        filepath: Path to the notebook whose kernel should be restarted.
    """
    from notebook_mcp.execution.kernel import restart_kernel as _restart
    return _restart(filepath)


@mcp.tool()
@require_workspace
def interrupt_kernel(filepath: str) -> str:
    """Send an interrupt signal to the kernel (equivalent to Ctrl+C).

    Requires: pip install jupyter_client ipykernel

    Args:
        filepath: Path to the notebook.
    """
    from notebook_mcp.execution.kernel import interrupt_kernel as _interrupt
    return _interrupt(filepath)


@mcp.tool()
@require_workspace
def get_kernel_status(filepath: str) -> Dict[str, Any]:
    """Get the status of the kernel associated with a notebook.

    Returns:
        Dict with: status, kernel_name, is_alive, filepath.
    """
    from notebook_mcp.execution.kernel import get_kernel_status as _status
    return _status(filepath)


@mcp.tool()
@require_workspace
def inspect_variable(filepath: str, variable_name: str) -> Dict[str, Any]:
    """Inspect a variable in the kernel's namespace.

    Requires the kernel to be running (call execute_cell first if needed).
    Requires: pip install jupyter_client ipykernel

    Args:
        filepath:      Path to the notebook.
        variable_name: Name of the variable to inspect.

    Returns:
        Dict with: name, type, repr, shape (arrays/DataFrames), columns,
        dtype, length.
    """
    from notebook_mcp.execution.executor import inspect_variable as _inspect
    return _inspect(filepath, variable_name)


@mcp.tool()
@require_workspace
def list_kernel_variables(filepath: str) -> Dict[str, Any]:
    """List all user-defined variables in the kernel's namespace.

    Requires: pip install jupyter_client ipykernel

    Args:
        filepath: Path to the notebook.

    Returns:
        Dict with 'variables': {name: {type, repr}} mapping.
    """
    from notebook_mcp.execution.executor import list_kernel_variables as _list_vars
    return _list_vars(filepath)


# ===========================================================================
# CATEGORY 5: Visualization Intelligence
# ===========================================================================

@mcp.tool()
@require_workspace
def describe_visualization(filepath: str, cell_index: int) -> Dict[str, Any]:
    """Generate a structured text description of a cell's visualization.

    Analyses both the source code and stored output to describe the chart type,
    axes, title, data variables, and other properties. This lets LLMs understand
    visualizations without needing to see the actual image.

    Args:
        filepath:   Path to the notebook.
        cell_index: Zero-based index of the cell containing the visualization.

    Returns:
        Dict with: description (natural language), chart_type, library, title,
        x_label, y_label, data_variables, series_names, is_interactive,
        has_rendered_output, output_mimes.
    """
    nb = get_notebook_content(filepath)
    n = len(nb.cells)
    if cell_index < 0 or cell_index >= n:
        raise IndexError(f"Cell index {cell_index} out of range (0–{n-1}).")
    cell = nb.cells[cell_index]
    desc = viz_describer.describe_cell_visualization(cell, cell_index)
    return desc.to_dict()


@mcp.tool()
@require_workspace
def scan_visualizations(filepath: str) -> List[Dict[str, Any]]:
    """Scan a notebook and return all cells that produce visualizations.

    Returns:
        List of dicts: cell_index, library, chart_type, has_output,
        is_interactive, mime_types.
    """
    nb = get_notebook_content(filepath)
    return viz_detector.scan_notebook_visualizations(nb)


@mcp.tool()
@require_workspace
def get_visualization_image(
    filepath: str,
    cell_index: int,
    max_width: int = 1200,
    max_height: int = 900,
    max_size_kb: int = 500,
) -> Dict[str, Any]:
    """Get the actual image data from a visualization cell.

    Returns the base64-encoded image data, suitable for passing to
    vision-capable LLMs (Claude, GPT-4V). Images are optionally resized
    to stay within the specified size limits.

    Requires: pip install Pillow  (for image resizing; optional)

    Args:
        filepath:    Path to the notebook.
        cell_index:  Zero-based index of the cell.
        max_width:   Maximum image width in pixels (default 1200).
        max_height:  Maximum image height in pixels (default 900).
        max_size_kb: Maximum output size in KB (default 500).

    Returns:
        Dict with: mime, data (base64), original_size_chars,
        returned_size_chars, resized. Or error if no image found.
    """
    nb = get_notebook_content(filepath)
    n = len(nb.cells)
    if cell_index < 0 or cell_index >= n:
        raise IndexError(f"Cell index {cell_index} out of range (0–{n-1}).")
    cell = nb.cells[cell_index]
    result = img_handler.get_cell_image(cell, max_width, max_height, max_size_kb)
    if result is None:
        # Also generate a description so the LLM isn't empty-handed
        desc = viz_describer.describe_cell_visualization(cell, cell_index)
        return {
            "error": "No image output found in this cell.",
            "hint": "Execute the cell first using execute_cell(), then try again.",
            "description": desc.description,
        }
    # Add description alongside the image
    desc = viz_describer.describe_cell_visualization(cell, cell_index)
    result["description"] = desc.description
    return result


@mcp.tool()
@require_workspace
def open_visualization(
    filepath: str,
    cell_index: int,
    open_browser: bool = True,
) -> Dict[str, Any]:
    """Open a cell's visualization in a browser window.

    Starts an on-demand local web server (port 9981 by default) and opens
    the visualization in the default browser. Interactive visualizations
    (Plotly, Bokeh) are served as interactive HTML pages.

    Args:
        filepath:     Path to the notebook.
        cell_index:   Zero-based index of the cell.
        open_browser: Whether to open the URL in the default browser (default True).

    Returns:
        Dict with: url, cell_index, description, opened_browser.
    """
    nb = get_notebook_content(filepath)
    n = len(nb.cells)
    if cell_index < 0 or cell_index >= n:
        raise IndexError(f"Cell index {cell_index} out of range (0–{n-1}).")
    cell = nb.cells[cell_index]
    notebook_name = os.path.basename(filepath)
    desc = viz_describer.describe_cell_visualization(cell, cell_index)
    page_html = viz_server.render_cell_to_html(cell, cell_index, notebook_name, desc.description)

    if page_html is None:
        return {
            "url": None,
            "error": "No visual output found in this cell.",
            "hint": "Execute the cell first to generate output, then call this tool again.",
            "description": desc.description,
        }

    url = viz_server.cache_and_open_visualization(
        filepath, cell_index, page_html, open_browser=open_browser
    )
    return {
        "url": url,
        "cell_index": cell_index,
        "description": desc.description,
        "opened_browser": open_browser,
    }


@mcp.tool()
@require_workspace
def open_gallery(filepath: str, open_browser: bool = True) -> Dict[str, Any]:
    """Open a gallery of all visualizations in a notebook in a browser window.

    Starts the on-demand visualization server and opens a gallery page showing
    thumbnails of all plot outputs found in the notebook.

    Args:
        filepath:     Path to the notebook.
        open_browser: Whether to open the URL in the default browser (default True).

    Returns:
        Dict with: url, visualization_count, opened_browser.
    """
    nb = get_notebook_content(filepath)
    notebook_name = os.path.basename(filepath)
    viz_list = viz_detector.scan_notebook_visualizations(nb)

    gallery_items = []
    for info in viz_list:
        idx = info["cell_index"]
        cell = nb.cells[idx]
        desc = viz_describer.describe_cell_visualization(cell, idx)

        # Generate a thumbnail (small version of the image)
        img = img_handler.get_cell_image(cell, max_width=400, max_height=300, max_size_kb=100)
        thumb = img["data"] if img else None

        key = viz_server._make_key(filepath, idx)
        # Cache the full-size page too
        page_html = viz_server.render_cell_to_html(cell, idx, notebook_name, desc.description)
        if page_html:
            viz_server._viz_cache[key] = page_html

        gallery_items.append({
            "key": key,
            "cell_index": idx,
            "library": info.get("library"),
            "chart_type": info.get("chart_type"),
            "description": desc.description,
            "thumbnail": thumb,
        })

    gallery_html = viz_server._render_gallery_page(notebook_name, gallery_items)
    url = viz_server.cache_and_open_gallery(filepath, gallery_html, open_browser=open_browser)

    return {
        "url": url,
        "visualization_count": len(viz_list),
        "opened_browser": open_browser,
    }


# ===========================================================================
# CATEGORY 6: Notebook Intelligence
# ===========================================================================

@mcp.tool()
@require_workspace
def summarize_notebook(
    filepath: str,
    detail_level: str = "standard",
) -> Dict[str, Any]:
    """Generate a structured summary of a notebook's purpose and content.

    Analyses all cells statically (no kernel required) to produce a summary
    covering: title, domain, data sources, operations performed, visualizations,
    and execution state.

    Args:
        filepath:     Path to the notebook.
        detail_level: 'brief' (minimal), 'standard' (default), or 'detailed'
                      (includes full outline and imports).

    Returns:
        Dict with summary fields appropriate to detail_level.
    """
    return nb_summarizer.summarize_notebook(filepath, detail_level)


@mcp.tool()
@require_workspace
def get_notebook_pipeline(filepath: str) -> Dict[str, Any]:
    """Analyse a notebook's data flow and return a pipeline description.

    Statically infers variable assignments and reads between cells to
    produce a DAG-like description of the data pipeline.

    Returns:
        Dict with: stages (role, produces, consumes per cell), data_flow,
        entry_points, exit_points, role_summary, summary.
    """
    return nb_pipeline.get_notebook_pipeline(filepath)


@mcp.tool()
@require_workspace
def analyze_cell_error(filepath: str, cell_index: int) -> Dict[str, Any]:
    """Analyze the error output of a cell and provide diagnostic hints.

    Parses the stored error traceback, identifies the error type and likely
    cause, and suggests a fix. Works without a running kernel.

    Args:
        filepath:   Path to the notebook.
        cell_index: Zero-based index of the cell to analyze.

    Returns:
        Dict with: has_error, error_type, error_message, traceback_summary,
        error_line, hint, preceding_context, cell_source.
    """
    return data_inspector.analyze_cell_error(filepath, cell_index)


@mcp.tool()
@require_workspace
def inspect_dataframe_output(filepath: str, cell_index: int) -> Dict[str, Any]:
    """Extract DataFrame metadata from a cell's stored output (no kernel needed).

    Parses the HTML table representation that pandas generates to extract
    column names, visible row count, and shape.

    Args:
        filepath:   Path to the notebook.
        cell_index: Zero-based index of the cell.
    """
    return data_inspector.inspect_dataframe_from_output(filepath, cell_index)


# ===========================================================================
# Entry point
# ===========================================================================

def main() -> None:
    """Start the Notebook MCP Server."""
    log.info("Starting Notebook MCP Server v2.0 (Advanced Edition)...")
    log.info("Working directory: %s", os.getcwd())
    log.info(
        "Tools available: workspace(4) + notebook_crud(8) + cell_mgmt(14) + "
        "execution(8) + visualization(5) + intelligence(4) = 43 total"
    )

    try:
        mcp.run()
    except AttributeError:
        log.warning("mcp.run() not found — trying legacy entry points.")
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
