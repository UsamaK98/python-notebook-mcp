"""
Notebook summarization: generate a concise, structured summary of a
notebook's purpose, methodology, data, and findings.

Works entirely from static analysis (no kernel required).
"""

import re
import logging
from typing import Any, Dict, List, Optional

from notebook_mcp.core.notebook_io import get_notebook_content
from notebook_mcp.core.search import notebook_outline, notebook_info
from notebook_mcp.visualization.detector import scan_notebook_visualizations

log = logging.getLogger(__name__)


def _collect_markdown_text(nb: Any) -> str:
    """Concatenate all markdown cell content."""
    parts = []
    for cell in nb.cells:
        if cell.cell_type == "markdown":
            parts.append(cell.source)
    return "\n\n".join(parts)


def _collect_import_statements(nb: Any) -> List[str]:
    """Extract all import statements from code cells."""
    imports = []
    for cell in nb.cells:
        if cell.cell_type == "code":
            for line in cell.source.splitlines():
                s = line.strip()
                if s.startswith("import ") or s.startswith("from "):
                    if s not in imports:
                        imports.append(s)
    return imports


def _infer_domain_from_imports(imports: List[str]) -> List[str]:
    """Infer the domain/purpose from import statements."""
    domain_hints = []
    import_text = "\n".join(imports)

    checks = [
        (["pandas", "numpy", "scipy"], "Data Analysis"),
        (["sklearn", "scikit", "xgboost", "lightgbm", "catboost"], "Machine Learning"),
        (["tensorflow", "keras", "torch", "pytorch"], "Deep Learning"),
        (["matplotlib", "seaborn", "plotly", "bokeh", "altair"], "Data Visualization"),
        (["nltk", "spacy", "transformers", "gensim", "text"], "Natural Language Processing"),
        (["cv2", "PIL", "torchvision", "skimage", "image"], "Computer Vision"),
        (["statsmodels", "scipy.stats", "pingouin"], "Statistical Analysis"),
        (["requests", "httpx", "urllib", "scrapy", "bs4"], "Web / API"),
        (["sqlalchemy", "psycopg2", "pymongo", "sqlite"], "Database"),
        (["fastapi", "flask", "django", "starlette"], "Web Framework"),
    ]

    for keywords, domain in checks:
        if any(kw in import_text for kw in keywords):
            domain_hints.append(domain)

    return domain_hints


def _extract_data_sources(nb: Any) -> List[str]:
    """Find file reads and data loading calls."""
    sources = []
    patterns = [
        r'pd\.read_csv\s*\(\s*["\']([^"\']+)["\']',
        r'pd\.read_excel\s*\(\s*["\']([^"\']+)["\']',
        r'pd\.read_parquet\s*\(\s*["\']([^"\']+)["\']',
        r'pd\.read_json\s*\(\s*["\']([^"\']+)["\']',
        r'open\s*\(\s*["\']([^"\']+)["\']',
        r'Path\s*\(\s*["\']([^"\']+)["\']',
        r'load_dataset\s*\(\s*["\']([^"\']+)["\']',
        r'torch\.load\s*\(\s*["\']([^"\']+)["\']',
        r'np\.load\s*\(\s*["\']([^"\']+)["\']',
    ]
    for cell in nb.cells:
        if cell.cell_type == "code":
            for pattern in patterns:
                for m in re.finditer(pattern, cell.source):
                    src = m.group(1)
                    if src not in sources:
                        sources.append(src)
    return sources


