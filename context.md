<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" class="logo" width="120"/>

# 

---

# Comprehensive Prompt for Building a Command-Based MCP for Jupyter Notebooks

This prompt will help you implement a robust Model Context Protocol (MCP) server that allows Claude Desktop to interact with local Jupyter notebooks effectively.

## Project Overview

Your goal is to create a command-based MCP server that:

- Reads, manipulates, and executes Jupyter notebook (.ipynb) files
- Uses STDIO for communication (command-based approach)
- Can be integrated with Claude Desktop
- Provides comprehensive notebook manipulation capabilities
- Handles errors gracefully with informative messages


## Core Functionality Requirements

Your MCP server should implement these essential tools:

```python
# Define these tools in your MCP server
tools = [
    {
        "name": "read_notebook",
        "description": "Read the contents of a Jupyter notebook",
        "parameters": {
            "notebook_path": {
                "type": "string",
                "description": "Path to the notebook file"
            },
            "include_outputs": {
                "type": "boolean",
                "description": "Whether to include cell outputs in the response",
                "default": True
            }
        }
    },
    {
        "name": "add_cell",
        "description": "Add a new cell to the notebook",
        "parameters": {
            "notebook_path": {
                "type": "string",
                "description": "Path to the notebook file"
            },
            "cell_content": {
                "type": "string",
                "description": "Content to add to the cell"
            },
            "cell_type": {
                "type": "string",
                "description": "Type of cell (code or markdown)",
                "enum": ["code", "markdown"],
                "default": "code"
            },
            "position": {
                "type": "integer",
                "description": "Position to insert the cell (negative indices count from the end)",
                "default": -1
            }
        }
    },
    {
        "name": "execute_cell",
        "description": "Execute a specific cell and return its output",
        "parameters": {
            "notebook_path": {
                "type": "string",
                "description": "Path to the notebook file"
            },
            "cell_id": {
                "type": "string",
                "description": "ID of the cell to execute"
            }
        }
    },
    {
        "name": "edit_cell",
        "description": "Edit the content of an existing cell",
        "parameters": {
            "notebook_path": {
                "type": "string",
                "description": "Path to the notebook file"
            },
            "cell_id": {
                "type": "string",
                "description": "ID of the cell to edit"
            },
            "new_content": {
                "type": "string",
                "description": "New content for the cell"
            }
        }
    },
    {
        "name": "list_cells",
        "description": "List all cells in the notebook with their IDs and types",
        "parameters": {
            "notebook_path": {
                "type": "string",
                "description": "Path to the notebook file"
            }
        }
    },
    {
        "name": "get_notebook_structure",
        "description": "Get a structural overview of the notebook",
        "parameters": {
            "notebook_path": {
                "type": "string",
                "description": "Path to the notebook file"
            }
        }
    },
    {
        "name": "add_and_execute_code_cell",
        "description": "Add a new code cell and execute it immediately",
        "parameters": {
            "notebook_path": {
                "type": "string",
                "description": "Path to the notebook file"
            },
            "cell_content": {
                "type": "string",
                "description": "Code to add and execute"
            },
            "position": {
                "type": "integer",
                "description": "Position to insert the cell",
                "default": -1
            }
        }
    }
]
```


## Implementation Architecture

Structure your MCP server like this:

```
my-jupyter-mcp/
├── mcp_server.py          # Main entry point handling STDIO
├── notebook_manager.py    # Core notebook operations
├── tool_handlers.py       # Functions that implement each tool
├── error_handling.py      # Error handling utilities
├── utils.py               # Helper functions
└── README.md              # Documentation
```


## Implementation Guidelines

### 1. STDIO Protocol Handler

Create a simple JSON-RPC 2.0 handler for STDIO-based communication:

