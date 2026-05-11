import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class ResolvePathTest(unittest.TestCase):
    def setUp(self):
        import server

        self.server = server
        self._scratch = tempfile.mkdtemp(prefix="nb_mcp_test_")
        self.workspace = os.path.join(self._scratch, "ws")
        os.makedirs(self.workspace)
        self._saved_dir = server.WORKSPACE_DIR
        self._saved_flag = server.WORKSPACE_INITIALIZED
        server.WORKSPACE_DIR = self.workspace
        server.WORKSPACE_INITIALIZED = True

    def tearDown(self):
        self.server.WORKSPACE_DIR = self._saved_dir
        self.server.WORKSPACE_INITIALIZED = self._saved_flag
        shutil.rmtree(self._scratch, ignore_errors=True)

    def test_relative_traversal_blocked(self):
        with self.assertRaisesRegex(ValueError, "outside the initialized workspace"):
            self.server.resolve_path("../outside.ipynb")

    def test_absolute_path_outside_blocked(self):
        with self.assertRaisesRegex(ValueError, "outside the initialized workspace"):
            self.server.resolve_path("/tmp/external_outside.ipynb")

    def test_normalized_escape_blocked(self):
        with self.assertRaisesRegex(ValueError, "outside the initialized workspace"):
            self.server.resolve_path("subdir/../../escape.ipynb")

    def test_dot_prefixed_escape_blocked(self):
        with self.assertRaisesRegex(ValueError, "outside the initialized workspace"):
            self.server.resolve_path("./a/../../../escape.ipynb")

    def test_empty_path_rejected(self):
        with self.assertRaisesRegex(ValueError, "non-empty path"):
            self.server.resolve_path("")

    def test_create_new_notebook_refuses_traversal(self):
        with self.assertRaisesRegex(ValueError, "outside the initialized workspace"):
            self.server.create_new_notebook("../escaped_via_relpath.ipynb", title="poc")
        escaped = os.path.realpath(os.path.join(self.workspace, "..", "escaped_via_relpath.ipynb"))
        self.assertFalse(os.path.exists(escaped))

    def test_simple_name_allowed(self):
        result = self.server.resolve_path("notebook.ipynb")
        self.assertEqual(result, os.path.join(os.path.realpath(self.workspace), "notebook.ipynb"))

    def test_nested_name_allowed(self):
        result = self.server.resolve_path("sub/dir/n.ipynb")
        self.assertTrue(result.startswith(os.path.realpath(self.workspace) + os.sep))

    def test_dot_prefix_inside_allowed(self):
        result = self.server.resolve_path("./foo.ipynb")
        self.assertEqual(result, os.path.join(os.path.realpath(self.workspace), "foo.ipynb"))


if __name__ == "__main__":
    unittest.main()
