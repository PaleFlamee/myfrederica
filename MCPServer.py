# Local tools briding MCP server

import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types
import json

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
    return types.Tool(
        name=tool_def["function"]["name"],
        description=tool_def["function"]["description"],
        inputSchema=tool_def["function"]["parameters"]
    )


@app.list_tools()
async def list_tools() -> list[types.Tool]:

    return [
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

@app.call_tool()
async def call_tool(name: str, arguments_dict: dict) -> list[types.TextContent]:
    tool_response=TOOL_EXECUTORS[name]({
        "function": { # 兼容层，以后删掉
            "name": name,
            "arguments": json.dumps(arguments_dict)
        }
    })
    return [
        types.TextContent(
            type="text",
            text=tool_response
        )
    ]

async def main():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())