```python
import json
import sys
from typing import Dict, Any, List, Optional

class MCPServer:
    def __init__(self, tools):
        self.tools = {tool["name"]: tool for tool in tools}
        self.tool_handlers = self._load_tool_handlers()
    
    def _load_tool_handlers(self):
        # Import and map functions to tool names
        from tool_handlers import (
            read_notebook, add_cell, execute_cell, edit_cell,
            list_cells, get_notebook_structure, add_and_execute_code_cell
        )
        
        return {
            "read_notebook": read_notebook,
            "add_cell": add_cell,
            "execute_cell": execute_cell,
            "edit_cell": edit_cell,
            "list_cells": list_cells,
            "get_notebook_structure": get_notebook_structure,
            "add_and_execute_code_cell": add_and_execute_code_cell
        }
    
    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})
        
        if method == "mcp.list_tools":
            return self._handle_list_tools(request_id)
        elif method == "mcp.use_tool":
            return self._handle_use_tool(request_id, params)
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method {method} not found"
                }
            }
    
    def _handle_list_tools(self, request_id: str) -> Dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": list(self.tools.values())
        }
    
    def _handle_use_tool(self, request_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        tool_name = params.get("tool_name")
        tool_params = params.get("parameters", {})
        
        if tool_name not in self.tool_handlers:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32602,
                    "message": f"Tool {tool_name} not found"
                }
            }
        
        try:
            result = self.tool_handlers[tool_name](**tool_params)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
    
    def run(self):
        """Run the MCP server, reading and writing JSON-RPC over STDIO"""
        for line in sys.stdin:
            try:
                request = json.loads(line)
                response = self.handle_request(request)
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
            except json.JSONDecodeError:
                sys.stdout.write(json.dumps({
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": "Parse error"
                    }
                }) + "\n")
                sys.stdout.flush()

if __name__ == "__main__":
    from tools_definition import tools
    server = MCPServer(tools)
    server.run()
```


### 2. Notebook Manager

Create a robust notebook manager using nbformat and nbclient:

```python
import os
import nbformat
from nbclient import NotebookClient
from typing import Dict, Any, List, Optional, Tuple, Union

class NotebookManager:
    def __init__(self):
        pass
    
    def load_notebook(self, notebook_path: str) -> nbformat.NotebookNode:
        """Load a notebook from disk"""
        if not os.path.exists(notebook_path):
            raise FileNotFoundError(f"Notebook {notebook_path} not found")
        
        return nbformat.read(notebook_path, as_version=4)
    
    def save_notebook(self, notebook: nbformat.NotebookNode, notebook_path: str) -> None:
        """Save a notebook to disk"""
        nbformat.write(notebook, notebook_path)
    
    def execute_notebook(self, notebook: nbformat.NotebookNode, 
                          cell_indices: Optional[List[int]] = None) -> nbformat.NotebookNode:
        """Execute cells in the notebook"""
        client = NotebookClient(notebook, timeout=600, kernel_name='python3')
        
        if cell_indices is not None:
            for idx in cell_indices:
                client.execute_cell(notebook.cells[idx])
        else:
            return client.execute()
        
        return notebook
    
    def execute_single_cell(self, notebook: nbformat.NotebookNode, 
                            cell_idx: int) -> Dict[str, Any]:
        """Execute a single cell and return its outputs"""
        client = NotebookClient(notebook, timeout=600, kernel_name='python3')
        client.execute_cell(notebook.cells[cell_idx])
        return notebook.cells[cell_idx].outputs
    
    def get_cell_index_by_id(self, notebook: nbformat.NotebookNode, 
                             cell_id: str) -> int:
        """Find cell index by ID"""
        for idx, cell in enumerate(notebook.cells):
            if cell.id == cell_id:
                return idx
        raise ValueError(f"Cell with ID {cell_id} not found")
    
    def add_cell(self, notebook: nbformat.NotebookNode, 
                 content: str, cell_type: str = "code", 
                 position: int = -1) -> Tuple[nbformat.NotebookNode, str]:
        """Add a new cell to the notebook and return the updated notebook and cell ID"""
        if position < 0:
            position = len(notebook.cells) + position + 1
        
        cell = nbformat.v4.new_cell(cell_type=cell_type, source=content)
        notebook.cells.insert(position, cell)
        
        return notebook, cell.id
    
    def edit_cell(self, notebook: nbformat.NotebookNode, 
                  cell_id: str, new_content: str) -> nbformat.NotebookNode:
        """Edit the content of a cell"""
        idx = self.get_cell_index_by_id(notebook, cell_id)
        notebook.cells[idx].source = new_content
        return notebook
    
    def get_notebook_structure(self, notebook: nbformat.NotebookNode) -> Dict[str, Any]:
        """Get a structural overview of the notebook"""
        cells_info = []
        for idx, cell in enumerate(notebook.cells):
            cells_info.append({
                "index": idx,
                "id": cell.id,
                "type": cell.cell_type,
                "content_preview": cell.source[:50] + "..." if len(cell.source) > 50 else cell.source
            })
        
        metadata = {
            "kernelspec": notebook.metadata.get("kernelspec", {}),
            "language_info": notebook.metadata.get("language_info", {})
        }
        
        return {
            "cells_count": len(notebook.cells),
            "cells": cells_info,
            "metadata": metadata
        }
```


