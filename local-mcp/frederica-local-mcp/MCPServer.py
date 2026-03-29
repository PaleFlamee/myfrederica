# Local tools briding MCP server

import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types
import json
import logging
import logging.handlers
import sys

# MCPServer 以子进程运行，stdout 归 MCP 协议（JSON-RPC），日志只能写 stderr + 独立文件
_fmt = logging.Formatter(
    '<%(asctime)s>{%(levelname)s}[%(name)s]: %(message)s',
    datefmt='%Y-%m-%d@%H:%M:%S'
)
_root = logging.getLogger()
_root.setLevel(logging.DEBUG)
_sh = logging.StreamHandler(sys.stderr)
_sh.setLevel(logging.DEBUG)
_sh.setFormatter(_fmt)
_root.addHandler(_sh)
_fh = logging.handlers.RotatingFileHandler(
    'mcp_server.log', maxBytes=10_485_760, backupCount=3, encoding='utf-8'
)
_fh.setLevel(logging.DEBUG)
_fh.setFormatter(_fmt)
_root.addHandler(_fh)

logger = logging.getLogger(__name__)

app = Server("frederica-tools")


from tools.create_file_or_folder_tool import execute_tool_call as execute_create_file_tool, TOOL_DEFINITION as create_file_tool_def
from tools.delete_file_or_folder_tool import execute_tool_call as execute_delete_file_tool, TOOL_DEFINITION as delete_file_tool_def
from tools.read_file_tool import execute_tool_call as execute_read_file_tool, TOOL_DEFINITION as read_file_tool_def
from tools.list_file_tool import execute_tool_call as execute_list_file_tool, TOOL_DEFINITION as list_file_tool_def
from tools.write_to_file_tool import execute_tool_call as execute_write_file_tool, TOOL_DEFINITION as write_file_tool_def
from tools.replace_in_file_tool import execute_tool_call as execute_replace_file_tool, TOOL_DEFINITION as replace_file_tool_def
from tools.execute_command_tool import execute_tool_call as execute_execute_command_tool, TOOL_DEFINITION as execute_command_tool_def
from tools.fetch_url_tool import execute_tool_call as execute_fetch_url_tool, TOOL_DEFINITION as fetch_url_tool_def
from tools.web_search_ali_tool import execute_tool_call as execute_web_search_tool, TOOL_DEFINITION as web_search_tool_def
from tools.search_markdown_tool import execute_tool_call as execute_search_markdown_tool, TOOL_DEFINITION as search_markdown_tool_def
TOOL_EXECUTORS = {
    "list_files": execute_list_file_tool,
    "read_file": execute_read_file_tool,
    "create_file_or_folder": execute_create_file_tool,
    "write_file": execute_write_file_tool,
    "delete_file_or_folder": execute_delete_file_tool,
    "replace_in_file": execute_replace_file_tool,
    "web_search_ali": execute_web_search_tool,
    "fetch_url_markdown": execute_fetch_url_tool,
    "execute_command": execute_execute_command_tool,
    "search_markdown_titles": execute_search_markdown_tool,
}
def openai_to_mcp_tool(tool_def:dict)->types.Tool:
    name = tool_def["function"]["name"]
    logger.debug(f"Converting OpenAI tool definition to MCP: {name}")
    return types.Tool(
        name=name,
        description=tool_def["function"]["description"],
        inputSchema=tool_def["function"]["parameters"]
    )


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    logger.debug("list_tools called")
    tools = [
        openai_to_mcp_tool(create_file_tool_def),
        openai_to_mcp_tool(delete_file_tool_def),
        openai_to_mcp_tool(read_file_tool_def),
        openai_to_mcp_tool(list_file_tool_def),
        openai_to_mcp_tool(write_file_tool_def),
        openai_to_mcp_tool(replace_file_tool_def),
        openai_to_mcp_tool(execute_command_tool_def),
        openai_to_mcp_tool(fetch_url_tool_def),
        openai_to_mcp_tool(web_search_tool_def),
        openai_to_mcp_tool(search_markdown_tool_def),
    ]
    logger.info(f"Listing {len(tools)} tools")
    return tools

@app.call_tool()
async def call_tool(name: str, arguments_dict: dict) -> list[types.TextContent]:
    logger.info(f"call_tool: {name}, args={arguments_dict}")
    if not name in TOOL_EXECUTORS:
        logger.warning(f"Tool not found: {name}")
        return [types.TextContent(type="text", text=f"Local MCP Server Exception: Tool {name} Not Found")]
    try:
        tool_response = TOOL_EXECUTORS[name](arguments_dict)
        logger.debug(f"Tool {name} returned {len(tool_response)} chars")
        return [
            types.TextContent(
                type="text",
                text=tool_response
            )
        ]
    except Exception as e:
        logger.exception(f"Exception while executing tool {name}")
        return [types.TextContent(type="text", text=f"Local MCP Server Exception: {e}")]

async def main():
    logger.info("MCPServer starting")
    async with stdio_server() as (read, write):
        logger.info("stdio_server ready")
        await app.run(read, write, app.create_initialization_options())
    logger.info("MCPServer stopped")


if __name__ == "__main__":
    asyncio.run(main())