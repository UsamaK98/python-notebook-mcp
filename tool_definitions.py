"""
Tool definitions for the Jupyter Notebook MCP server.
This file defines the available tools and their parameters.
"""

tools = [
    {
        "name": "read_notebook",
        "description": "Read the contents of a Jupyter notebook",
        "parameters": {
            "type": "object",
            "properties": {
                "notebook_path": {
                    "type": "string",
                    "description": "Path to the notebook file"
                },
                "include_outputs": {
                    "type": "boolean",
                    "description": "Whether to include cell outputs in the response",
                    "default": True
                }
            },
            "required": ["notebook_path"]
        }
    },
    {
        "name": "write_notebook",
        "description": "Write content to a Jupyter notebook, replacing existing content",
        "parameters": {
            "type": "object",
            "properties": {
                "notebook_path": {
                    "type": "string",
                    "description": "Path to the notebook file"
                },
                "content": {
                    "type": "object",
                    "description": "Notebook content in nbformat structure"
                }
            },
            "required": ["notebook_path", "content"]
        }
    },
    {
        "name": "create_notebook",
        "description": "Create a new Jupyter notebook",
        "parameters": {
            "type": "object",
            "properties": {
                "notebook_path": {
                    "type": "string",
                    "description": "Path to create the new notebook file"
                },
                "kernel_name": {
                    "type": "string",
                    "description": "Kernel to use for the notebook",
                    "default": "python3"
                }
            },
            "required": ["notebook_path"]
        }
    },
    {
        "name": "add_cell",
        "description": "Add a new cell to the notebook",
        "parameters": {
            "type": "object",
            "properties": {
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
            },
            "required": ["notebook_path", "cell_content"]
        }
    },
    {
        "name": "edit_cell",
        "description": "Edit the content of an existing cell",
        "parameters": {
            "type": "object",
            "properties": {
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
            },
            "required": ["notebook_path", "cell_id", "new_content"]
        }
    },
    {
        "name": "delete_cell",
        "description": "Delete a cell from the notebook",
        "parameters": {
            "type": "object",
            "properties": {
                "notebook_path": {
                    "type": "string",
                    "description": "Path to the notebook file"
                },
                "cell_id": {
                    "type": "string",
                    "description": "ID of the cell to delete"
                }
            },
            "required": ["notebook_path", "cell_id"]
        }
    },
    {
        "name": "execute_cell",
        "description": "Execute a specific cell and return its output",
        "parameters": {
            "type": "object",
            "properties": {
                "notebook_path": {
                    "type": "string",
                    "description": "Path to the notebook file"
                },
                "cell_id": {
                    "type": "string",
                    "description": "ID of the cell to execute"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Execution timeout in seconds",
                    "default": 60
                }
            },
            "required": ["notebook_path", "cell_id"]
        }
    },
    {
        "name": "get_outputs",
        "description": "Get outputs from a specific cell",
        "parameters": {
            "type": "object",
            "properties": {
                "notebook_path": {
                    "type": "string",
                    "description": "Path to the notebook file"
                },
                "cell_id": {
                    "type": "string",
                    "description": "ID of the cell to get outputs from"
                }
            },
            "required": ["notebook_path", "cell_id"]
        }
    },
    {
        "name": "run_all_cells",
        "description": "Execute all cells in the notebook in sequence",
        "parameters": {
            "type": "object",
            "properties": {
                "notebook_path": {
                    "type": "string",
                    "description": "Path to the notebook file"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Execution timeout per cell in seconds",
                    "default": 60
                }
            },
            "required": ["notebook_path"]
        }
    },
    {
        "name": "undo_last_operation",
        "description": "Undo the last operation on the notebook",
        "parameters": {
            "type": "object",
            "properties": {
                "notebook_path": {
                    "type": "string",
                    "description": "Path to the notebook file"
                }
            },
            "required": ["notebook_path"]
        }
    },
    {
        "name": "notebook_diff",
        "description": "Compare two notebooks and return their differences",
        "parameters": {
            "type": "object",
            "properties": {
                "notebook_path_a": {
                    "type": "string",
                    "description": "Path to the first notebook"
                },
                "notebook_path_b": {
                    "type": "string",
                    "description": "Path to the second notebook"
                },
                "include_outputs": {
                    "type": "boolean",
                    "description": "Whether to include output differences in the comparison",
                    "default": False
                }
            },
            "required": ["notebook_path_a", "notebook_path_b"]
        }
    }
] 