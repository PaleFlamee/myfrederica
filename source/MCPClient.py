import asyncio
import threading
import logging
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from typing import Any, Dict, List, Optional
import os

logger = logging.getLogger(__name__)
    
class _McpClientBase:
    def __init__(self):
        self.is_tool_updated = False
        self._tools_openai = None
        self._session = None
        self._exit_stack = None
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        logger.debug(f"{self.__class__.__name__}: background event loop thread started")
    def _run(self, coro, timeout: float = 30):
        # 把协程提交到后台 loop，同步等待结果
        logger.debug(f"_run: submitting coroutine to background loop (timeout={timeout}s)")
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout)
    
    def list_tools(self) -> list:
        if self._tools_openai is None or self.is_tool_updated:
            logger.debug("list_tools: cache miss, fetching from server")
            self._tools_openai = self.get_openai_tool_definitions()
            self.is_tool_updated = False
        else:
            logger.debug("list_tools: returning cached tool list")
        return self._tools_openai
        
    
    def call_tool(self, name: str, arguments_dict: dict) -> str:
        logger.info(f"call_tool: {name}, args={arguments_dict}")
        result = self._run(self._session.call_tool(name, arguments_dict))
        if result.content:
            logger.debug(f"call_tool {name}: got response, {len(result.content[0].text)} chars")
            return result.content[0].text
        logger.warning(f"call_tool {name}: empty content in response")
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
        logger.info(f"get_openai_tool_definitions: fetched {len(tools_openai)} tools from server")
        return tools_openai

class McpClientStdio(_McpClientBase):
    def __init__(self, command: str, args: List[str], env: Optional[Dict[str, str]] = None):
        super().__init__()        
        self._command = command
        self._args = args
        self._env = env
        logger.info(f"McpClientStdio: initializing with {command},{args},{env}")
        self._run(self._init_session()) # 同步等待初始化完成
        logger.info("McpClientStdio: session initialized")
        
    async def _init_session(self):
        from contextlib import AsyncExitStack
        self._exit_stack = AsyncExitStack()
        
        # 用 exit_stack 接管 context manager，不会在退出时自动关闭
        logger.debug("McpClientStdio._init_session: launching subprocess and opening stdio transport")
        read, write = await self._exit_stack.enter_async_context(
            stdio_client(StdioServerParameters(
                command=self._command,
                args=self._args,
                env=self._env
            ))
        )
        logger.debug("McpClientStdio._init_session: stdio transport ready, creating ClientSession")
        self._session = await self._exit_stack.enter_async_context(
            ClientSession(read, write)
        )
        await self._session.initialize()
        logger.debug("McpClientStdio._init_session: MCP session initialized")
            
class McpClientSSE(_McpClientBase):
    def __init__(self, url: str, headers: Dict[str, Any]):
        super().__init__()
        self._url = url
        self.headers = headers
        logger.info(f"McpClientSSE: initializing with url={url}")
        self._run(self._init_session(), timeout=60) # 同步等待初始化完成
        logger.info("McpClientSSE: session initialized")
        
    async def _init_session(self):
        from contextlib import AsyncExitStack
        self._exit_stack = AsyncExitStack()
        
        # 用 exit_stack 接管 context manager，不会在退出时自动关闭
        logger.debug(f"McpClientSSE._init_session: connecting to {self._url}")
        read, write = await self._exit_stack.enter_async_context(
            sse_client(
                url=self._url,
                headers=self.headers
            )
        )
        logger.debug("McpClientSSE._init_session: SSE transport ready, creating ClientSession")
        self._session = await self._exit_stack.enter_async_context(
            ClientSession(read, write)
        )
        await self._session.initialize()
        logger.debug("McpClientSSE._init_session: MCP session initialized")

class McpClientStreamableHTTP(_McpClientBase):
    def __init__(self, url: str, headers: Dict[str, Any]):
        super().__init__()
        self._url = url
        self.headers = headers
        logger.info(f"McpClientStreamableHTTP: initializing with url={url}")
        self._run(self._init_session(), timeout=60) # 同步等待初始化完成
        logger.info("McpClientStreamableHTTP: session initialized")
        
    async def _init_session(self):
        from contextlib import AsyncExitStack
        import httpx
        from mcp.client.streamable_http import streamable_http_client
        
        self._exit_stack = AsyncExitStack()
        
        logger.debug(f"McpClientStreamableHTTP._init_session: connecting to {self._url}")
        
        # headers 通过 httpx.AsyncClient 传入，需要手动管理生命周期
        http_client = httpx.AsyncClient(headers=self.headers)
        await self._exit_stack.enter_async_context(http_client)
        
        read, write, _ = await self._exit_stack.enter_async_context(
            streamable_http_client(self._url, http_client=http_client)
        )
        logger.debug("McpClientStreamableHTTP._init_session: transport ready, creating ClientSession")
        self._session = await self._exit_stack.enter_async_context(
            ClientSession(read, write)
        )
        await self._session.initialize()
        logger.debug("McpClientStreamableHTTP._init_session: MCP session initialized")

