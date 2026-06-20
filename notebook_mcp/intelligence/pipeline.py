"""
Notebook pipeline analysis: statically infer data flow between cells
and extract a dependency graph (DAG).
"""

import ast
import re
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from notebook_mcp.core.notebook_io import get_notebook_content

log = logging.getLogger(__name__)


def _extract_assignments(source: str) -> Set[str]:
    """Return the set of variable names assigned in *source*."""
    assigned = set()
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                targets = []
                if isinstance(node, ast.Assign):
                    targets = node.targets
                elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
                    targets = [node.target]
                for t in targets:
                    if isinstance(t, ast.Name):
                        assigned.add(t.id)
                    elif isinstance(t, ast.Tuple):
                        for elt in t.elts:
                            if isinstance(elt, ast.Name):
                                assigned.add(elt.id)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                assigned.add(node.name)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assigned.add(alias.asname or alias.name.split(".")[0])
                else:
                    for alias in node.names:
                        assigned.add(alias.asname or alias.name)
    except SyntaxError:
        # Fall back to regex for cells with IPython magics
        for m in re.finditer(r"^([a-zA-Z_]\w*)\s*=", source, re.MULTILINE):
            assigned.add(m.group(1))
    return assigned


def _extract_reads(source: str, all_vars: Set[str]) -> Set[str]:
    """Return variables from *all_vars* that are read (but not assigned first) in *source*."""
    reads = set()
    # Simple heuristic: if a known var name appears as a token in source
    for var in all_vars:
        # Match var as a whole word that's not on the left side of =
        pattern = rf'\b{re.escape(var)}\b'
        if re.search(pattern, source):
            reads.add(var)
    return reads


def _classify_cell(source: str, assigned: Set[str], reads: Set[str]) -> str:
    """Classify a cell's role in the pipeline."""
    src_lower = source.lower()

    # Data loading
    if any(kw in src_lower for kw in ("read_csv", "read_excel", "read_parquet",
                                       "read_json", "load_dataset", "open(",
                                       "glob(", "listdir(")):
        return "data_loading"

    # Data saving
    if any(kw in src_lower for kw in ("to_csv", "to_excel", "to_parquet",
                                       "savefig", "joblib.dump", "pickle.dump",
                                       "torch.save", "model.save")):
        return "data_export"

    # Visualization
    if any(kw in src_lower for kw in ("plt.", "sns.", "px.", "bokeh", "altair",
                                       ".plot(", "show(", "display(")):
        return "visualization"

    # Model training
    if any(kw in src_lower for kw in (".fit(", ".train(", "train_model",
                                       "model.compile", "optimizer")):
        return "model_training"

    # Model evaluation
    if any(kw in src_lower for kw in (".predict(", ".evaluate(", ".score(",
                                       "accuracy", "confusion_matrix",
                                       "classification_report")):
        return "model_evaluation"

    # Data transformation
    if any(kw in src_lower for kw in ("dropna", "fillna", "merge", "concat",
                                       "groupby", "apply", "transform",
                                       "encode", "scale", "normalize",
                                       "reshape", "pivot")):
        return "data_transformation"

    # Exploration
    if any(kw in src_lower for kw in ("head(", "tail(", "describe(", "info(",
                                       "shape", "dtypes", "value_counts",
                                       "corr(", "nunique")):
        return "exploration"

    # Configuration / imports
    if all(line.strip().startswith(("import ", "from ", "#", ""))
           for line in source.splitlines() if line.strip()):
        return "imports"

    return "processing"


def get_notebook_pipeline(filepath: str) -> Dict[str, Any]:
    """Analyse a notebook and return a data-flow pipeline description.

    Returns:
        Dict with:
          - stages: list of stage dicts (cell_index, role, produces, consumes,
            description, source_preview)
          - data_flow: dict mapping variable -> list of cell indices that
            produce or consume it
          - entry_points: cell indices that load/create data
          - exit_points: cell indices that save/export data
          - summary: brief text description of the pipeline
    """
    nb = get_notebook_content(filepath)
    stages = []
    all_assigned: Dict[int, Set[str]] = {}

    # First pass: collect all assigned variables per cell
    global_vars: Set[str] = set()
    for idx, cell in enumerate(nb.cells):
        if cell.cell_type != "code":
            continue
        assigned = _extract_assignments(cell.source)
        all_assigned[idx] = assigned
        global_vars.update(assigned)

    # Second pass: build pipeline stages
    produced_by: Dict[str, List[int]] = {}  # var -> cells that assign it
    consumed_by: Dict[str, List[int]] = {}  # var -> cells that read it

    for idx, cell in enumerate(nb.cells):
        if cell.cell_type != "code":
            continue
        source = cell.source.strip()
        if not source:
            continue

        assigned = all_assigned.get(idx, set())
        reads = _extract_reads(source, global_vars - assigned)

        role = _classify_cell(source, assigned, reads)

        # Track data flow
        for var in assigned:
            produced_by.setdefault(var, []).append(idx)
        for var in reads:
            consumed_by.setdefault(var, []).append(idx)

        # Build a preview of the cell
        lines = [l for l in source.splitlines() if l.strip()]
        preview = lines[0][:100] if lines else "(empty)"

        stages.append({
            "cell_index": idx,
            "role": role,
            "produces": sorted(assigned - {"_", "__"}),
            "consumes": sorted(reads),
            "source_preview": preview,
        })

    # Identify entry and exit points
    entry_points = [s["cell_index"] for s in stages if s["role"] == "data_loading"]
    exit_points = [s["cell_index"] for s in stages if s["role"] == "data_export"]

    # Build a simplified data flow (only meaningful variables)
    # Filter out trivial single-char or private vars
    data_flow = {}
    for var, producers in produced_by.items():
        if len(var) <= 1 or var.startswith("_"):
            continue
        consumers = consumed_by.get(var, [])
        if producers or consumers:
            data_flow[var] = {
                "produced_by_cells": producers,
                "consumed_by_cells": consumers,
            }

    # Build a text summary
    role_counts: Dict[str, int] = {}
    for s in stages:
        role_counts[s["role"]] = role_counts.get(s["role"], 0) + 1

    role_parts = [f"{count} {role.replace('_', ' ')} cell(s)"
                  for role, count in sorted(role_counts.items()) if count]
    summary = f"Notebook with {len(stages)} code cell(s): " + ", ".join(role_parts) + "."
    if entry_points:
        summary += f" Data loaded in cell(s): {entry_points}."
    if exit_points:
        summary += f" Data exported in cell(s): {exit_points}."

    return {
        "stages": stages,
        "data_flow": data_flow,
        "entry_points": entry_points,
        "exit_points": exit_points,
        "role_summary": role_counts,
        "summary": summary,
    }
