"""
Global configuration and workspace state for the Notebook MCP server.

All mutable server-level state lives here so modules can import it without
creating circular dependencies.
"""

import os
from typing import Optional

# ---------------------------------------------------------------------------
# Workspace state — mutated by initialize_workspace()
# ---------------------------------------------------------------------------

WORKSPACE_DIR: str = os.getcwd()
WORKSPACE_INITIALIZED: bool = False


def set_workspace(directory: str) -> None:
    """Set the global workspace directory and mark it as initialized."""
    global WORKSPACE_DIR, WORKSPACE_INITIALIZED
    WORKSPACE_DIR = directory
    WORKSPACE_INITIALIZED = True


def get_workspace() -> str:
    """Return the current workspace directory."""
    return WORKSPACE_DIR


def is_initialized() -> bool:
    """Return True if the workspace has been initialized."""
    return WORKSPACE_INITIALIZED
