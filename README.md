# Python Notebook MCP

> MCP server enabling AI assistants to interact with Jupyter notebooks through the Model Context Protocol.

[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## 🚀 Features

- Create and manage Jupyter notebooks
- Read/write notebook cells (code and markdown)
- View cell outputs including text and visualizations
- Initialize custom workspace directories

## 📋 Prerequisites

- Python 3.10+
- `fastmcp` and `nbformat` packages

## 🔧 Installation

```bash
# Clone the repository
git clone https://github.com/usamakhatab/python-notebook-mcp.git
cd python-notebook-mcp

# Install dependencies with uv (recommended)
uv pip install -r requirements.txt

# Install dependencies with pip
pip install -r requirements.txt
```

## 🔌 Integration

### Claude Desktop

1. Open Claude Desktop settings → Developer → Edit Config
2. Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "jupyter": {
      "command": "python",
      "args": ["C:\\full\\path\\to\\server.py"],
      "autoApprove": ["initialize_workspace", "list_notebooks"]
    }
  }
}
```

### Cursor IDE

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "jupyter": {
      "command": "python",
      "args": ["C:\\full\\path\\to\\server.py"]
    }
  }
}
```

## 📘 Usage

### Key Concept: Workspace Initialization

Always begin by initializing the workspace:

```
initialize_workspace("C:\\absolute\\path\\to\\project")
```

> ⚠️ You **must** provide the full absolute path; relative paths are not accepted

### Core Operations

```
# Create a notebook
create_notebook("notebook.ipynb", "My Analysis")

# Add a cell
add_cell("notebook.ipynb", "print('Hello, world!')", "code")

# Read a cell
read_cell("notebook.ipynb", 0)

# Edit a cell
edit_cell("notebook.ipynb", 0, "# Updated markdown")

# View outputs
read_cell_output("notebook.ipynb", 1)
```

## 🛠️ Available Tools

| Tool | Description |
|------|-------------|
| `initialize_workspace` | **REQUIRED FIRST STEP** - Set workspace directory |
| `list_notebooks` | List all notebook files in a directory |
| `create_notebook` | Create a new Jupyter notebook |
| `read_notebook` | Get complete notebook contents |
| `read_cell` | Get a specific cell from a notebook |
| `edit_cell` | Update a cell's content |
| `read_notebook_outputs` | Get all outputs from a notebook |
| `read_cell_output` | Get output from a specific cell |
| `add_cell` | Add a new cell to a notebook |

## 🧪 Development

### Debugging

Run in development mode:
```bash
fastmcp dev server.py
```

### Testing

Test your MCP server with the FastMCP CLI:

```bash
# Install the MCP CLI
pip install "fastmcp[cli]"

# Run the CLI against your server
mcp-cli run server.py
```

This opens an interactive shell where you can test all available tools manually.

## 🔍 Troubleshooting

- **Wrong directory?** Initialize workspace with absolute path
- **Connection issues?** Use dev mode for detailed logs
- **MCP errors?** Check paths in configuration file

## 📄 License

[MIT License](LICENSE) 