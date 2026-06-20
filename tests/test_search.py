"""Tests for notebook search and outline utilities."""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nbformat.v4 import new_notebook, new_code_cell, new_markdown_cell

from notebook_mcp import config
from notebook_mcp.core.notebook_io import write_notebook_atomic
from notebook_mcp.core import search as nb_search


@pytest.fixture
def workspace(tmp_path):
    config.set_workspace(str(tmp_path))
    return tmp_path


@pytest.fixture
def complex_notebook(workspace):
    nb = new_notebook()
    nb.cells = [
        new_markdown_cell("# Data Analysis\n\nThis notebook analyses sales data."),
        new_markdown_cell("## Load Data"),
        new_code_cell("import pandas as pd\nimport numpy as np\n\ndf = pd.read_csv('sales.csv')"),
        new_markdown_cell("## Explore Data"),
        new_code_cell("def clean_data(df):\n    return df.dropna()\n\nclass DataPipeline:\n    pass"),
        new_code_cell("df.head()\ndf.describe()"),
        new_markdown_cell("## Visualize"),
        new_code_cell("import matplotlib.pyplot as plt\nplt.plot(df['revenue'])\nplt.show()"),
    ]
    path = str(workspace / "complex.ipynb")
    write_notebook_atomic(nb, path)
    return path


class TestSearch:
    def test_find_import(self, complex_notebook):
        results = nb_search.notebook_search(complex_notebook, "import pandas")
        assert len(results) == 1
        assert results[0]["cell_index"] == 2

    def test_case_insensitive(self, complex_notebook):
        results = nb_search.notebook_search(complex_notebook, "PANDAS")
        assert len(results) >= 1

    def test_case_sensitive_no_match(self, complex_notebook):
        results = nb_search.notebook_search(complex_notebook, "PANDAS", case_sensitive=True)
        assert len(results) == 0

    def test_no_match(self, complex_notebook):
        results = nb_search.notebook_search(complex_notebook, "zzz_not_found_zzz")
        assert results == []

    def test_context_lines(self, complex_notebook):
        results = nb_search.notebook_search(complex_notebook, "dropna", context_lines=1)
        assert len(results) == 1
        snippet = results[0]["matches"][0]["snippet"]
        assert "dropna" in snippet

    def test_multiple_matches_in_cell(self, complex_notebook):
        # "df" appears multiple times in cell 2
        results = nb_search.notebook_search(complex_notebook, "df")
        assert any(r["match_count"] > 1 for r in results)


class TestOutline:
    def test_headings_extracted(self, complex_notebook):
        outline = nb_search.notebook_outline(complex_notebook)
        headings = [e for e in outline if e["kind"].startswith("h")]
        names = [h["name"] for h in headings]
        assert "Data Analysis" in names
        assert "Load Data" in names
        assert "Explore Data" in names

    def test_functions_extracted(self, complex_notebook):
        outline = nb_search.notebook_outline(complex_notebook)
        functions = [e for e in outline if e["kind"] == "function"]
        names = [f["name"] for f in functions]
        assert "clean_data" in names

    def test_classes_extracted(self, complex_notebook):
        outline = nb_search.notebook_outline(complex_notebook)
        classes = [e for e in outline if e["kind"] == "class"]
        names = [c["name"] for c in classes]
        assert "DataPipeline" in names

    def test_cell_index_correct(self, complex_notebook):
        outline = nb_search.notebook_outline(complex_notebook)
        for entry in outline:
            assert "cell_index" in entry
            assert isinstance(entry["cell_index"], int)


class TestNotebookInfo:
    def test_basic_info(self, complex_notebook):
        info = nb_search.notebook_info(complex_notebook)
        assert info["cell_count"] == 8
        assert info["code_cells"] == 4
        assert info["markdown_cells"] == 4
        assert info["file_size_bytes"] > 0

    def test_has_no_errors(self, complex_notebook):
        info = nb_search.notebook_info(complex_notebook)
        assert info["has_errors"] is False


class TestValidate:
    def test_valid_notebook(self, complex_notebook):
        result = nb_search.notebook_validate(complex_notebook)
        assert result["valid"] is True
        assert result["error_count"] == 0
