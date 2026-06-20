"""
Tests for resolve_path() workspace containment.

Covers:
- Empty / non-string input rejection
- Relative traversal escape (../)
- Absolute path outside workspace
- Normalised escape (foo/../../../outside)
- Symlink-based escape (symlink inside workspace -> outside)
- Valid simple filename
- Valid nested relative path
- Valid dot-prefixed filename inside workspace
"""

import os
import sys
import tempfile
import shutil
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from notebook_mcp import config
from notebook_mcp.security import resolve_path


class TestResolvePath(unittest.TestCase):
    """Unit tests for resolve_path() workspace jail."""

    def setUp(self):
        self._scratch = tempfile.mkdtemp(prefix="nb_mcp_test_scratch_")
        self.workspace = tempfile.mkdtemp(
            prefix="nb_mcp_test_ws_", dir=self._scratch
        )
        config.set_workspace(self.workspace)

    def tearDown(self):
        try:
            shutil.rmtree(self._scratch, ignore_errors=True)
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # Rejection cases
    # -----------------------------------------------------------------------

    def test_empty_string_raises(self):
        with self.assertRaises(ValueError):
            resolve_path("")

    def test_whitespace_only_raises(self):
        with self.assertRaises(ValueError):
            resolve_path("   ")

    def test_none_raises(self):
        with self.assertRaises((ValueError, TypeError, AttributeError)):
            resolve_path(None)

    def test_traversal_escape_raises(self):
        with self.assertRaises(PermissionError):
            resolve_path("../outside.ipynb")

    def test_absolute_outside_raises(self):
        outside = os.path.join(self._scratch, "evil.ipynb")
        with self.assertRaises(PermissionError):
            resolve_path(outside)

    def test_normalised_traversal_raises(self):
        with self.assertRaises(PermissionError):
            resolve_path("subdir/../../outside")

    def test_dot_prefix_traversal_raises(self):
        with self.assertRaises(PermissionError):
            resolve_path("./../outside")

    def test_sibling_prefix_raises(self):
        """Paths like workspace_evil/ should NOT be treated as inside workspace."""
        sibling = self.workspace.rstrip(os.sep) + "_evil"
        try:
            os.makedirs(sibling, exist_ok=True)
            with self.assertRaises(PermissionError):
                resolve_path(os.path.join(sibling, "notebook.ipynb"))
        finally:
            shutil.rmtree(sibling, ignore_errors=True)

    @unittest.skipIf(sys.platform == "win32", "symlinks require elevated privileges on Windows")
    def test_symlink_escape_raises(self):
        outside = tempfile.mkdtemp(dir=self._scratch)
        link = os.path.join(self.workspace, "link_to_outside")
        os.symlink(outside, link)
        with self.assertRaises(PermissionError):
            resolve_path("link_to_outside/evil.ipynb")

    # -----------------------------------------------------------------------
    # Valid cases
    # -----------------------------------------------------------------------

    def test_valid_simple_filename(self):
        result = resolve_path("notebook.ipynb")
        expected = os.path.realpath(os.path.join(self.workspace, "notebook.ipynb"))
        self.assertEqual(result, expected)

    def test_valid_nested_path(self):
        result = resolve_path("sub/dir/notebook.ipynb")
        expected = os.path.realpath(os.path.join(self.workspace, "sub", "dir", "notebook.ipynb"))
        self.assertEqual(result, expected)

    def test_valid_dot_prefixed_filename(self):
        result = resolve_path(".hidden_notebook.ipynb")
        expected = os.path.realpath(os.path.join(self.workspace, ".hidden_notebook.ipynb"))
        self.assertEqual(result, expected)

    def test_valid_absolute_inside_workspace(self):
        target = os.path.join(self.workspace, "notebook.ipynb")
        result = resolve_path(target)
        self.assertEqual(result, os.path.realpath(target))

    def test_workspace_root_itself(self):
        """resolve_path('.') should return the workspace directory."""
        result = resolve_path(".")
        self.assertEqual(result, os.path.realpath(self.workspace))


if __name__ == "__main__":
    unittest.main()
