"""
Cell execution engine: executes cells via a running Jupyter kernel and
captures all output types.
"""

import logging
import queue
import time
from typing import Any, Dict, List, Optional, Tuple

import nbformat
from nbformat.v4 import output as nboutput

from notebook_mcp.security import resolve_path
from notebook_mcp.core.notebook_io import (
    get_notebook_content,
    write_notebook_atomic,
    process_cell_output,
)
from notebook_mcp.execution.kernel import get_or_start_kernel

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 60  # seconds
MAX_OUTPUT_SIZE = 1024 * 1024  # 1 MB per output field


def _capture_outputs(kc: Any, msg_id: str, timeout: float) -> Tuple[List[Dict], bool, Optional[str]]:
    """Collect all output messages for *msg_id* from the iopub channel.

    Returns:
        (outputs, timed_out, error_message)
    """
    outputs = []
    timed_out = False
    error_message = None
    deadline = time.monotonic() + timeout

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            timed_out = True
            error_message = f"Cell execution timed out after {timeout}s."
            break

        try:
            msg = kc.get_iopub_msg(timeout=min(remaining, 1.0))
        except queue.Empty:
            continue
        except Exception as e:
            log.warning("Error reading iopub message: %s", e)
            break

        msg_type = msg["msg_type"]
        content = msg["content"]

        if msg_type == "stream":
            text = content.get("text", "")
            if len(text) > MAX_OUTPUT_SIZE:
                text = text[:MAX_OUTPUT_SIZE] + "\n[Output truncated]"
            outputs.append({
                "output_type": "stream",
                "name": content.get("name", "stdout"),
                "text": text,
            })

        elif msg_type in ("execute_result", "display_data"):
            data = content.get("data", {})
            for mime in ("image/png", "image/jpeg"):
                if mime in data and len(data[mime]) > MAX_OUTPUT_SIZE:
                    data[mime] = data[mime][:MAX_OUTPUT_SIZE]
            out = {
                "output_type": msg_type,
                "data": data,
                "metadata": content.get("metadata", {}),
            }
            if msg_type == "execute_result":
                out["execution_count"] = content.get("execution_count")
            outputs.append(out)

        elif msg_type == "error":
            outputs.append({
                "output_type": "error",
                "ename": content.get("ename", ""),
                "evalue": content.get("evalue", ""),
                "traceback": content.get("traceback", []),
            })
            error_message = f"{content.get('ename', 'Error')}: {content.get('evalue', '')}"

        elif msg_type == "status":
            if content.get("execution_state") == "idle":
                # Kernel finished executing this message
                break

    return outputs, timed_out, error_message


def _build_nb_outputs(raw_outputs: List[Dict]) -> List[nbformat.NotebookNode]:
    """Convert raw message dicts to nbformat output nodes."""
    nb_outputs = []
    for raw in raw_outputs:
        ot = raw.get("output_type")
        if ot == "stream":
            nb_outputs.append(nboutput.new_output(
                output_type="stream",
                name=raw["name"],
                text=raw["text"],
            ))
        elif ot in ("execute_result", "display_data"):
            kw = {"output_type": ot, "data": raw["data"], "metadata": raw["metadata"]}
            if ot == "execute_result":
                kw["execution_count"] = raw.get("execution_count")
            nb_outputs.append(nboutput.new_output(**kw))
        elif ot == "error":
            nb_outputs.append(nboutput.new_output(
                output_type="error",
                ename=raw["ename"],
                evalue=raw["evalue"],
                traceback=raw["traceback"],
            ))
    return nb_outputs


def execute_cell(
    filepath: str,
    cell_index: int,
    timeout: float = DEFAULT_TIMEOUT,
    save_outputs: bool = True,
) -> Dict[str, Any]:
    """Execute a single cell and return its outputs.

    Args:
        filepath:     Path to the notebook.
        cell_index:   Zero-based index of the cell to execute.
        timeout:      Execution timeout in seconds.
        save_outputs: If True, writes execution outputs back to the .ipynb file.

    Returns:
        Dict with: cell_index, execution_count, outputs, timed_out,
        error_message, duration_ms.
    """
    nb = get_notebook_content(filepath)
    n = len(nb.cells)
    if cell_index < 0 or cell_index >= n:
        raise IndexError(f"Cell index {cell_index} out of range (0–{n-1}).")

    cell = nb.cells[cell_index]
    if cell.cell_type != "code":
        return {
            "cell_index": cell_index,
            "skipped": True,
            "reason": f"Cell is '{cell.cell_type}', not 'code'.",
            "outputs": [],
        }

    source = cell.source.strip()
    if not source:
        return {
            "cell_index": cell_index,
            "skipped": True,
            "reason": "Cell is empty.",
            "outputs": [],
        }

    _, kc = get_or_start_kernel(filepath)

    t_start = time.monotonic()
    msg_id = kc.execute(source)
    raw_outputs, timed_out, error_message = _capture_outputs(kc, msg_id, timeout)
    duration_ms = int((time.monotonic() - t_start) * 1000)

    # Determine execution count from outputs
    exec_count = None
    for out in raw_outputs:
        if out.get("output_type") == "execute_result" and out.get("execution_count"):
            exec_count = out["execution_count"]
            break

    if save_outputs:
        nb2 = get_notebook_content(filepath)
        nb2.cells[cell_index].outputs = _build_nb_outputs(raw_outputs)
        nb2.cells[cell_index].execution_count = exec_count
        resolved_path = resolve_path(filepath)
        write_notebook_atomic(nb2, resolved_path)

    serialised_outputs = []
    for raw in raw_outputs:
        node = nbformat.from_dict(raw)
        node.output_type = raw.get("output_type", "")
        serialised_outputs.append(process_cell_output(node))

    return {
        "cell_index": cell_index,
        "execution_count": exec_count,
        "outputs": serialised_outputs,
        "timed_out": timed_out,
        "error_message": error_message,
        "duration_ms": duration_ms,
    }


