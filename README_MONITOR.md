# 主程序监控和管理工具

## 概述

这是一个用于监控和管理正在运行的 `main.py` 程序的命令行工具。通过HTTP API提供实时状态监控和控制功能。

## 架构

1. **APIServer.py** - 嵌入在主程序中的HTTP API服务器
2. **monitor_cli.py** - 命令行工具，通过HTTP API与主程序交互
3. **main.py** - 修改后的主程序，集成API服务器

## 功能特性

### 监控功能
- ✅ 系统状态监控（CPU、内存、运行时间）
- ✅ 用户状态监控（活跃用户、会话信息）
- ✅ 定时任务监控（任务状态、执行历史）
- ✅ 进程信息监控（线程数、打开文件数）

### 控制功能
- ✅ 向用户发送消息
- ✅ 管理定时任务（创建、删除、列出）
- ✅ 重启用户会话
- ✅ 实时状态查询

## 安装和使用

### 1. 启动主程序
```bash
python main.py
```

主程序启动时会自动启动API服务器（默认端口：8080）：
```
API服务器已启动，可通过 http://localhost:8080 访问
使用 monitor_cli.py 工具进行监控和管理
```

### 2. 使用命令行工具

#### 查看系统状态
```bash
python monitor_cli.py status
```

#### 列出所有用户
```bash
python monitor_cli.py users
```

#### 查看特定用户信息
```bash
python monitor_cli.py user ivybridge
```

#### 发送消息给用户
```bash
python monitor_cli.py send ivybridge "Hello, this is a test message"
```

#### 管理定时任务
```bash
# 列出所有定时任务
python monitor_cli.py cron list

# 添加定时任务
python monitor_cli.py cron add --name "提醒吃饭" --user ivybridge --message "该吃饭了" --time "2024-03-12 18:00:00" --repeat daily

# 删除定时任务
python monitor_cli.py cron delete --name "提醒吃饭"
```

#### 重启用户会话
```bash
python monitor_cli.py restart ivybridge
```

### 3. 高级选项

#### 使用JSON格式输出
```bash
python monitor_cli.py --json status
```

#### 指定API服务器地址
```bash
python monitor_cli.py --url http://192.168.1.100:8080 status
```

## API接口

### GET /api/status
获取系统状态信息

### GET /api/users
获取用户列表

### GET /api/user/{user_id}
获取特定用户信息

### GET /api/cron
获取定时任务列表

### POST /api/message
发送消息给用户
```json
{
  "user_id": "ivybridge",
  "message": "Hello"
}
```

### POST /api/cron
管理定时任务
```json
{
  "action": "add",
  "name": "提醒",
  "target_user": "ivybridge",
  "message": "该吃饭了",
  "target_time": "2024-03-12 18:00:00",
  "repeat": "daily"
}
```

### POST /api/user/restart
重启用户会话
```json
{
  "user_id": "ivybridge"
}
```

## 技术细节

### 依赖项
- `psutil` - 系统资源监控（已安装）
- `requests` - HTTP客户端（已安装）

### 端口配置
默认端口：8080
可以在 `main.py` 中修改：
```python
api_server = APIServer(host="localhost", port=8080)
```

### 错误处理
- 命令行工具会显示友好的错误信息
- API服务器返回标准的HTTP状态码和JSON错误信息
- 连接失败时会提示检查主程序是否运行

## 测试

运行测试脚本验证功能：
```bash
python test_api.py
```

## 故障排除

### 1. 无法连接到API服务器
```
错误: 无法连接到API服务器，请确保主程序正在运行
```
解决方案：启动主程序 `python main.py`

### 2. 端口冲突
```
错误: Failed to start API server: [Errno 10048]
```
解决方案：修改端口号或关闭占用8080端口的程序

### 3. 缺少依赖
```
ModuleNotFoundError: No module named 'psutil'
```
解决方案：安装依赖 `pip install psutil`

## 扩展开发

### 添加新的监控指标
1. 在 `APIServer.py` 的 `_collect_system_status` 方法中添加新的指标
2. 在 `monitor_cli.py` 的 `get_status` 方法中显示新指标

### 添加新的控制功能
1. 在 `APIServer.py` 中添加新的API端点
2. 在 `monitor_cli.py` 中添加对应的命令行命令
3. 更新帮助信息和文档

## 安全考虑

当前版本为开发环境设计，生产环境建议：
1. 添加API密钥认证
2. 使用HTTPS加密通信
3. 限制访问IP地址
4. 添加请求频率限制

## 性能影响

API服务器使用独立的线程运行，对主程序性能影响极小：
- 内存占用：约5-10MB
- CPU使用：仅在请求时处理
- 网络带宽：JSON数据量小

## 许可证

本项目基于原有项目的许可证。