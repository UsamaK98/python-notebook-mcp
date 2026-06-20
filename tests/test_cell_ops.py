"""Tests for cell management operations."""

import os
import sys
import tempfile
import json
import pytest

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import nbformat
from nbformat.v4 import new_notebook, new_code_cell, new_markdown_cell

from notebook_mcp import config
from notebook_mcp.core.notebook_io import write_notebook_atomic, get_notebook_content
from notebook_mcp.core import cell_ops


@pytest.fixture
def workspace(tmp_path):
    """Set up a temporary workspace and return the path."""
    config.set_workspace(str(tmp_path))
    return tmp_path


@pytest.fixture
def sample_notebook(workspace):
    """Create a sample notebook with 5 cells."""
    nb = new_notebook()
    nb.cells = [
        new_markdown_cell("# Title"),
        new_code_cell("x = 1"),
        new_code_cell("y = 2"),
        new_markdown_cell("## Section"),
        new_code_cell("z = x + y\nprint(z)"),
    ]
    path = str(workspace / "test.ipynb")
    write_notebook_atomic(nb, path)
    return path


class TestDeleteCell:
    def test_delete_middle_cell(self, sample_notebook):
        result = cell_ops.delete_cell(sample_notebook, 2)
        nb = get_notebook_content(sample_notebook)
        assert len(nb.cells) == 4
        assert "Deleted cell 2" in result

    def test_delete_first_cell(self, sample_notebook):
        cell_ops.delete_cell(sample_notebook, 0)
        nb = get_notebook_content(sample_notebook)
        assert nb.cells[0].source == "x = 1"

    def test_delete_last_cell(self, sample_notebook):
        cell_ops.delete_cell(sample_notebook, 4)
        nb = get_notebook_content(sample_notebook)
        assert len(nb.cells) == 4

    def test_delete_invalid_index(self, sample_notebook):
        with pytest.raises(IndexError):
            cell_ops.delete_cell(sample_notebook, 99)

    def test_delete_negative_index(self, sample_notebook):
        with pytest.raises(IndexError):
            cell_ops.delete_cell(sample_notebook, -1)


class TestMoveCell:
    def test_move_forward(self, sample_notebook):
        # Move cell 0 to position 2
        cell_ops.move_cell(sample_notebook, 0, 2)
        nb = get_notebook_content(sample_notebook)
        assert nb.cells[0].source == "x = 1"
        assert nb.cells[2].source == "# Title"

    def test_move_backward(self, sample_notebook):
        # Move cell 4 to position 1
        cell_ops.move_cell(sample_notebook, 4, 1)
        nb = get_notebook_content(sample_notebook)
        assert "z = x + y" in nb.cells[1].source

    def test_move_to_same_position(self, sample_notebook):
        result = cell_ops.move_cell(sample_notebook, 2, 2)
        assert "already at index" in result

    def test_move_invalid_from(self, sample_notebook):
        with pytest.raises(IndexError):
            cell_ops.move_cell(sample_notebook, 99, 0)

    def test_move_invalid_to(self, sample_notebook):
        with pytest.raises(IndexError):
            cell_ops.move_cell(sample_notebook, 0, 99)


class TestDuplicateCell:
    def test_duplicate_once(self, sample_notebook):
        cell_ops.duplicate_cell(sample_notebook, 1)
        nb = get_notebook_content(sample_notebook)
        assert len(nb.cells) == 6
        assert nb.cells[1].source == nb.cells[2].source == "x = 1"

    def test_duplicate_multiple(self, sample_notebook):
        cell_ops.duplicate_cell(sample_notebook, 0, count=3)
        nb = get_notebook_content(sample_notebook)
        assert len(nb.cells) == 8

    def test_duplicate_invalid_count(self, sample_notebook):
        with pytest.raises(ValueError):
            cell_ops.duplicate_cell(sample_notebook, 0, count=0)


