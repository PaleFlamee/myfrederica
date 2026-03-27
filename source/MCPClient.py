import asyncio
import threading
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from typing import Any, Dict, List, Optional
import sys
import json
    
class _McpClientBase:
    def __init__(self):
        self.is_tool_updated = False
        self._tools_openai = None
        self._session = None
        self._exit_stack = None
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
    def _run(self, coro, timeout: float = 30):
        # 把协程提交到后台 loop，同步等待结果
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout)
    
    def list_tools(self) -> list:
        if self._tools_openai is None or self.is_tool_updated:
            self._tools_openai = self.get_openai_tool_definitions()
            self.is_tool_updated = False
        return self._tools_openai
        
    
    def call_tool(self, name: str, arguments_dict: dict) -> str:
        result = self._run(self._session.call_tool(name, arguments_dict))
        if result.content:
            return result.content[0].text
        return ""  # 或者返回一个错误提示字符串
    
    def get_openai_tool_definitions(self) -> list:
        tools_mcp = self._run(self._session.list_tools()).tools
        tools_openai = []
        for tool_mcp in tools_mcp:
            tools_openai.append({
                "type": "function",
                "function": {
                    "name": tool_mcp.name,
                    "description": tool_mcp.description,
                    "parameters": tool_mcp.inputSchema
                }
            })
        return tools_openai

class McpClientStdio(_McpClientBase):
    def __init__(self, server_script: str):
        super().__init__()
        self._server_script = server_script
        self._run(self._init_session()) # 同步等待初始化完成
        
    async def _init_session(self):
        from contextlib import AsyncExitStack
        self._exit_stack = AsyncExitStack()
        
        # 用 exit_stack 接管 context manager，不会在退出时自动关闭
        read, write = await self._exit_stack.enter_async_context(
            stdio_client(StdioServerParameters(
                command=sys.executable,
                args=[self._server_script]
            ))
        )
        self._session = await self._exit_stack.enter_async_context(
            ClientSession(read, write)
        )
        await self._session.initialize()
            
class McpClientSSE(_McpClientBase):
    def __init__(self, url: str, headers: Dict[str, Any]):
        super().__init__()
        self._url = url
        self.headers = headers
        self._run(self._init_session()) # 同步等待初始化完成
        
    async def _init_session(self):
        from contextlib import AsyncExitStack
        self._exit_stack = AsyncExitStack()
        
        # 用 exit_stack 接管 context manager，不会在退出时自动关闭
        read, write = await self._exit_stack.enter_async_context(
            sse_client(
                url=self._url,
                headers=self.headers
            )
        )
        self._session = await self._exit_stack.enter_async_context(
            ClientSession(read, write)
        )
        await self._session.initialize()

from tools.cron_manage_tool import TOOL_DEFINITION as cron_manage_tool_def, execute_tool_call as execute_cron_manage_tool

class ToolRegistry:
    def __init__(self, remote_mcp_servers:list[Dict[str, Dict[str, Any]]] = []): # list[{url:str, headers:{str:Any}}]
        self.tools = []
        self.tool_executors = {}

        self.tools.extend([cron_manage_tool_def])
        self.tool_executors["cron_manage"] = execute_cron_manage_tool

        import os
        script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "MCPServer.py")
        self.local_mcp_client = McpClientStdio(server_script=script_path)
        local_mcp_tools = self.local_mcp_client.list_tools()
        self.tools.extend(local_mcp_tools)
        for tool in local_mcp_tools:
            self.tool_executors[tool["function"]["name"]] = self.local_mcp_client.call_tool
        # temporarily ignoring remote mcp servers

    
    def execute(self, name, arguments_dict):
        return self.tool_executors[name](name, arguments_dict)
    def get_tools(self):
        return self.tools