### 3. Tool Handler Implementation

Create handlers for each tool in your MCP:

```python
from notebook_manager import NotebookManager
from typing import Dict, Any, List, Optional
import os

# Initialize the notebook manager
notebook_manager = NotebookManager()

def read_notebook(notebook_path: str, include_outputs: bool = True) -> Dict[str, Any]:
    """Read the contents of a Jupyter notebook"""
    try:
        notebook = notebook_manager.load_notebook(notebook_path)
        
        cells = []
        for cell in notebook.cells:
            cell_data = {
                "id": cell.id,
                "type": cell.cell_type,
                "content": cell.source
            }
            
            if include_outputs and cell.cell_type == "code":
                output_text = []
                for output in cell.outputs:
                    if output.output_type == "stream":
                        output_text.append(output.text)
                    elif output.output_type == "execute_result":
                        if hasattr(output, "data") and "text/plain" in output.data:
                            output_text.append(output.data["text/plain"])
                    elif output.output_type == "display_data":
                        if hasattr(output, "data") and "text/plain" in output.data:
                            output_text.append(output.data["text/plain"])
                    elif output.output_type == "error":
                        output_text.append(f"ERROR: {output.ename}: {output.evalue}")
                
                cell_data["outputs"] = output_text
            
            cells.append(cell_data)
        
        return {
            "notebook_path": notebook_path,
            "cells": cells,
            "metadata": dict(notebook.metadata)
        }
    except Exception as e:
        raise Exception(f"Error reading notebook: {str(e)}")

def add_cell(notebook_path: str, cell_content: str, 
            cell_type: str = "code", position: int = -1) -> Dict[str, Any]:
    """Add a new cell to the notebook"""
    try:
        notebook = notebook_manager.load_notebook(notebook_path)
        updated_notebook, cell_id = notebook_manager.add_cell(
            notebook, cell_content, cell_type, position
        )
        notebook_manager.save_notebook(updated_notebook, notebook_path)
        
        return {
            "success": True,
            "message": f"Added {cell_type} cell at position {position if position >= 0 else 'end'}",
            "cell_id": cell_id
        }
    except Exception as e:
        raise Exception(f"Error adding cell: {str(e)}")

def execute_cell(notebook_path: str, cell_id: str) -> Dict[str, Any]:
    """Execute a specific cell and return its output"""
    try:
        notebook = notebook_manager.load_notebook(notebook_path)
        cell_idx = notebook_manager.get_cell_index_by_id(notebook, cell_id)
        
        outputs = notebook_manager.execute_single_cell(notebook, cell_idx)
        notebook_manager.save_notebook(notebook, notebook_path)
        
        # Process and format outputs
        output_text = []
        for output in outputs:
            if output.output_type == "stream":
                output_text.append(output.text)
            elif output.output_type == "execute_result":
                if hasattr(output, "data") and "text/plain" in output.data:
                    output_text.append(output.data["text/plain"])
            elif output.output_type == "display_data":
                if hasattr(output, "data") and "text/plain" in output.data:
                    output_text.append(output.data["text/plain"])
            elif output.output_type == "error":
                output_text.append(f"ERROR: {output.ename}: {output.evalue}")
        
        return {
            "success": True,
            "cell_id": cell_id,
            "outputs": output_text
        }
    except Exception as e:
        raise Exception(f"Error executing cell: {str(e)}")

def edit_cell(notebook_path: str, cell_id: str, new_content: str) -> Dict[str, Any]:
    """Edit the content of an existing cell"""
    try:
        notebook = notebook_manager.load_notebook(notebook_path)
        updated_notebook = notebook_manager.edit_cell(notebook, cell_id, new_content)
        notebook_manager.save_notebook(updated_notebook, notebook_path)
        
        return {
            "success": True,
            "message": f"Updated cell {cell_id}",
            "cell_id": cell_id
        }
    except Exception as e:
        raise Exception(f"Error editing cell: {str(e)}")

def list_cells(notebook_path: str) -> Dict[str, Any]:
    """List all cells in the notebook with their IDs and types"""
    try:
        notebook = notebook_manager.load_notebook(notebook_path)
        
        cells = []
        for idx, cell in enumerate(notebook.cells):
            cells.append({
                "index": idx,
                "id": cell.id,
                "type": cell.cell_type,
                "content_preview": cell.source[:50] + "..." if len(cell.source) > 50 else cell.source
            })
        
        return {
            "success": True,
            "notebook_path": notebook_path,
            "cells": cells
        }
    except Exception as e:
        raise Exception(f"Error listing cells: {str(e)}")

def get_notebook_structure(notebook_path: str) -> Dict[str, Any]:
    """Get a structural overview of the notebook"""
    try:
        notebook = notebook_manager.load_notebook(notebook_path)
        structure = notebook_manager.get_notebook_structure(notebook)
        
        return {
            "success": True,
            "notebook_path": notebook_path,
            "structure": structure
        }
    except Exception as e:
        raise Exception(f"Error getting notebook structure: {str(e)}")

def add_and_execute_code_cell(notebook_path: str, cell_content: str, position: int = -1) -> Dict[str, Any]:
    """Add a new code cell and execute it immediately"""
    try:
        # First add the cell
        result = add_cell(notebook_path, cell_content, "code", position)
        cell_id = result["cell_id"]
        
        # Then execute it
        execute_result = execute_cell(notebook_path, cell_id)
        
        return {
            "success": True,
            "cell_id": cell_id,
            "outputs": execute_result["outputs"]
        }
    except Exception as e:
        raise Exception(f"Error adding and executing cell: {str(e)}")
```


