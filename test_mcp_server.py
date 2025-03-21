#!/usr/bin/env python
"""
Test script for the Jupyter Notebook MCP server.
This script sends requests to the MCP server and validates the responses.
"""

import json
import subprocess
import sys
import os
import time
import tempfile
import shutil
import nbformat

def test_mcp_server():
    """Test the MCP server functionality"""
    # Create a test notebook
    test_dir = tempfile.mkdtemp()
    test_notebook_path = os.path.join(test_dir, "test_notebook.ipynb")
    
    # Path to your MCP server script
    server_path = "./mcp_server.py"
    
    # Start the server process
    process = subprocess.Popen(
        [sys.executable, server_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1  # Line buffered
    )
    
    try:
        # Test 1: List tools
        print("Test 1: Listing tools...")
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
        assert "result" in response, "No result in response"
        assert len(response["result"]) > 0, "No tools returned"
        print(f"✓ Successfully listed {len(response['result'])} tools")
        
        # Test 2: Create a notebook
        print("Test 2: Creating a notebook...")
        create_notebook_request = {
            "jsonrpc": "2.0",
            "id": "2",
            "method": "mcp.use_tool",
            "params": {
                "tool_name": "create_notebook",
                "parameters": {
                    "notebook_path": test_notebook_path
                }
            }
        }
        
        # Send the request
        process.stdin.write(json.dumps(create_notebook_request) + "\n")
        process.stdin.flush()
        
        # Read the response
        response = json.loads(process.stdout.readline())
        assert "result" in response, "No result in response"
        assert response["result"]["success"], "Failed to create notebook"
        print(f"✓ Successfully created notebook at {test_notebook_path}")
        
        # Test 3: Add a code cell
        print("Test 3: Adding a code cell...")
        add_cell_request = {
            "jsonrpc": "2.0",
            "id": "3",
            "method": "mcp.use_tool",
            "params": {
                "tool_name": "add_cell",
                "parameters": {
                    "notebook_path": test_notebook_path,
                    "cell_content": "print('Hello, world!')",
                    "cell_type": "code"
                }
            }
        }
        
        # Send the request
        process.stdin.write(json.dumps(add_cell_request) + "\n")
        process.stdin.flush()
        
        # Read the response
        response = json.loads(process.stdout.readline())
        assert "result" in response, "No result in response"
        assert response["result"]["success"], "Failed to add cell"
        cell_id = response["result"]["cell_id"]
        print(f"✓ Successfully added code cell with ID {cell_id}")
        
        # Test 4: Add a markdown cell
        print("Test 4: Adding a markdown cell...")
        add_markdown_cell_request = {
            "jsonrpc": "2.0",
            "id": "4",
            "method": "mcp.use_tool",
            "params": {
                "tool_name": "add_cell",
                "parameters": {
                    "notebook_path": test_notebook_path,
                    "cell_content": "# Test Heading",
                    "cell_type": "markdown"
                }
            }
        }
        
        # Send the request
        process.stdin.write(json.dumps(add_markdown_cell_request) + "\n")
        process.stdin.flush()
        
        # Read the response
        response = json.loads(process.stdout.readline())
        assert "result" in response, "No result in response"
        assert response["result"]["success"], "Failed to add markdown cell"
        markdown_cell_id = response["result"]["cell_id"]
        print(f"✓ Successfully added markdown cell with ID {markdown_cell_id}")
        
        # Test 5: Read the notebook
        print("Test 5: Reading the notebook...")
        read_notebook_request = {
            "jsonrpc": "2.0",
            "id": "5",
            "method": "mcp.use_tool",
            "params": {
                "tool_name": "read_notebook",
                "parameters": {
                    "notebook_path": test_notebook_path,
                    "include_outputs": True
                }
            }
        }
        
        # Send the request
        process.stdin.write(json.dumps(read_notebook_request) + "\n")
        process.stdin.flush()
        
        # Read the response
        response = json.loads(process.stdout.readline())
        assert "result" in response, "No result in response"
        assert "cells" in response["result"], "No cells in notebook"
        assert len(response["result"]["cells"]) == 2, f"Expected 2 cells, got {len(response['result']['cells'])}"
        print(f"✓ Successfully read notebook with {len(response['result']['cells'])} cells")
        
        # Test 6: Execute the code cell
        print("Test 6: Executing code cell...")
        execute_cell_request = {
            "jsonrpc": "2.0",
            "id": "6",
            "method": "mcp.use_tool",
            "params": {
                "tool_name": "execute_cell",
                "parameters": {
                    "notebook_path": test_notebook_path,
                    "cell_id": cell_id
                }
            }
        }
        
        # Send the request
        process.stdin.write(json.dumps(execute_cell_request) + "\n")
        process.stdin.flush()
        
        # Read the response
        response = json.loads(process.stdout.readline())
        assert "result" in response, "No result in response"
        assert "outputs" in response["result"], "No outputs in response"
        print(f"✓ Successfully executed cell with outputs: {response['result']['outputs']}")
        
        # Test 7: Edit a cell
        print("Test 7: Editing a cell...")
        edit_cell_request = {
            "jsonrpc": "2.0",
            "id": "7",
            "method": "mcp.use_tool",
            "params": {
                "tool_name": "edit_cell",
                "parameters": {
                    "notebook_path": test_notebook_path,
                    "cell_id": cell_id,
                    "new_content": "print('Hello, edited world!')"
                }
            }
        }
        
        # Send the request
        process.stdin.write(json.dumps(edit_cell_request) + "\n")
        process.stdin.flush()
        
        # Read the response
        response = json.loads(process.stdout.readline())
        assert "result" in response, "No result in response"
        assert response["result"]["success"], "Failed to edit cell"
        print(f"✓ Successfully edited cell with ID {cell_id}")
        
        # Test 8: Run all cells
        print("Test 8: Running all cells...")
        run_all_cells_request = {
            "jsonrpc": "2.0",
            "id": "8",
            "method": "mcp.use_tool",
            "params": {
                "tool_name": "run_all_cells",
                "parameters": {
                    "notebook_path": test_notebook_path
                }
            }
        }
        
        # Send the request
        process.stdin.write(json.dumps(run_all_cells_request) + "\n")
        process.stdin.flush()
        
        # Read the response
        response = json.loads(process.stdout.readline())
        assert "result" in response, "No result in response"
        assert response["result"]["success"], "Failed to run all cells"
        print(f"✓ Successfully ran {response['result']['cells_executed']} cells")
        
        # Test 9: Delete a cell
        print("Test 9: Deleting a cell...")
        delete_cell_request = {
            "jsonrpc": "2.0",
            "id": "9",
            "method": "mcp.use_tool",
            "params": {
                "tool_name": "delete_cell",
                "parameters": {
                    "notebook_path": test_notebook_path,
                    "cell_id": markdown_cell_id
                }
            }
        }
        
        # Send the request
        process.stdin.write(json.dumps(delete_cell_request) + "\n")
        process.stdin.flush()
        
        # Read the response
        response = json.loads(process.stdout.readline())
        assert "result" in response, "No result in response"
        assert response["result"]["success"], "Failed to delete cell"
        print(f"✓ Successfully deleted cell with ID {markdown_cell_id}")
        
        # Test 10: Undo the deletion
        print("Test 10: Undoing last operation...")
        undo_request = {
            "jsonrpc": "2.0",
            "id": "10",
            "method": "mcp.use_tool",
            "params": {
                "tool_name": "undo_last_operation",
                "parameters": {
                    "notebook_path": test_notebook_path
                }
            }
        }
        
        # Send the request
        process.stdin.write(json.dumps(undo_request) + "\n")
        process.stdin.flush()
        
        # Read the response
        response = json.loads(process.stdout.readline())
        assert "result" in response, "No result in response"
        assert response["result"]["success"], "Failed to undo operation"
        print(f"✓ Successfully undid last operation")
        
        # Test 11: Check final notebook state
        print("Test 11: Verifying final notebook state...")
        final_read_request = {
            "jsonrpc": "2.0",
            "id": "11",
            "method": "mcp.use_tool",
            "params": {
                "tool_name": "read_notebook",
                "parameters": {
                    "notebook_path": test_notebook_path,
                    "include_outputs": True
                }
            }
        }
        
        # Send the request
        process.stdin.write(json.dumps(final_read_request) + "\n")
        process.stdin.flush()
        
        # Read the response
        response = json.loads(process.stdout.readline())
        assert "result" in response, "No result in response"
        assert "cells" in response["result"], "No cells in notebook"
        assert len(response["result"]["cells"]) == 2, f"Expected 2 cells, got {len(response['result']['cells'])}"
        print(f"✓ Final notebook verification successful")
        
        print("\nAll tests completed successfully!")
        
    except AssertionError as e:
        print(f"❌ Test failed: {str(e)}")
    finally:
        # Clean up
        process.terminate()
        shutil.rmtree(test_dir)

if __name__ == "__main__":
    test_mcp_server() 