def execute_range(
    filepath: str,
    start_index: int,
    end_index: int,
    timeout: float = DEFAULT_TIMEOUT,
    stop_on_error: bool = True,
) -> List[Dict[str, Any]]:
    """Execute cells from *start_index* to *end_index* (inclusive).

    Args:
        filepath:      Path to the notebook.
        start_index:   First cell to execute (0-based).
        end_index:     Last cell to execute (0-based, inclusive).
        timeout:       Per-cell execution timeout in seconds.
        stop_on_error: If True, stops execution when a cell errors.

    Returns:
        List of per-cell result dicts (same format as execute_cell).
    """
    nb = get_notebook_content(filepath)
    n = len(nb.cells)
    if start_index < 0 or start_index >= n:
        raise IndexError(f"start_index {start_index} out of range (0–{n-1}).")
    if end_index < start_index or end_index >= n:
        raise IndexError(f"end_index {end_index} out of range ({start_index}–{n-1}).")

    results = []
    for idx in range(start_index, end_index + 1):
        result = execute_cell(filepath, idx, timeout=timeout)
        results.append(result)
        if stop_on_error and result.get("error_message"):
            log.warning("Stopping execution at cell %d due to error.", idx)
            break

    return results


def execute_all(
    filepath: str,
    timeout: float = DEFAULT_TIMEOUT,
    stop_on_error: bool = True,
) -> Dict[str, Any]:
    """Execute all cells in the notebook.

    Returns:
        Dict with: total_cells, executed, skipped, errored, results,
        total_duration_ms.
    """
    nb = get_notebook_content(filepath)
    n = len(nb.cells)
    if n == 0:
        return {"total_cells": 0, "executed": 0, "skipped": 0, "errored": 0, "results": []}

    results = execute_range(filepath, 0, n - 1, timeout=timeout, stop_on_error=stop_on_error)
    executed = sum(1 for r in results if not r.get("skipped"))
    skipped = sum(1 for r in results if r.get("skipped"))
    errored = sum(1 for r in results if r.get("error_message"))
    total_ms = sum(r.get("duration_ms", 0) for r in results)

    return {
        "total_cells": n,
        "executed": executed,
        "skipped": skipped,
        "errored": errored,
        "total_duration_ms": total_ms,
        "results": results,
    }


def inspect_variable(filepath: str, variable_name: str) -> Dict[str, Any]:
    """Inspect a variable in the kernel's namespace.

    Returns:
        Dict with: name, type, repr, shape (for arrays/DataFrames), columns,
        dtype, length, error.
    """
    _, kc = get_or_start_kernel(filepath)

    # Execute an inspection snippet
    inspection_code = f"""
import json as _json
_var = {variable_name!r}
try:
    _obj = eval(_var)
    _type = type(_obj).__name__
    _module = type(_obj).__module__
    _repr = repr(_obj)[:500]
    _info = {{"name": _var, "type": _type, "module": _module, "repr": _repr}}
    try:
        _info["length"] = len(_obj)
    except (TypeError, AttributeError):
        pass
    try:
        _info["shape"] = list(_obj.shape)
    except AttributeError:
        pass
    try:
        _info["dtype"] = str(_obj.dtype)
    except AttributeError:
        pass
    try:
        _info["columns"] = list(_obj.columns.tolist())
    except AttributeError:
        pass
    print("__NBMCP_INSPECT__:" + _json.dumps(_info))
except Exception as _e:
    print("__NBMCP_INSPECT__:" + _json.dumps({{"error": str(_e), "name": _var}}))
"""

    msg_id = kc.execute(inspection_code)
    raw_outputs, _, _ = _capture_outputs(kc, msg_id, timeout=10)

    for out in raw_outputs:
        text = out.get("text", "")
        if "__NBMCP_INSPECT__:" in text:
            import json
            try:
                payload = text.split("__NBMCP_INSPECT__:", 1)[1].strip()
                return json.loads(payload)
            except (json.JSONDecodeError, IndexError):
                pass

    return {"error": f"Could not inspect variable '{variable_name}'"}


def list_kernel_variables(filepath: str) -> Dict[str, Any]:
    """List all variables in the kernel's namespace with type and repr preview."""
    _, kc = get_or_start_kernel(filepath)

    list_code = """
import json as _json
_vars = {}
for _name, _obj in list(vars().items()):
    if _name.startswith('_'):
        continue
    try:
        _vars[_name] = {
            "type": type(_obj).__name__,
            "repr": repr(_obj)[:100],
        }
    except Exception:
        _vars[_name] = {"type": "unknown", "repr": "?"}
print("__NBMCP_VARS__:" + _json.dumps(_vars))
"""

    msg_id = kc.execute(list_code)
    raw_outputs, _, _ = _capture_outputs(kc, msg_id, timeout=10)

    for out in raw_outputs:
        text = out.get("text", "")
        if "__NBMCP_VARS__:" in text:
            import json
            try:
                payload = text.split("__NBMCP_VARS__:", 1)[1].strip()
                return {"variables": json.loads(payload)}
            except (json.JSONDecodeError, IndexError):
                pass

    return {"variables": {}, "error": "Could not list variables"}
