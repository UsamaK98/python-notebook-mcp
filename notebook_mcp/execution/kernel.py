"""
Kernel lifecycle management for the Notebook MCP execution engine.

Uses jupyter_client (optional dependency) to start, stop, restart, and
inspect kernels. One kernel per notebook filepath.

If jupyter_client is not installed, all functions raise ImportError with
a clear install instruction.
"""

import logging
import os
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

# Registry mapping canonical notebook paths to active kernel managers
_kernels: Dict[str, Any] = {}


def _require_jupyter_client():
    """Raise ImportError if jupyter_client is not available."""
    try:
        import jupyter_client  # noqa: F401
        return jupyter_client
    except ImportError:
        raise ImportError(
            "jupyter_client is not installed. Cell execution requires it.\n"
            "Install with: pip install jupyter_client ipykernel\n"
            "Or: uv pip install jupyter_client ipykernel"
        )


def _canonical(filepath: str) -> str:
    """Return a canonical (resolved) path for use as a registry key."""
    return os.path.realpath(filepath)


def get_or_start_kernel(
    filepath: str,
    kernel_name: Optional[str] = None,
    cwd: Optional[str] = None,
) -> Any:
    """Return an existing kernel client for *filepath*, or start a new one.

    Args:
        filepath:    Canonical notebook path (used as registry key).
        kernel_name: Jupyter kernel spec name (e.g. 'python3'). Auto-detects
                     from notebook metadata when None.
        cwd:         Working directory for the kernel process.

    Returns:
        A (KernelManager, KernelClient) tuple.
    """
    _require_jupyter_client()
    from jupyter_client import KernelManager

    key = _canonical(filepath)
    if key in _kernels:
        km, kc = _kernels[key]
        if km.is_alive():
            log.debug("Reusing existing kernel for %s", key)
            return km, kc
        else:
            log.info("Kernel for %s died; restarting.", key)
            del _kernels[key]

    km = KernelManager(kernel_name=kernel_name or "python3")
    if cwd:
        km.cwd = cwd
    elif filepath:
        km.cwd = os.path.dirname(os.path.realpath(filepath)) or os.getcwd()

    log.info("Starting kernel '%s' for %s", km.kernel_name, key)
    km.start_kernel()
    kc = km.client()
    kc.start_channels()
    kc.wait_for_ready(timeout=60)
    _kernels[key] = (km, kc)
    log.info("Kernel ready for %s", key)
    return km, kc


def restart_kernel(filepath: str) -> str:
    """Restart the kernel associated with *filepath*."""
    _require_jupyter_client()
    key = _canonical(filepath)
    if key in _kernels:
        km, kc = _kernels[key]
        log.info("Restarting kernel for %s", key)
        kc.stop_channels()
        km.restart_kernel(now=True)
        kc = km.client()
        kc.start_channels()
        kc.wait_for_ready(timeout=60)
        _kernels[key] = (km, kc)
        return f"Kernel restarted for {key}"
    else:
        # Start fresh
        get_or_start_kernel(filepath)
        return f"New kernel started for {key}"


def interrupt_kernel(filepath: str) -> str:
    """Send an interrupt signal to the kernel for *filepath*."""
    _require_jupyter_client()
    key = _canonical(filepath)
    if key not in _kernels:
        return f"No running kernel found for {key}"
    km, _ = _kernels[key]
    if km.is_alive():
        km.interrupt_kernel()
        return f"Interrupt sent to kernel for {key}"
    return f"Kernel for {key} is not running."


def shutdown_kernel(filepath: str) -> str:
    """Shut down the kernel for *filepath*."""
    _require_jupyter_client()
    key = _canonical(filepath)
    if key not in _kernels:
        return f"No running kernel found for {key}"
    km, kc = _kernels[key]
    try:
        kc.stop_channels()
        km.shutdown_kernel(now=True)
    except Exception as e:
        log.warning("Error shutting down kernel: %s", e)
    del _kernels[key]
    return f"Kernel shut down for {key}"


def get_kernel_status(filepath: str) -> Dict[str, Any]:
    """Return the status of the kernel for *filepath*."""
    key = _canonical(filepath)
    if key not in _kernels:
        return {
            "status": "not_started",
            "filepath": key,
            "kernel_name": None,
            "is_alive": False,
        }

    try:
        _require_jupyter_client()
    except ImportError:
        return {
            "status": "jupyter_client_not_installed",
            "filepath": key,
            "kernel_name": None,
            "is_alive": False,
        }

    km, kc = _kernels[key]
    alive = km.is_alive()
    return {
        "status": "running" if alive else "dead",
        "filepath": key,
        "kernel_name": km.kernel_name,
        "is_alive": alive,
    }


def list_active_kernels() -> Dict[str, Any]:
    """Return a summary of all active kernels."""
    result = {}
    for key, (km, _) in _kernels.items():
        try:
            alive = km.is_alive()
        except Exception:
            alive = False
        result[key] = {
            "kernel_name": km.kernel_name,
            "is_alive": alive,
        }
    return result
