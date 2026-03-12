# WeChatServer 使用说明

## 概述

这是一个简洁的企业微信回调服务器，用于处理企业微信的消息回调。服务器接收企业微信的加密消息，解密后转发给UserManager进行处理，并返回响应。

## 功能特性

1. **企业微信服务器验证**：处理GET请求，完成企业微信服务器的URL验证
2. **消息接收与解密**：接收并解密企业微信的加密消息
3. **消息处理**：将文本消息转发给UserManager进行异步处理
4. **错误处理**：完善的错误处理和日志记录
5. **简洁设计**：代码简洁精干，逻辑清晰

## 环境变量配置

在`.env`文件中配置以下环境变量：

```bash
# 企业微信必要配置
WECHAT_WORK_CORPID=your_corpid_here
WECHAT_WORK_CALLBACK_TOKEN=your_token_here
WECHAT_WORK_ENCODING_AES_KEY=your_aes_key_here

# 服务器配置（可选，有默认值）
SERVER_HOST=0.0.0.0  # 监听地址，默认0.0.0.0
SERVER_PORT=8888     # 监听端口，默认8888

# 其他企业微信配置（可选）
WECHAT_WORK_CORPSECRET=your_corpsecret_here
WECHAT_WORK_AGENTID=your_agentid_here
```

## 快速开始

### 1. 安装依赖

```bash
pip install wechatpy python-dotenv
```

### 2. 配置环境变量

复制`.env.example`为`.env`并填写正确的企业微信配置：

```bash
cp .env.example .env
# 编辑.env文件，填写企业微信配置
```

### 3. 启动服务器

#### 方式一：直接运行

```python
from source.WeChatServer import run_wechat_server

if __name__ == "__main__":
    run_wechat_server()
```

#### 方式二：使用WeChatServer类

```python
from source.WeChatServer import WeChatServer

server = WeChatServer()
server.start()  # 阻塞运行，按Ctrl+C停止
```

#### 方式三：命令行运行

```bash
python -m source.WeChatServer
```

### 4. 配置企业微信回调

在企业微信管理后台配置回调URL：
- URL: `http://你的域名或IP:8888/callback`
- Token: 与`.env`中的`WECHAT_WORK_CALLBACK_TOKEN`一致
- EncodingAESKey: 与`.env`中的`WECHAT_WORK_ENCODING_AES_KEY`一致

## 代码结构

```
WeChatServer.py
├── WeChatCallbackHandler (HTTP请求处理器)
│   ├── do_GET()          # 处理企业微信服务器验证
│   ├── do_POST()         # 处理企业微信消息
│   └── _handle_message() # 消息处理逻辑
└── WeChatServer (服务器主类)
    ├── __init__()        # 初始化配置验证
    ├── start()           # 启动服务器
    └── stop()            # 停止服务器
```

## 消息处理流程

1. **接收请求**：企业微信发送加密消息到`/callback`端点
2. **参数验证**：检查必要的查询参数(msg_signature, timestamp, nonce)
3. **消息解密**：使用wechatpy库解密消息
4. **消息解析**：解析XML消息为Message对象
5. **消息处理**：
   - 文本消息：转发给UserManager
   - 事件消息：记录日志
   - 其他消息：记录日志
6. **返回响应**：加密响应并返回给企业微信

## 与UserManager集成

服务器会自动检测UserManager的可用性：

- 如果`source.Users`模块可用，文本消息会被转发到UserManager
- 如果不可用，只记录日志，不影响基本功能

```python
# 自动集成示例
if USER_MANAGER_AVAILABLE:
    user_manager = UserManager()
    user_manager.new_message(
        user_id=user_id,
        incoming_message_queue=[
            Message(content=content, role="user")
        ]
    )
```

## 日志记录

服务器使用现有的日志系统，只记录warning和error级别的日志：

- **错误日志(error)**：记录关键错误，如配置缺失、解密失败等
- **警告日志(warning)**：记录重要事件，如服务器启动、消息接收等
- **不记录info/debug日志**：保持日志简洁

## 错误处理

1. **配置验证**：启动时检查必要环境变量，缺失则抛出异常
2. **请求验证**：缺少必要参数返回400错误
3. **解密失败**：返回400错误
4. **处理异常**：即使处理出错也返回success，避免企业微信重试
5. **服务器错误**：返回500错误

## 测试

提供了完整的测试脚本：

```bash
# 运行测试
python test_wechat_server.py
```

测试内容包括：
- 配置验证测试
- 处理器初始化测试
- 服务器功能测试

## 注意事项

1. **企业微信要求**：必须在5秒内返回响应，因此实际消息处理是异步的
2. **加密要求**：AES Key必须是43位（32字节Base64编码）
3. **网络要求**：服务器需要能被企业微信服务器访问（公网IP或内网穿透）
4. **性能考虑**：使用简单的HTTPServer，适合中小规模使用

## 扩展建议

1. **增加认证**：可添加IP白名单验证
2. **性能优化**：可替换为异步服务器（如aiohttp）
3. **监控集成**：可添加健康检查端点
4. **配置管理**：可支持配置文件和环境变量多种方式

## 故障排除

### 常见问题

1. **服务器启动失败**
   - 检查端口是否被占用
   - 检查环境变量配置

2. **企业微信验证失败**
   - 检查Token、EncodingAESKey是否正确
   - 检查服务器时间是否同步

3. **消息接收失败**
   - 检查网络连通性
   - 检查日志中的错误信息

### 日志查看

查看`app.log`文件获取详细错误信息。

## 版本历史

- v1.0.0: 初始版本，基本功能实现
- 参考`source/legacy/wechat_server.py`的简化版本