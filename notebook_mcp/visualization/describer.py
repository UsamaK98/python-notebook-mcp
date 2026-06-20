"""
Visualization describer: generate structured text descriptions of plots
by analysing cell source code and output metadata.

Enables LLMs to understand what a visualization shows without needing
to "see" the image directly.
"""

import ast
import re
import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from notebook_mcp.visualization.detector import (
    detect_library,
    detect_chart_type,
    has_visual_output,
    get_image_data,
    get_html_output,
)

log = logging.getLogger(__name__)


@dataclass
class PlotDescription:
    """Structured description of a visualization."""
    cell_index: int
    library: Optional[str] = None
    chart_type: Optional[str] = None
    title: Optional[str] = None
    x_label: Optional[str] = None
    y_label: Optional[str] = None
    z_label: Optional[str] = None
    data_variables: List[str] = field(default_factory=list)
    series_names: List[str] = field(default_factory=list)
    color_info: Optional[str] = None
    figure_size: Optional[str] = None
    annotations: List[str] = field(default_factory=list)
    is_interactive: bool = False
    has_rendered_output: bool = False
    output_mimes: List[str] = field(default_factory=list)
    source_summary: str = ""
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _extract_string_arg(source: str, pattern: str) -> Optional[str]:
    """Extract a string argument from a function call matching *pattern*.

    e.g. pattern=r"plt\\.title\\s*\\(" extracts "My Title" from plt.title("My Title").
    """
    # Match calls like func("string") or func('string')
    full_pattern = pattern + r'\s*["\']([^"\']+)["\']'
    m = re.search(full_pattern, source)
    if m:
        return m.group(1)
    # Also try keyword argument: title="string"
    kw_pattern = r'title\s*=\s*["\']([^"\']+)["\']'
    m = re.search(kw_pattern, source)
    if m:
        return m.group(1)
    return None


def _extract_variable_names(source: str) -> List[str]:
    """Extract variable names used as data arguments in plotting calls."""
    variables = set()

    # Common patterns: func(df['col']), func(x=col_name), px.scatter(df, x='col')
    # Extract bare identifiers used as x= y= data= arguments
    for kw in ("x", "y", "z", "data", "hue", "color", "size"):
        patterns = [
            rf'{kw}\s*=\s*([a-zA-Z_]\w*)',  # x=variable_name
            rf'{kw}\s*=\s*["\']([^"\']+)["\']',  # x='column_name'
        ]
        for pat in patterns:
            for m in re.finditer(pat, source):
                variables.add(m.group(1))

    # Also capture the first positional arg to common plot functions
    for func in ("plt.plot", "plt.scatter", "plt.bar", "sns.lineplot",
                 "sns.scatterplot", "sns.heatmap"):
        pat = rf'{re.escape(func)}\s*\(\s*([a-zA-Z_]\w*)'
        for m in re.finditer(pat, source):
            variables.add(m.group(1))

    return sorted(variables)


def _extract_series_names(source: str) -> List[str]:
    """Extract series/legend labels from label= arguments."""
    labels = []
    for m in re.finditer(r'label\s*=\s*["\']([^"\']+)["\']', source):
        labels.append(m.group(1))
    return labels


def _extract_color_info(source: str) -> Optional[str]:
    """Extract color/colormap information."""
    # cmap= argument
    m = re.search(r'cmap\s*=\s*["\']([^"\']+)["\']', source)
    if m:
        return f"colormap: {m.group(1)}"
    m = re.search(r'color\s*=\s*["\']([^"\']+)["\']', source)
    if m:
        return f"color: {m.group(1)}"
    return None


def _extract_figure_size(source: str) -> Optional[str]:
    """Extract figure size if set."""
    m = re.search(r'figsize\s*=\s*\((\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\)', source)
    if m:
        return f"{m.group(1)}x{m.group(2)} inches"
    return None


def describe_cell_visualization(cell: Any, cell_index: int) -> PlotDescription:
    """Generate a PlotDescription for *cell*.

    Analyses both the source code and the actual outputs (if present).
    """
    source = cell.source if hasattr(cell, "source") else ""
    desc = PlotDescription(cell_index=cell_index)

    desc.library = detect_library(source)
    desc.chart_type = detect_chart_type(source)
    desc.has_rendered_output = has_visual_output(cell)

    # Extract metadata from source
    desc.title = (
        _extract_string_arg(source, r"plt\.title\s*\(")
        or _extract_string_arg(source, r"\.update_layout\s*\(.*?title")
        or _extract_string_arg(source, r'title\s*=\s*')
    )
    desc.x_label = (
        _extract_string_arg(source, r"plt\.xlabel\s*\(")
        or _extract_string_arg(source, r"ax\.set_xlabel\s*\(")
        or _extract_string_arg(source, r'x_label\s*=\s*')
        or _extract_string_arg(source, r'labels\s*=\s*\{[^}]*"x"\s*:\s*')
    )
    desc.y_label = (
        _extract_string_arg(source, r"plt\.ylabel\s*\(")
        or _extract_string_arg(source, r"ax\.set_ylabel\s*\(")
        or _extract_string_arg(source, r'y_label\s*=\s*')
        or _extract_string_arg(source, r'labels\s*=\s*\{[^}]*"y"\s*:\s*')
    )
    desc.data_variables = _extract_variable_names(source)
    desc.series_names = _extract_series_names(source)
    desc.color_info = _extract_color_info(source)
    desc.figure_size = _extract_figure_size(source)
    desc.is_interactive = desc.library in ("plotly", "bokeh", "altair")

    # Collect output MIME types
    for out in getattr(cell, "outputs", []):
        if out.output_type in ("execute_result", "display_data"):
            for mime in getattr(out, "data", {}).keys():
                if mime not in desc.output_mimes:
                    desc.output_mimes.append(mime)

    # Build a human-readable source summary
    lines = [l for l in source.splitlines() if l.strip() and not l.strip().startswith("#")]
    desc.source_summary = lines[0][:120] if lines else "(empty)"

    # Compose the natural-language description
    parts = []
    if desc.chart_type:
        chart_name = desc.chart_type.replace("_", " ")
        parts.append(f"A {chart_name}")
    else:
        parts.append("A visualization")

    if desc.library:
        parts[-1] += f" created with {desc.library}"

    if desc.title:
        parts.append(f"titled '{desc.title}'")

    if desc.x_label and desc.y_label:
        parts.append(f"with x-axis '{desc.x_label}' and y-axis '{desc.y_label}'")
    elif desc.x_label:
        parts.append(f"with x-axis '{desc.x_label}'")
    elif desc.y_label:
        parts.append(f"with y-axis '{desc.y_label}'")

    if desc.series_names:
        parts.append(f"showing {len(desc.series_names)} series: {', '.join(desc.series_names[:5])}")
    elif desc.data_variables:
        parts.append(f"using variables: {', '.join(desc.data_variables[:5])}")

    if desc.color_info:
        parts.append(f"({desc.color_info})")

    if desc.is_interactive:
        parts.append("[interactive]")

    if not desc.has_rendered_output:
        parts.append("[no rendered output stored — cell may need to be executed]")

    desc.description = ". ".join(parts) + "."
    return desc
