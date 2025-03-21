import json
import sys
import logging
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("mcp_server.log"), logging.StreamHandler()]
)
logger = logging.getLogger("mcp_server")

class MCPServer:
    def __init__(self, tools):
        self.tools = {tool["name"]: tool for tool in tools}
        self.tool_handlers = self._load_tool_handlers()
    
    def _load_tool_handlers(self):
        # Import tool handlers
        from tool_handlers import (
            read_notebook, write_notebook, create_notebook,
            add_cell, edit_cell, delete_cell, execute_cell, get_outputs,
            run_all_cells, undo_last_operation, notebook_diff
        )
        
        # Map tool names to handler functions
        return {
            "read_notebook": read_notebook,
            "write_notebook": write_notebook,
            "create_notebook": create_notebook,
            "add_cell": add_cell,
            "edit_cell": edit_cell,
            "delete_cell": delete_cell,
            "execute_cell": execute_cell,
            "get_outputs": get_outputs,
            "run_all_cells": run_all_cells,
            "undo_last_operation": undo_last_operation,
            "notebook_diff": notebook_diff
        }
    
    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})
        
        logger.info(f"Received request: {method} with ID {request_id}")
        
        if method == "mcp.list_tools":
            return self._handle_list_tools(request_id)
        elif method == "mcp.use_tool":
            return self._handle_use_tool(request_id, params)
        else:
            logger.error(f"Method {method} not found")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method {method} not found"
                }
            }
    
    def _handle_list_tools(self, request_id: str) -> Dict[str, Any]:
        logger.info("Listing available tools")
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": list(self.tools.values())
        }
    
    def _handle_use_tool(self, request_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        tool_name = params.get("tool_name")
        tool_params = params.get("parameters", {})
        
        logger.info(f"Using tool: {tool_name} with parameters: {tool_params}")
        
        if tool_name not in self.tool_handlers:
            logger.error(f"Tool {tool_name} not found")
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
            logger.error(f"Error executing tool {tool_name}: {str(e)}", exc_info=True)
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
        logger.info("MCP server started")
        for line in sys.stdin:
            try:
                request = json.loads(line)
                response = self.handle_request(request)
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
            except json.JSONDecodeError:
                logger.error("Invalid JSON received")
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
    # Import tool definitions
    from tool_definitions import tools
    
    # Start the server
    server = MCPServer(tools)
    server.run() 