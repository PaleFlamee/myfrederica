# myfrederica

基于企业微信的 LLM 智能对话 Agent 框架。通过企业微信接收用户消息，调用 OpenAI 兼容的大语言模型生成回复，并借助 MCP（Model Context Protocol）工具系统执行文件操作、网络搜索、定时任务等自动化操作。

## 功能特性

- **企业微信集成** — 接收并回复企业微信消息，支持文本、图片、文件等多模态内容
- **多用户会话管理** — 每个用户独立的会话线程、聊天历史与记忆文件
- **MCP 工具系统** — 支持本地 stdio 和远程 SSE/HTTP 两种 MCP 服务器，可灵活扩展工具
- **内置工具集** — 文件读写、目录操作、Shell 命令执行、网页抓取、网络搜索等
- **定时任务** — 持久化 cron 任务，支持一次性和每日重复触发
- **HTTP 监控 API** — 内嵌 API 服务器，可查询运行状态、管理用户与任务

## 目录结构

```
myfrederica/
├── main.py                     # 主入口
├── APIServer.py                # 监控 HTTP API 服务器
├── MCPServer.py                # MCP 服务器实现
├── monitor_cli.py              # 监控命令行工具
├── requirements.txt
├── .env.example                # 环境变量模板
├── source/                     # 核心模块
│   ├── Config.py               # 配置加载
│   ├── Users.py                # 用户/会话管理
│   ├── Message.py              # 消息数据结构
│   ├── WeChatClient.py         # 企业微信 API 客户端
│   ├── WeChatServerV2.py       # 异步回调服务器
│   ├── MCPClient.py            # MCP 客户端与工具注册
│   ├── CronManagerV2.py        # 定时任务管理
│   └── Utils.py                # 工具函数
├── tools/                      # 内置工具实现
└── home/                       # 运行时数据（用户记忆、会话记录、配置）
    ├── soul                    # Agent 人格/系统提示
    ├── frederica               # 全局记忆
    ├── local_mcp_servers.json  # 本地 MCP 服务器配置
    ├── remote_mcp_servers.json # 远程 MCP 服务器配置
    ├── cron.json               # 定时任务持久化
    └── {user_id}/              # 每用户数据目录
        ├── sessions/           # 会话历史
        ├── memories/           # 用户记忆文件
        └── images/             # 用户图片缓存
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填写以下必要配置：

```env
# LLM（兼容 OpenAI API，可使用阿里云 DashScope 等）
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-max
LLM_MAX_TOKENS=8192
LLM_TEMPERATURE=0.7
LLM_ENABLE_THINKING=false

# 企业微信
WECHAT_WORK_CORPID=your_corpid
WECHAT_WORK_CORPSECRET=your_corpsecret
WECHAT_WORK_AGENTID=your_agentid
WECHAT_WORK_CALLBACK_TOKEN=your_token
WECHAT_WORK_ENCODING_AES_KEY=your_aes_key

# 回调服务器
SERVER_HOST=0.0.0.0
SERVER_PORT=8080

# 数据目录
HOME_DIRECTORY=home
USER_CONVERSATION_EXPIRE_TIMEOUT=30
```

### 3. 配置 MCP 服务器（可选）

编辑 `home/local_mcp_servers.json` 添加本地 MCP 工具服务器，格式与 Claude Desktop 一致：

```json
{
  "mcpServers": {
    "my-tool": {
      "command": "python",
      "args": ["path/to/server.py"]
    }
  }
}
```

### 4. 启动

```bash
python main.py
```

## 监控与管理

程序运行后，API 服务器默认监听 `localhost:20721`。使用命令行工具进行管理：

```bash
# 系统状态
python monitor_cli.py status

# 用户列表
python monitor_cli.py users

# 查看特定用户
python monitor_cli.py user {user_id}

# 向用户发送消息
python monitor_cli.py send {user_id} "消息内容"

# 定时任务管理
python monitor_cli.py cron list
python monitor_cli.py cron add --name "提醒" --user {user_id} --message "内容" --time "2026-01-01 09:00:00" --repeat daily
python monitor_cli.py cron delete --name "提醒"

# 重启用户会话
python monitor_cli.py restart {user_id}
```

详细说明见 [README_MONITOR.md](README_MONITOR.md)。

## 内置工具

| 工具 | 说明 |
|------|------|
| `read_file` | 读取文件内容 |
| `write_to_file` | 写入文件 |
| `replace_in_file` | 替换文件内容 |
| `list_file` | 列出目录内容 |
| `create_file_or_folder` | 创建文件或目录 |
| `delete_file_or_folder` | 删除文件或目录 |
| `execute_command` | 执行 Shell 命令 |
| `fetch_url` | 抓取网页内容（Jina Reader） |
| `web_search` | 网络搜索（阿里云 OpenSearch） |
| `cron_manage` | 管理定时任务 |

## 架构说明

```
企业微信回调
    │
    ▼
WeChatServerV2 (aiohttp 异步服务器)
    │  解密、解析消息
    ▼
UserManager.general_handle_new_message()
    │  路由到对应用户
    ▼
User.awaiting_queue
    │  消息聚合（10秒防抖）
    ▼
User.process_loop() 线程
    │  调用 LLM
    ▼
get_llm_response() → OpenAI 兼容 API
    │  处理工具调用
    ▼
ToolRegistry.execute() → MCP 工具
    │  返回结果，继续对话
    ▼
WeChatClient.send_text_message() → 企业微信
```

每个用户拥有独立的后台线程处理消息，会话超时后自动触发记忆整理和告别流程。

## 依赖

```
python-dotenv   # 环境变量
openai          # LLM API 客户端
wechatpy        # 企业微信加解密
requests        # HTTP 客户端
aiohttp         # 异步 HTTP 服务器
mcp             # Model Context Protocol
psutil          # 系统监控（monitor_cli 使用）
```

## License

MIT License — Copyright 2026 PaleFlame