from tools.cron_manage_tool import TOOL_DEFINITION as cron_manage_tool_def, execute_tool_call as execute_cron_manage_tool

class ToolRegistry:
    def __init__(self, local_mcp_servers:Dict[str, Dict[str, Any]] = {},\
                 remote_mcp_servers:Dict[str, Dict[str, Any]] = {}): # [name:{url:str, headers:{str:Any}}]
        logger.info("ToolRegistry: initializing")
        self.tools = []
        self.tool_executors = {}

        self.tools.extend([cron_manage_tool_def])
        self.tool_executors["cron_manage"] = execute_cron_manage_tool
        logger.debug("ToolRegistry: registered direct tool: cron_manage")

        # import os
        # script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "MCPServer.py")
        # logger.info(f"ToolRegistry: connecting to local MCP server: {script_path}")
        # self.local_mcp_client = McpClientStdio(server_script=script_path)
        # local_mcp_tools = self.local_mcp_client.list_tools()
        # self.tools.extend(local_mcp_tools)
        # for tool in local_mcp_tools:
        #     self.tool_executors[tool["function"]["name"]] = self.local_mcp_client.call_tool
        # logger.info(f"ToolRegistry: registered {len(local_mcp_tools)} tools from local MCP server")
        
        for server_name, server_cfg in local_mcp_servers.items():
            try:
                if "command" in server_cfg:
                    local_mcp_client = McpClientStdio(
                        command=server_cfg["command"],
                        args=server_cfg.get("args", []),
                        env=server_cfg.get("env", None)
                    )
                elif "url" in server_cfg:
                    server_type = server_cfg.get("type", "streamable_http")
                    if server_type == "sse":
                        local_mcp_client = McpClientSSE(server_cfg["url"], server_cfg.get("headers", {}))
                    else:
                        local_mcp_client = McpClientStreamableHTTP(server_cfg["url"], server_cfg.get("headers", {}))
                else:
                    logger.error(f"ToolRegistry: {server_name} has neither 'command' nor 'url', skipping")
                    continue

                local_mcp_tools = local_mcp_client.list_tools()
                self.tools.extend(local_mcp_tools)
                for tool in local_mcp_tools:
                    self.tool_executors[tool["function"]["name"]] = local_mcp_client.call_tool
                logger.info(f"ToolRegistry: registered {len(local_mcp_tools)} tools from {server_name}")

            except Exception as e:
                logger.error(f"ToolRegistry: failed to connect to {server_name} ({server_cfg}): {e}, skipping")

        for server_name, server_cfg in remote_mcp_servers.items():
            url = server_cfg["url"]
            headers = server_cfg.get("headers", {})
            logger.info(f"ToolRegistry: connecting to remote MCP server: {server_name} @ {url}")
            try:
                remote_mcp_client = McpClientStreamableHTTP(url, headers)
                remote_mcp_tools = remote_mcp_client.list_tools()
                self.tools.extend(remote_mcp_tools)
                for tool in remote_mcp_tools:
                    self.tool_executors[tool["function"]["name"]] = remote_mcp_client.call_tool
                logger.info(f"ToolRegistry: registered {len(remote_mcp_tools)} tools from {server_name}")
            except Exception as e:
                logger.error(f"ToolRegistry: failed to connect to {server_name} @ {url}: {e}, skipping")
        logger.info(f"ToolRegistry: ready, total {len(self.tools)} tools available")

    
    def execute(self, name, arguments_dict):
        logger.debug(f"ToolRegistry.execute: {name}")
        if name not in self.tool_executors:
            logger.error(f"ToolRegistry.execute: unknown tool '{name}'")
            return f"Tool not found: {name}"
        return self.tool_executors[name](name, arguments_dict)

    def get_tools(self):
        return self.tools
