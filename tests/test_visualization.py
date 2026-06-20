"""Tests for visualization detection and description."""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nbformat.v4 import new_notebook, new_code_cell, new_markdown_cell
from nbformat.v4.nbbase import new_output

from notebook_mcp import config
from notebook_mcp.core.notebook_io import write_notebook_atomic
from notebook_mcp.visualization import detector as viz_detector
from notebook_mcp.visualization import describer as viz_describer


@pytest.fixture
def workspace(tmp_path):
    config.set_workspace(str(tmp_path))
    return tmp_path


class TestDetector:
    def test_detect_matplotlib(self):
        source = "import matplotlib.pyplot as plt\nplt.plot([1,2,3])\nplt.show()"
        assert viz_detector.detect_library(source) == "matplotlib"

    def test_detect_seaborn(self):
        source = "import seaborn as sns\nsns.heatmap(data)"
        assert viz_detector.detect_library(source) == "seaborn"

    def test_detect_plotly(self):
        source = "import plotly.express as px\nfig = px.scatter(df, x='a', y='b')\nfig.show()"
        assert viz_detector.detect_library(source) == "plotly"

    def test_detect_no_library(self):
        source = "x = 1 + 2\nprint(x)"
        assert viz_detector.detect_library(source) is None

    def test_detect_bar_chart(self):
        source = "plt.bar(categories, values)"
        assert viz_detector.detect_chart_type(source) == "bar_chart"

    def test_detect_scatter(self):
        source = "plt.scatter(x, y)"
        assert viz_detector.detect_chart_type(source) == "scatter"

    def test_detect_heatmap(self):
        source = "sns.heatmap(corr_matrix, annot=True)"
        assert viz_detector.detect_chart_type(source) == "heatmap"

    def test_detect_histogram(self):
        source = "plt.hist(data, bins=30)"
        assert viz_detector.detect_chart_type(source) == "histogram"

    def test_has_visual_output_png(self):
        cell = new_code_cell("plt.plot()")
        cell.outputs = [new_output(
            "display_data",
            data={"image/png": "abc123", "text/plain": "<Figure>"},
            metadata={},
        )]
        assert viz_detector.has_visual_output(cell) is True

    def test_has_visual_output_empty(self):
        cell = new_code_cell("x = 1")
        assert viz_detector.has_visual_output(cell) is False

    def test_scan_notebook_finds_viz_cells(self, tmp_path):
        config.set_workspace(str(tmp_path))
        nb = new_notebook()
        # Cell 0: no viz
        c0 = new_code_cell("x = 1")
        # Cell 1: matplotlib
        c1 = new_code_cell("import matplotlib.pyplot as plt\nplt.plot([1,2,3])\nplt.show()")
        c1.outputs = [new_output(
            "display_data",
            data={"image/png": "fakebase64", "text/plain": "<Figure>"},
            metadata={},
        )]
        # Cell 2: plotly
        c2 = new_code_cell("import plotly.express as px\nfig = px.bar(df)\nfig.show()")
        nb.cells = [c0, c1, c2]

        results = viz_detector.scan_notebook_visualizations(nb)
        cell_indices = [r["cell_index"] for r in results]
        assert 1 in cell_indices
        assert 2 in cell_indices
        assert 0 not in cell_indices


class TestDescriber:
    def test_describes_line_chart(self):
        source = (
            "import matplotlib.pyplot as plt\n"
            "plt.figure(figsize=(10, 6))\n"
            "plt.plot(df['date'], df['revenue'], label='Revenue')\n"
            "plt.title('Revenue Over Time')\n"
            "plt.xlabel('Date')\n"
            "plt.ylabel('Revenue (USD)')\n"
            "plt.show()"
        )
        cell = new_code_cell(source)
        desc = viz_describer.describe_cell_visualization(cell, 0)
        assert desc.library == "matplotlib"
        assert desc.chart_type == "line_chart"
        assert desc.title == "Revenue Over Time"
        assert desc.x_label == "Date"
        assert desc.y_label == "Revenue (USD)"
        assert "Revenue" in desc.series_names
        assert "line chart" in desc.description.lower()

    def test_describes_seaborn_heatmap(self):
        source = "sns.heatmap(corr_matrix, cmap='viridis', annot=True)"
        cell = new_code_cell(source)
        desc = viz_describer.describe_cell_visualization(cell, 1)
        assert desc.library == "seaborn"
        assert desc.chart_type == "heatmap"
        assert desc.color_info == "colormap: viridis"

    def test_description_not_empty(self):
        source = "plt.scatter(x, y)"
        cell = new_code_cell(source)
        desc = viz_describer.describe_cell_visualization(cell, 0)
        assert desc.description
        assert len(desc.description) > 10

    def test_no_output_hint(self):
        source = "plt.plot(x, y)\nplt.show()"
        cell = new_code_cell(source)
        desc = viz_describer.describe_cell_visualization(cell, 0)
        assert not desc.has_rendered_output
        assert "no rendered output" in desc.description.lower()

    def test_interactive_flag(self):
        source = "import plotly.express as px\nfig = px.scatter(df, x='a', y='b')\nfig.show()"
        cell = new_code_cell(source)
        desc = viz_describer.describe_cell_visualization(cell, 0)
        assert desc.is_interactive is True
