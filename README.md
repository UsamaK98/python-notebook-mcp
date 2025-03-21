# Jupyter Notebook MCP Server

A command-based Model Context Protocol (MCP) server for Jupyter notebooks, enabling local AI deployments (like Claude Desktop) to interact with Jupyter notebooks.

## Features

- Read, write, and create Jupyter notebooks
- Add, edit, delete, and execute cells
- Execute entire notebooks
- Track and undo operations
- Compare notebooks
- Handle outputs with different types (text, errors, data)
- Atomic file operations with locking
- Comprehensive error handling

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/jupyter-notebook-mcp.git
cd jupyter-notebook-mcp
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Starting the Server

Run the MCP server:

```bash
python mcp_server.py
```

### Claude Desktop Integration

To integrate with Claude Desktop, create a configuration file:

```json
{
  "mcp_servers": {
    "jupyter": {
      "command": "python",
      "args": [
        "/path/to/your/mcp_server.py"
      ],
      "env": {
        "MCP_MODE": "full",
        "MAX_CELLS": "1000"
      }
    }
  }
}
```

Save this as `claude_desktop_config.json` in the appropriate location for your system:

- Windows: `%APPDATA%\Claude Desktop\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude Desktop/claude_desktop_config.json`
- Linux: `~/.config/Claude Desktop/claude_desktop_config.json`

## Available Tools

The MCP server provides the following tools:

1. **read_notebook**: Read the contents of a Jupyter notebook
2. **write_notebook**: Write content to a Jupyter notebook
3. **create_notebook**: Create a new Jupyter notebook
4. **add_cell**: Add a new cell to the notebook
5. **edit_cell**: Edit the content of an existing cell
6. **delete_cell**: Delete a cell from the notebook
7. **execute_cell**: Execute a specific cell and return its output
8. **get_outputs**: Get outputs from a specific cell
9. **run_all_cells**: Execute all cells in the notebook in sequence
10. **undo_last_operation**: Undo the last operation on the notebook
11. **notebook_diff**: Compare two notebooks and return their differences

## API Reference

### JSON-RPC 2.0 Protocol

The server uses JSON-RPC 2.0 over STDIO. There are two main methods:

- `mcp.list_tools`: List available tools
- `mcp.use_tool`: Execute a specific tool

### Tool Parameters

For details on each tool's parameters, see the [tool_definitions.py](tool_definitions.py) file.

## Error Codes

The server uses standard JSON-RPC 2.0 error codes:

- `-32700`: Parse error
- `-32600`: Invalid request
- `-32601`: Method not found
- `-32602`: Invalid params
- `-32603`: Internal error

## Security Considerations

This MCP server has full access to the filesystem and can execute arbitrary code through notebook cells. Always run it in a secure environment and validate inputs carefully.

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. 