## Claude Desktop Integration

To integrate with Claude Desktop, create a configuration file:

```json
{
  "mcpServers": {
    "jupyter": {
      "command": "python",
      "args": [
        "/path/to/your/mcp_server.py"
      ],
      "env": {
        "PYTHONPATH": "/path/to/your/project",
        "NOTEBOOK_PATH": "${NOTEBOOK_PATH}"
      }
    }
  }
}
```

Save this as `claude_desktop_config.json` in the appropriate location for your system:

- Windows: `%APPDATA%\Claude Desktop\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude Desktop/claude_desktop_config.json`
- Linux: `~/.config/Claude Desktop/claude_desktop_config.json`


## Error Handling Best Practices

1. Implement comprehensive error handling in your MCP server:
    - Validate all input parameters
    - Handle file not found errors gracefully
    - Catch and report execution errors
    - Provide clear error messages
2. Add structured logging:
    - Log all operations for debugging
    - Include timestamps and severity levels
    - Don't log sensitive information
3. Implement graceful degradation:
    - If a notebook is too large, offer to read without outputs
    - If execution times out, provide partial results

## Testing Your Implementation

To test your MCP implementation, create a simple test script:

```python
import json
import subprocess
import sys

def test_mcp_server():
    # Path to your MCP server script
    server_path = "./mcp_server.py"
    
    # Start the server process
    process = subprocess.Popen(
        [sys.executable, server_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Test listing tools
    list_tools_request = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "mcp.list_tools"
    }
    
    # Send the request
    process.stdin.write(json.dumps(list_tools_request) + "\n")
    process.stdin.flush()
    
    # Read the response
    response = json.loads(process.stdout.readline())
    print("List tools response:", json.dumps(response, indent=2))
    
    # Test reading a notebook
    use_tool_request = {
        "jsonrpc": "2.0",
        "id": "2",
        "method": "mcp.use_tool",
        "params": {
            "tool_name": "read_notebook",
            "parameters": {
                "notebook_path": "example.ipynb",
                "include_outputs": True
            }
        }
    }
    
    # Send the request
    process.stdin.write(json.dumps(use_tool_request) + "\n")
    process.stdin.flush()
    
    # Read the response
    response = json.loads(process.stdout.readline())
    print("Read notebook response:", json.dumps(response, indent=2))
    
    # Clean up
    process.terminate()

if __name__ == "__main__":
    test_mcp_server()
```