class TestChangeCellType:
    def test_code_to_markdown(self, sample_notebook):
        cell_ops.change_cell_type(sample_notebook, 1, "markdown")
        nb = get_notebook_content(sample_notebook)
        assert nb.cells[1].cell_type == "markdown"
        assert nb.cells[1].source == "x = 1"

    def test_markdown_to_code(self, sample_notebook):
        cell_ops.change_cell_type(sample_notebook, 0, "code")
        nb = get_notebook_content(sample_notebook)
        assert nb.cells[0].cell_type == "code"

    def test_invalid_type(self, sample_notebook):
        with pytest.raises(ValueError):
            cell_ops.change_cell_type(sample_notebook, 0, "invalid")


class TestSplitCell:
    def test_split_code_cell(self, sample_notebook):
        # Cell 4 has 2 lines: "z = x + y\nprint(z)"
        cell_ops.split_cell(sample_notebook, 4, 1)
        nb = get_notebook_content(sample_notebook)
        assert len(nb.cells) == 6
        assert "z = x + y" in nb.cells[4].source
        assert "print(z)" in nb.cells[5].source

    def test_split_invalid_line(self, sample_notebook):
        with pytest.raises(ValueError):
            cell_ops.split_cell(sample_notebook, 4, 0)

    def test_split_out_of_range_line(self, sample_notebook):
        with pytest.raises(ValueError):
            cell_ops.split_cell(sample_notebook, 4, 99)


class TestMergeCells:
    def test_merge_adjacent_cells(self, sample_notebook):
        cell_ops.merge_cells(sample_notebook, 1)
        nb = get_notebook_content(sample_notebook)
        assert len(nb.cells) == 4
        assert "x = 1" in nb.cells[1].source
        assert "y = 2" in nb.cells[1].source

    def test_merge_last_cell_raises(self, sample_notebook):
        with pytest.raises(IndexError):
            cell_ops.merge_cells(sample_notebook, 4)


class TestBulkAddCells:
    def test_bulk_add_append(self, sample_notebook):
        cells = [
            {"content": "a = 1", "cell_type": "code"},
            {"content": "b = 2"},
            {"content": "# Header", "cell_type": "markdown"},
        ]
        cell_ops.bulk_add_cells(sample_notebook, cells)
        nb = get_notebook_content(sample_notebook)
        assert len(nb.cells) == 8

    def test_bulk_add_at_index(self, sample_notebook):
        cells = [{"content": "inserted = True"}]
        cell_ops.bulk_add_cells(sample_notebook, cells, index=0)
        nb = get_notebook_content(sample_notebook)
        assert nb.cells[0].source == "inserted = True"

    def test_bulk_add_empty_raises(self, sample_notebook):
        with pytest.raises(ValueError):
            cell_ops.bulk_add_cells(sample_notebook, [])

    def test_bulk_add_missing_content_raises(self, sample_notebook):
        with pytest.raises(ValueError):
            cell_ops.bulk_add_cells(sample_notebook, [{"cell_type": "code"}])


class TestClearOutputs:
    def test_clear_cell_outputs(self, workspace):
        nb = new_notebook()
        cell = new_code_cell("print('hi')")
        from nbformat.v4.nbbase import new_output
        cell.outputs = [new_output("stream", name="stdout", text="hi\n")]
        cell.execution_count = 1
        nb.cells = [cell]
        path = str(workspace / "out_test.ipynb")
        write_notebook_atomic(nb, path)

        cell_ops.clear_cell_outputs(path, 0)
        nb2 = get_notebook_content(path)
        assert nb2.cells[0].outputs == []
        assert nb2.cells[0].execution_count is None

    def test_clear_all_outputs(self, workspace):
        nb = new_notebook()
        from nbformat.v4.nbbase import new_output
        for i in range(3):
            c = new_code_cell(f"x = {i}")
            c.outputs = [new_output("stream", name="stdout", text=f"{i}\n")]
            c.execution_count = i + 1
            nb.cells.append(c)
        path = str(workspace / "all_out_test.ipynb")
        write_notebook_atomic(nb, path)

        result = cell_ops.clear_all_outputs(path)
        assert "3 code cell" in result
        nb2 = get_notebook_content(path)
        for cell in nb2.cells:
            assert cell.outputs == []
