"""
Tests for resolve_path() workspace containment in server.py.

Covers:
- Empty / non-string input rejection
- Relative traversal escape (../)
- Absolute path outside workspace
- Normalised escape (foo/../../../outside)
- Dot-prefixed escape (./../outside)
- Symlink-based escape (symlink inside workspace → outside directory)
- Valid simple filename
- Valid nested relative path
- Valid dot-prefixed filename inside workspace
- End-to-end: create_new_notebook() rejects a traversal path

No third-party dependencies — stdlib unittest only.
"""
import os
import sys
import tempfile
import shutil
import unittest

# ---------------------------------------------------------------------------
# Import server module — add its directory to sys.path if needed
# ---------------------------------------------------------------------------
_SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)

import server


class TestResolvePath(unittest.TestCase):
    """Unit tests for server.resolve_path() workspace jail."""

    def setUp(self):
        """Create an isolated temp workspace and a scratch dir outside it."""
        self._scratch = tempfile.mkdtemp(prefix="nb_mcp_test_scratch_")
        self.workspace = tempfile.mkdtemp(
            prefix="nb_mcp_test_ws_", dir=self._scratch
        )
        # Patch module-level globals so the jail is active
        self._orig_workspace = server.WORKSPACE_DIR
        self._orig_initialized = server.WORKSPACE_INITIALIZED
        server.WORKSPACE_DIR = self.workspace
        server.WORKSPACE_INITIALIZED = True

    def tearDown(self):
        """Restore globals and remove temp dirs."""
        server.WORKSPACE_DIR = self._orig_workspace
        server.WORKSPACE_INITIALIZED = self._orig_initialized
        shutil.rmtree(self._scratch, ignore_errors=True)

    # ------------------------------------------------------------------
    # Escape-vector tests — all must raise PermissionError (or ValueError
    # for the input-validation cases)
    # ------------------------------------------------------------------

    def test_empty_string_raises(self):
        with self.assertRaises(ValueError):
            server.resolve_path("")

    def test_whitespace_only_raises(self):
        with self.assertRaises(ValueError):
            server.resolve_path("   ")

    def test_non_string_raises(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            server.resolve_path(None)  # type: ignore[arg-type]

    def test_relative_traversal_blocked(self):
        """../outside.ipynb must not escape the workspace."""
        with self.assertRaises(PermissionError):
            server.resolve_path("../outside.ipynb")

    def test_absolute_path_outside_blocked(self):
        """An absolute path that points outside the workspace is rejected."""
        outside = os.path.join(self._scratch, "outside.ipynb")
        with self.assertRaises(PermissionError):
            server.resolve_path(outside)

    def test_normalised_traversal_blocked(self):
        """A path like foo/../../../outside must still be caught after realpath."""
        with self.assertRaises(PermissionError):
            server.resolve_path("foo/../../../outside.ipynb")

    def test_dot_prefixed_traversal_blocked(self):
        with self.assertRaises(PermissionError):
            server.resolve_path("./../outside.ipynb")

    def test_sibling_prefix_not_confused(self):
        """A workspace named /ws must not accept /ws-evil as being inside it.

        This guards against a naive ``startswith`` containment check.
        """
        # Create a sibling dir whose name starts with the workspace basename
        sibling = self.workspace.rstrip(os.sep) + "-evil"
        os.makedirs(sibling, exist_ok=True)
        sibling_file = os.path.join(sibling, "evil.ipynb")
        try:
            with self.assertRaises(PermissionError):
                server.resolve_path(sibling_file)
        finally:
            shutil.rmtree(sibling, ignore_errors=True)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks not supported on this platform")
    def test_symlink_escape_blocked(self):
        """A symlink inside the workspace that points outside must be rejected.

        This directly exercises the realpath-based containment guarantee.
        """
        outside_target = os.path.join(self._scratch, "outside_target")
        os.makedirs(outside_target, exist_ok=True)
        evil_link = os.path.join(self.workspace, "evil_link")
        try:
            os.symlink(outside_target, evil_link)
        except (OSError, NotImplementedError):
            self.skipTest("Cannot create symlink in this environment")

        with self.assertRaises(PermissionError):
            server.resolve_path("evil_link/secret.ipynb")

    # ------------------------------------------------------------------
    # Positive tests — valid in-workspace paths must succeed
    # ------------------------------------------------------------------

    def test_simple_filename_resolves(self):
        result = server.resolve_path("notebook.ipynb")
        expected = os.path.realpath(os.path.join(self.workspace, "notebook.ipynb"))
        self.assertEqual(result, expected)

    def test_nested_relative_path_resolves(self):
        result = server.resolve_path("subdir/nested.ipynb")
        expected = os.path.realpath(
            os.path.join(self.workspace, "subdir", "nested.ipynb")
        )
        self.assertEqual(result, expected)

    def test_dot_prefixed_inside_workspace_resolves(self):
        """A filename starting with a dot that stays inside the workspace is fine."""
        result = server.resolve_path(".hidden_notebook.ipynb")
        expected = os.path.realpath(
            os.path.join(self.workspace, ".hidden_notebook.ipynb")
        )
        self.assertEqual(result, expected)

    def test_absolute_inside_workspace_resolves(self):
        """An absolute path that stays inside the workspace is permitted."""
        inside = os.path.join(self.workspace, "allowed.ipynb")
        result = server.resolve_path(inside)
        self.assertEqual(result, os.path.realpath(inside))

    # ------------------------------------------------------------------
    # End-to-end: create_new_notebook must reject traversal paths
    # ------------------------------------------------------------------

    def test_create_new_notebook_blocks_traversal(self):
        """create_new_notebook must not create a file outside the workspace."""
        escaped = os.path.join(self._scratch, "poc.ipynb")
        with self.assertRaises(PermissionError):
            server.create_new_notebook("../poc.ipynb")
        self.assertFalse(
            os.path.exists(escaped),
            "create_new_notebook must not have written the escaped file",
        )


if __name__ == "__main__":
    unittest.main()