## Dependencies

Your MCP server will require these Python packages:

- nbformat (for reading/writing notebooks)
- nbclient (for executing notebooks)
- jupyter_core (for notebook paths)
- ipykernel (for Python kernel)

Install them with:

```
pip install nbformat nbclient jupyter_core ipykernel
```

<div style="text-align: center">⁂</div>

[^1]: https://www.reddit.com/r/ClaudeAI/comments/1hxrpzm/what_would_you_like_to_see_addedfixed_in_claudeai/

[^2]: https://github.com/datalayer/jupyter-mcp-server

[^3]: https://www.reddit.com/r/emacs/comments/1i2hi0t/your_reason_to_switch_to_emacs_or_was_it_your/

[^4]: https://www.reddit.com/r/cursor/comments/1j3v1zi/i_built_a_cursor_extension_that_actually/

[^5]: https://libraries.io/pypi/mcp-server-jupyter

[^6]: https://pypi.org/project/mcp-client-jupyter-chat/

[^7]: https://github.com/datalayer/jupyter-mcp-server/blob/main/RELEASE.md

[^8]: https://www.reddit.com/r/raycastapp/comments/1ij20al/ama_with_raycasts_founders/

[^9]: https://www.reddit.com/r/ClaudeAI/comments/1h3f6kh/dont_guess_ask_would_have_saved_days_of_my_life/

[^10]: https://www.reddit.com/r/AI_Agents/top/

[^11]: https://www.reddit.com/r/LocalLLaMA/comments/1hofvtw/deepseek_v3_is_absolutely_astonishing/

[^12]: https://learn.microsoft.com/en-us/azure/sentinel/notebook-get-started

[^13]: https://github.com/modelcontextprotocol/servers

[^14]: https://blog.jupyter.org/building-ai-agents-for-jupyterlab-using-notebook-intelligence-0515d4c41a61

[^15]: https://github.com/CIMCB/MetabWorkflowTutorial/blob/master/Tutorial1.ipynb

[^16]: https://github.com/punkpeye/awesome-mcp-clients/blob/main/README.md

[^17]: https://blog.jupyter.org/introducing-notebook-intelligence-3648c306b91a

[^18]: https://digitalhumanities.hkust.edu.hk/tutorials/how-to-open-ipynb-file-jupyter-notebook/

[^19]: https://blog.stackademic.com/exploring-model-context-protocol-mcp-with-claude-desktop-simplifying-ai-integration-e447087f95a1

[^20]: https://jupyterlab.readthedocs.io/en/stable/getting_started/overview.html

[^21]: https://jupyter-notebook.readthedocs.io/en/stable/notebook.html

[^22]: https://infisical.com/blog/managing-secrets-mcp-servers

[^23]: https://stackoverflow.com/questions/38867031/what-is-the-easiest-way-to-create-a-webapp-from-an-interactive-jupyter-notebook

[^24]: http://ipython.org/ipython-doc/3/notebook/notebook.html

[^25]: https://www.reddit.com/r/mcp/new/?after=dDNfMWltejdqdA%3D%3D\&sort=hot\&t=day\&feedViewType=cardView

[^26]: https://www.reddit.com/r/mcp/new/?after=dDNfMWlvc2w2ZA%3D%3D\&sort=new\&t=all\&feedViewType=cardView

[^27]: https://www.reddit.com/r/mcp/new/?after=dDNfMWpib2RwMw%3D%3D\&sort=new\&t=DAY\&feedViewType=compactView

[^28]: https://www.reddit.com/r/mcp/new/?after=dDNfMWlwYjhqMA%3D%3D\&sort=top\&t=ALL

[^29]: https://www.reddit.com/r/mcp/new/?after=dDNfMWlvbnJiaA%3D%3D\&sort=top\&t=MONTH\&feedViewType=cardView

[^30]: https://www.reddit.com/r/mcp/top/?after=dDNfMWpia3ZjNA%3D%3D\&sort=top\&t=DAY

