"""Tests for notebook intelligence: summarizer, pipeline, error analysis."""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nbformat.v4 import new_notebook, new_code_cell, new_markdown_cell
from nbformat.v4.nbbase import new_output

from notebook_mcp import config
from notebook_mcp.core.notebook_io import write_notebook_atomic
from notebook_mcp.intelligence import summarizer as nb_summarizer
from notebook_mcp.intelligence import pipeline as nb_pipeline
from notebook_mcp.intelligence import data_inspector


@pytest.fixture
def workspace(tmp_path):
    config.set_workspace(str(tmp_path))
    return tmp_path


@pytest.fixture
def ml_notebook(workspace):
    nb = new_notebook()
    nb.metadata["kernelspec"] = {"name": "python3", "language": "python"}
    nb.cells = [
        new_markdown_cell("# Sales Prediction Model\n\nThis notebook trains an ML model."),
        new_code_cell("import pandas as pd\nimport numpy as np\nfrom sklearn.linear_model import LinearRegression"),
        new_markdown_cell("## Load Data"),
        new_code_cell("df = pd.read_csv('sales.csv')\nprint(df.shape)"),
        new_markdown_cell("## Preprocess"),
        new_code_cell("df_clean = df.dropna()\nX = df_clean[['price', 'quantity']]\ny = df_clean['revenue']"),
        new_markdown_cell("## Train Model"),
        new_code_cell("model = LinearRegression()\nmodel.fit(X, y)"),
        new_markdown_cell("## Evaluate"),
        new_code_cell("score = model.score(X, y)\nprint(f'R² = {score:.3f}')"),
        new_markdown_cell("## Visualize"),
        new_code_cell("import matplotlib.pyplot as plt\nplt.scatter(y, model.predict(X))\nplt.show()"),
    ]
    path = str(workspace / "ml_model.ipynb")
    write_notebook_atomic(nb, path)
    return path


@pytest.fixture
def error_notebook(workspace):
    nb = new_notebook()
    nb.cells = [
        new_code_cell("x = undefined_var"),
    ]
    err_output = new_output(
        "error",
        ename="NameError",
        evalue="name 'undefined_var' is not defined",
        traceback=[
            "\x1b[0;31mNameError\x1b[0m                                 Traceback (most recent call last)",
            "Cell In[1], line 1",
            "---> 1 x = undefined_var",
            "\x1b[0;31mNameError\x1b[0m: name 'undefined_var' is not defined",
        ],
    )
    nb.cells[0].outputs = [err_output]
    path = str(workspace / "error_nb.ipynb")
    write_notebook_atomic(nb, path)
    return path


class TestSummarizer:
    def test_brief_summary(self, ml_notebook):
        summary = nb_summarizer.summarize_notebook(ml_notebook, "brief")
        assert "title" in summary
        assert "domain" in summary
        assert "cell_count" in summary
        assert summary["cell_count"] == 12

    def test_standard_summary_domain(self, ml_notebook):
        summary = nb_summarizer.summarize_notebook(ml_notebook, "standard")
        domains = summary.get("domain", [])
        # Should detect ML and data analysis
        assert any("Learning" in d or "Analysis" in d for d in domains)

    def test_standard_summary_data_sources(self, ml_notebook):
        summary = nb_summarizer.summarize_notebook(ml_notebook)
        sources = summary["data"]["input_sources"]
        assert "sales.csv" in sources

    def test_standard_summary_visualizations(self, ml_notebook):
        summary = nb_summarizer.summarize_notebook(ml_notebook)
        assert summary["visualizations"]["count"] >= 1

    def test_detailed_includes_imports(self, ml_notebook):
        summary = nb_summarizer.summarize_notebook(ml_notebook, "detailed")
        assert "imports" in summary
        assert any("pandas" in imp for imp in summary["imports"])

    def test_title_extracted(self, ml_notebook):
        summary = nb_summarizer.summarize_notebook(ml_notebook)
        assert summary["title"] == "Sales Prediction Model"


class TestPipeline:
    def test_pipeline_has_stages(self, ml_notebook):
        pipeline = nb_pipeline.get_notebook_pipeline(ml_notebook)
        assert "stages" in pipeline
        assert len(pipeline["stages"]) > 0

    def test_entry_points_detected(self, ml_notebook):
        pipeline = nb_pipeline.get_notebook_pipeline(ml_notebook)
        # Cell 3 loads data from CSV
        assert len(pipeline["entry_points"]) >= 1

    def test_data_flow_has_variables(self, ml_notebook):
        pipeline = nb_pipeline.get_notebook_pipeline(ml_notebook)
        data_flow = pipeline["data_flow"]
        assert "df" in data_flow or "model" in data_flow

    def test_role_summary(self, ml_notebook):
        pipeline = nb_pipeline.get_notebook_pipeline(ml_notebook)
        roles = pipeline["role_summary"]
        assert "data_loading" in roles
        assert "model_training" in roles

    def test_summary_string(self, ml_notebook):
        pipeline = nb_pipeline.get_notebook_pipeline(ml_notebook)
        assert isinstance(pipeline["summary"], str)
        assert len(pipeline["summary"]) > 10


class TestErrorAnalysis:
    def test_detects_name_error(self, error_notebook):
        result = data_inspector.analyze_cell_error(error_notebook, 0)
        assert result["has_error"] is True
        assert result["error_type"] == "NameError"

    def test_error_message(self, error_notebook):
        result = data_inspector.analyze_cell_error(error_notebook, 0)
        assert "undefined_var" in result["error_message"]

    def test_hint_provided(self, error_notebook):
        result = data_inspector.analyze_cell_error(error_notebook, 0)
        assert result["hint"] is not None
        assert len(result["hint"]) > 10

    def test_traceback_cleaned(self, error_notebook):
        result = data_inspector.analyze_cell_error(error_notebook, 0)
        # Should not contain ANSI escape codes
        assert "\x1b" not in result["traceback_summary"]

    def test_no_error_cell(self, workspace):
        nb = new_notebook()
        nb.cells = [new_code_cell("x = 1")]
        path = str(workspace / "no_err.ipynb")
        write_notebook_atomic(nb, path)
        result = data_inspector.analyze_cell_error(path, 0)
        assert result["has_error"] is False

    def test_invalid_index_raises(self, error_notebook):
        with pytest.raises(IndexError):
            data_inspector.analyze_cell_error(error_notebook, 99)
