"""
Visualization detector: identify which cells produce visual outputs and
classify the visualization type by analysing cell source code and outputs.
"""

import re
import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Library detection patterns
# ---------------------------------------------------------------------------

_LIBRARY_PATTERNS = {
    "matplotlib": [
        r"\bplt\s*\.",
        r"\bmatplotlib\b",
        r"import\s+matplotlib",
        r"from\s+matplotlib",
        r"\bfig,\s*ax\b",
        r"\bax\s*\.",
    ],
    "seaborn": [
        r"\bsns\s*\.",
        r"import\s+seaborn",
        r"from\s+seaborn",
    ],
    "plotly": [
        r"\bpx\s*\.",
        r"\bgo\s*\.",
        r"import\s+plotly",
        r"from\s+plotly",
        r"\.show\(\)",
    ],
    "bokeh": [
        r"import\s+bokeh",
        r"from\s+bokeh",
        r"\bfigure\s*\(",
        r"show\(",
    ],
    "altair": [
        r"\balt\s*\.",
        r"import\s+altair",
        r"from\s+altair",
        r"\.mark_",
    ],
    "pandas_plot": [
        r"\.plot\s*\(",
        r"\.plot\s*\.\s*\w+",
    ],
}

# Chart type patterns: map to canonical chart type names
_CHART_TYPE_PATTERNS = {
    "bar_chart": [
        r"\.bar\s*\(",
        r"\.barh\s*\(",
        r"bar_chart",
        r"\.Bar\s*\(",
        r"px\.bar\s*\(",
        r"sns\.barplot\s*\(",
        r"sns\.countplot\s*\(",
    ],
    "line_chart": [
        r"\.plot\s*\(",
        r"\.line\s*\(",
        r"px\.line\s*\(",
        r"sns\.lineplot\s*\(",
        r"\.Line\s*\(",
    ],
    "scatter": [
        r"\.scatter\s*\(",
        r"px\.scatter\s*\(",
        r"sns\.scatterplot\s*\(",
        r"\.Scatter\s*\(",
        r"\.regplot\s*\(",
    ],
    "histogram": [
        r"\.hist\s*\(",
        r"px\.histogram\s*\(",
        r"sns\.histplot\s*\(",
        r"sns\.distplot\s*\(",
        r"sns\.kdeplot\s*\(",
    ],
    "heatmap": [
        r"sns\.heatmap\s*\(",
        r"\.imshow\s*\(",
        r"px\.imshow\s*\(",
        r"\.pcolor\s*\(",
        r"\.pcolormesh\s*\(",
    ],
    "box_plot": [
        r"\.boxplot\s*\(",
        r"\.box\s*\(",
        r"px\.box\s*\(",
        r"sns\.boxplot\s*\(",
        r"sns\.violinplot\s*\(",
    ],
    "pie_chart": [
        r"\.pie\s*\(",
        r"px\.pie\s*\(",
    ],
    "3d_plot": [
        r"Axes3D",
        r"px\.scatter_3d\s*\(",
        r"px\.line_3d\s*\(",
        r"px\.surface\s*\(",
        r"plot_surface\s*\(",
    ],
    "subplot": [
        r"plt\.subplot",
        r"plt\.subplots\s*\(",
        r"make_subplots\s*\(",
    ],
    "image": [
        r"plt\.imshow\s*\(",
        r"\.imread\s*\(",
        r"Image\.open\s*\(",
    ],
}


def detect_library(source: str) -> Optional[str]:
    """Return the primary visualization library used in *source*, or None."""
    for lib, patterns in _LIBRARY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, source):
                return lib
    return None


def detect_chart_type(source: str) -> Optional[str]:
    """Return the chart type used in *source*, or None."""
    for chart_type, patterns in _CHART_TYPE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, source):
                return chart_type
    return None


def has_visual_output(cell: Any) -> bool:
    """Return True if *cell* has any visual (image/html) output."""
    if cell.cell_type != "code":
        return False
    for out in getattr(cell, "outputs", []):
        if out.output_type in ("execute_result", "display_data"):
            data = getattr(out, "data", {})
            if any(mime in data for mime in ("image/png", "image/jpeg", "image/svg+xml", "text/html")):
                return True
    return False


def produces_visualization(source: str) -> bool:
    """Return True if *source* likely produces a visualization (no output needed)."""
    lib = detect_library(source)
    if lib:
        return True
    # Check for show() calls
    if re.search(r"\bshow\s*\(\s*\)", source):
        return True
    return False


def get_image_data(cell: Any) -> Optional[Dict[str, str]]:
    """Extract the first image output from *cell*.

    Returns:
        Dict with 'mime' and 'data' (base64 string), or None.
    """
    if cell.cell_type != "code":
        return None
    for out in getattr(cell, "outputs", []):
        if out.output_type in ("execute_result", "display_data"):
            data = getattr(out, "data", {})
            for mime in ("image/png", "image/jpeg", "image/svg+xml"):
                if mime in data:
                    return {"mime": mime, "data": data[mime]}
    return None


def get_html_output(cell: Any) -> Optional[str]:
    """Extract the first text/html output from *cell*."""
    if cell.cell_type != "code":
        return None
    for out in getattr(cell, "outputs", []):
        if out.output_type in ("execute_result", "display_data"):
            data = getattr(out, "data", {})
            if "text/html" in data:
                return data["text/html"]
    return None


def scan_notebook_visualizations(nb: Any) -> List[Dict[str, Any]]:
    """Scan all cells and return a list of visualizations found.

    Returns:
        List of dicts: cell_index, library, chart_type, has_output,
        is_interactive, mime_types.
    """
    results = []
    for idx, cell in enumerate(nb.cells):
        if cell.cell_type != "code":
            continue

        source = cell.source
        lib = detect_library(source)
        chart_type = detect_chart_type(source)
        has_output = has_visual_output(cell)
        is_visualization = (lib is not None) or has_output or produces_visualization(source)

        if not is_visualization:
            continue

        mime_types = []
        for out in getattr(cell, "outputs", []):
            if out.output_type in ("execute_result", "display_data"):
                for mime in getattr(out, "data", {}).keys():
                    if mime not in mime_types:
                        mime_types.append(mime)

        is_interactive = lib in ("plotly", "bokeh", "altair") or "text/html" in mime_types

        results.append({
            "cell_index": idx,
            "library": lib,
            "chart_type": chart_type,
            "has_output": has_output,
            "is_interactive": is_interactive,
            "mime_types": mime_types,
        })

    return results
