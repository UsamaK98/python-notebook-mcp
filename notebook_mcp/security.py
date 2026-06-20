"""
Path security utilities for the Notebook MCP server.

Provides workspace-jail enforcement (CWE-22 path traversal protection) and
Git-Bash / Unix-style path conversion on Windows.
"""

import os
import sys
import re
from functools import wraps
from typing import Callable

from notebook_mcp import config


def convert_unix_path(path: str) -> str:
    """Convert Unix-style Git-Bash paths (e.g. /d/Projects) to Windows paths.

    Only active on win32; a no-op on every other platform.
    """
    if sys.platform != "win32":
        return path

    match = re.match(r"^/([a-zA-Z])(/.*)?$", path)
    if match:
        drive_letter = match.group(1).upper()
        remainder = (match.group(2) or "").replace("/", "\\")
        if not remainder:
            remainder = "\\"
        return f"{drive_letter}:{remainder}"
    return path


def resolve_path(path: str) -> str:
    """Resolve *path* to an absolute canonical path inside the workspace.

    Steps:
    1. Validate non-empty string input.
    2. Convert Git-Bash / Unix-style drive paths on Windows.
    3. Resolve relative paths against WORKSPACE_DIR.
    4. Canonicalise with os.path.realpath() (symlinks + ../ expansion).
    5. Assert result sits inside workspace root.

    Raises:
        ValueError:      if path is empty or not a string.
        PermissionError: if resolved path escapes the workspace root.
    """
    if not isinstance(path, str) or not path.strip():
        raise ValueError("ERROR: a non-empty path string is required.")

    path = convert_unix_path(path)

    workspace_dir = config.get_workspace()
    if os.path.isabs(path):
        real_target = os.path.realpath(path)
    else:
        real_target = os.path.realpath(os.path.join(workspace_dir, path))

    if config.is_initialized():
        real_workspace = os.path.realpath(workspace_dir)
        norm_workspace = os.path.normcase(real_workspace)
        norm_target = os.path.normcase(real_target)

        try:
            contained = (
                norm_target == norm_workspace
                or os.path.commonpath([norm_workspace, norm_target]) == norm_workspace
            )
        except ValueError:
            contained = False

        if not contained:
            raise PermissionError(
                f"Path '{path}' resolves to '{real_target}' which is outside "
                f"the workspace root '{real_workspace}'. "
                "Absolute paths and traversal sequences (../) that escape the "
                "workspace are not permitted. (CWE-22 Path Traversal protection.)"
            )

    return real_target


def require_workspace(func: Callable) -> Callable:
    """Decorator that ensures the workspace has been initialized before a tool runs."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not config.is_initialized():
            raise ValueError(
                "ERROR: Workspace not initialized. Please call "
                "initialize_workspace() first with the FULL ABSOLUTE PATH "
                "to the directory where your notebook files are located."
            )
        return func(*args, **kwargs)
    return wrapper