def _extract_output_targets(nb: Any) -> List[str]:
    """Find file saves and outputs."""
    targets = []
    patterns = [
        r'\.to_csv\s*\(\s*["\']([^"\']+)["\']',
        r'\.to_excel\s*\(\s*["\']([^"\']+)["\']',
        r'\.to_parquet\s*\(\s*["\']([^"\']+)["\']',
        r'\.to_json\s*\(\s*["\']([^"\']+)["\']',
        r'plt\.savefig\s*\(\s*["\']([^"\']+)["\']',
        r'torch\.save\s*\(.*?,\s*["\']([^"\']+)["\']',
        r'joblib\.dump\s*\(.*?,\s*["\']([^"\']+)["\']',
        r'pickle\.dump\s*\(.*?,.*?["\']([^"\']+)["\']',
    ]
    for cell in nb.cells:
        if cell.cell_type == "code":
            for pattern in patterns:
                for m in re.finditer(pattern, cell.source):
                    tgt = m.group(1)
                    if tgt not in targets:
                        targets.append(tgt)
    return targets


def _count_cell_errors(nb: Any) -> int:
    count = 0
    for cell in nb.cells:
        if cell.cell_type == "code":
            for out in getattr(cell, "outputs", []):
                if out.output_type == "error":
                    count += 1
    return count


def summarize_notebook(filepath: str, detail_level: str = "standard") -> Dict[str, Any]:
    """Generate a structured summary of the notebook.

    Args:
        filepath:     Path to the notebook.
        detail_level: 'brief', 'standard', or 'detailed'.

    Returns:
        Dict with structured summary fields.
    """
    nb = get_notebook_content(filepath)
    info = notebook_info(filepath)
    outline = notebook_outline(filepath)
    viz_list = scan_notebook_visualizations(nb)
    imports = _collect_import_statements(nb)
    domains = _infer_domain_from_imports(imports)
    data_sources = _extract_data_sources(nb)
    output_targets = _extract_output_targets(nb)
    error_count = _count_cell_errors(nb)
    markdown_text = _collect_markdown_text(nb)

    # Extract the notebook title from the first H1 heading
    title = None
    for entry in outline:
        if entry.get("kind") == "h1":
            title = entry["name"]
            break

    # Find key sections from headings
    sections = [e["name"] for e in outline if e.get("kind") in ("h1", "h2")]

    # Find all defined functions and classes
    functions = [e["name"] for e in outline if e.get("kind") == "function"]
    classes = [e["name"] for e in outline if e.get("kind") == "class"]

    # Build prose description from markdown
    prose_lines = []
    for line in markdown_text.splitlines():
        s = line.strip()
        if s and not s.startswith("#") and len(s) > 20:
            prose_lines.append(s)
        if len(prose_lines) >= 5:
            break

    summary = {
        "title": title or "(untitled)",
        "domain": domains if domains else ["(unknown)"],
        "overview": prose_lines[:3],
        "structure": {
            "total_cells": info["cell_count"],
            "code_cells": info["code_cells"],
            "markdown_cells": info["markdown_cells"],
            "sections": sections[:10],
        },
        "data": {
            "input_sources": data_sources[:10],
            "output_targets": output_targets[:10],
        },
        "operations": {
            "libraries_used": [
                imp.replace("import ", "").replace("from ", "").split(" ")[0]
                for imp in imports[:20]
                if not imp.startswith("from")
            ],
            "functions_defined": functions[:10],
            "classes_defined": classes[:10],
        },
        "visualizations": {
            "count": len(viz_list),
            "types": list({v.get("chart_type") for v in viz_list if v.get("chart_type")}),
            "libraries": list({v.get("library") for v in viz_list if v.get("library")}),
        },
        "execution_state": {
            "cells_with_output": info["cells_with_output"],
            "has_errors": info["has_errors"],
            "error_count": error_count,
        },
        "kernel": {
            "name": info["kernel_name"],
            "language": info["language"],
        },
    }

    if detail_level == "brief":
        return {
            "title": summary["title"],
            "domain": summary["domain"],
            "cell_count": info["cell_count"],
            "visualizations": len(viz_list),
            "has_errors": info["has_errors"],
            "data_sources": data_sources[:3],
        }

    if detail_level == "detailed":
        summary["imports"] = imports[:30]
        summary["full_outline"] = outline

    return summary