[^31]: https://www.reddit.com/r/mcp/new/?after=dDNfMWpibHl4ag%3D%3D\&sort=new\&t=HOUR

[^32]: https://www.reddit.com/r/mcp/new/?after=dDNfMWlyemNhdw%3D%3D\&sort=hot\&t=day

[^33]: https://www.reddit.com/r/mcp/rising/?after=dDNfMWpiMHNnNQ%3D%3D\&sort=new\&t=WEEK

[^34]: https://www.reddit.com/r/mcp/rising/?after=dDNfMWo4ZHNwaA%3D%3D\&sort=top\&t=month

[^35]: https://www.reddit.com/r/mcp/new/?after=dDNfMWl3djZmMw%3D%3D\&sort=top\&t=month

[^36]: https://www.reddit.com/r/mcp/top/?after=dDNfMWpia3ZjNA%3D%3D\&sort=new\&t=week\&feedViewType=cardView

[^37]: https://www.reddit.com/r/mcp/new/?after=dDNfMWloMW43Mw%3D%3D\&sort=new\&t=month\&feedViewType=compactView

[^38]: https://www.reddit.com/r/mcp/top/?feedViewType=cardView

[^39]: https://www.reddit.com/r/mcp/top/?after=dDNfMWo2dmd4cQ%3D%3D\&sort=top\&t=WEEK

[^40]: https://www.reddit.com/r/mcp/new/?after=dDNfMWpicHVhdA%3D%3D\&sort=hot\&t=DAY

[^41]: https://www.mcpserverfinder.com/servers/mcp-server-jupyter

[^42]: https://modelcontextprotocol.io/quickstart/server

[^43]: https://github.com/datalayer/jupyter-mcp-server/blob/main/LICENSE

[^44]: https://blog.jiang.jp/post/llm-agents-mcp-comprehensive-guide

[^45]: https://github.com/datalayer/jupyter-mcp-server/actions

[^46]: https://github.com/datalayer/jupyter-mcp-server/blob/main/Dockerfile

[^47]: https://github.com/datalayer/jupyter-mcp-server/blob/main/Makefile

[^48]: https://stackoverflow.com/questions/79505420/how-to-implement-a-model-context-protocol-mcp-server-with-sse

[^49]: https://github.com/datalayer/jupyter-mcp-server/security

[^50]: https://glama.ai/mcp/servers/et849kq742/related-servers

[^51]: https://github.com/jupyter-server/jupyter_server

[^52]: https://www.youtube.com/watch?v=kfTDFkhNDFU

[^53]: https://github.com/datalayer/jupyter-mcp-server/actions/workflows/build.yml

[^54]: https://smithery.ai/server/@datalayer/jupyter-mcp-server

[^55]: https://www.reddit.com/r/ArtificialInteligence/comments/1ftskuk/has_anyone_used_notebooklm_how_exactly_do_you_use/

[^56]: https://www.reddit.com/r/LocalLLaMA/comments/1ckw7en/what_software_do_you_use_to_interact_with_local/

[^57]: https://www.reddit.com/r/LocalLLaMA/comments/1hk1lk3/youre_all_wrong_about_ai_coding_its_not_about/

[^58]: https://stackoverflow.com/questions/17905350/running-an-ipython-jupyter-notebook-non-interactively

[^59]: https://www.youtube.com/watch?v=5ZWeCKY5WZE

[^60]: https://discourse.jupyter.org/t/how-to-run-a-notebook-using-command-line/3475

[^61]: https://www.linkedin.com/pulse/how-mcp-empowering-next-generation-ai-powered-agents-ke-zheng-qzvqe

[^62]: https://www.anthropic.com/news/model-context-protocol

[^63]: https://www.reddit.com/r/ClaudeAI/comments/1j86vgm/mcp_simplified_like_youre_5_years_old/

[^64]: https://www.reddit.com/r/ClaudeAI/comments/1hblo5y/resources_on_learning_mcp_as_a_developer/

[^65]: https://www.reddit.com/r/programming/comments/1hafiy0/kitchenai_open_source_llmops_tool_for_ai_devs_go/

[^66]: https://github.com/datalayer/jupyter-mcp-server/blob/main/smithery.yaml

[^67]: https://glama.ai/mcp/servers/et849kq742

