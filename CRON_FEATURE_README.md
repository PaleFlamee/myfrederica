# Cron任务功能使用说明

## 功能概述

已成功为项目添加了cron任务功能，包含以下两部分：

1. **CronManager类**：负责管理定时任务，自动检查并执行到期的cron任务
2. **cron_manage_tool工具**：LLM可用的工具，支持create、delete、list三个功能

## 文件结构

```
source/
├── CronManager.py          # CronManager类实现
├── Users.py               # 已集成cron_manage_tool工具
└── ...

main.py                    # 已集成CronManager初始化
home/cron.json            # cron任务存储文件（JSON格式）
```

## 使用方法

### 1. 启动应用

直接运行 `main.py`，CronManager会自动启动：

```bash
python main.py
```

### 2. 控制台快捷命令

在应用运行时的控制台中，可以使用以下快捷命令：

- `cron list` - 列出所有cron任务
- `cron cleanup` - 清理7天前的过期任务
- `exit` - 退出应用

### 3. 通过LLM使用cron_manage_tool

LLM现在可以使用 `cron_manage` 工具来管理定时任务：

#### 创建cron任务
```json
{
  "action": "create",
  "name": "提醒吃饭",
  "target_user": "ivybridge",
  "message": "该吃饭了！",
  "target_time": "2024-03-12 18:00:00"
}
```

#### 删除cron任务
```json
{
  "action": "delete",
  "name": "提醒吃饭"
}
```

#### 列出cron任务
```json
{
  "action": "list"
}
```

#### 按状态过滤列出任务
```json
{
  "action": "list",
  "filter_status": "pending"
}
```

### 4. Cron任务数据结构

cron任务以JSON格式存储在 `home/cron.json`：

```json
{
  "cron_tasks": [
    {
      "id": "hash_value",
      "name": "任务名称",
      "target_user": "用户ID",
      "message": "要发送的消息内容",
      "target_time": "2024-03-12 18:00:00",
      "status": "pending",  // pending, executing, executed, error
      "created_at": "2024-03-12 10:00:00",
      "created_by": "创建者",
      "executed_at": null,
      "error_message": null
    }
  ],
  "version": "1.0"
}
```

## 工作原理

### CronManager线程
- 在 `main.py` 中创建并启动
- 每分钟检查一次到期的cron任务
- 到期任务会自动添加到对应用户的 `awaiting_queue`
- 执行后任务状态更新为 `executed`

### 错误处理
- 用户不存在时，任务状态标记为 `error`
- 时间格式错误会被捕获并提示
- 重复任务名称会被拒绝

### 任务ID生成
使用MD5哈希生成12位ID，基于：`name:target_user:target_time:message`

## 测试验证

已通过完整测试，包括：
- ✅ CronManager基本功能（添加、删除、列出）
- ✅ 文件保存和加载
- ✅ ID生成一致性
- ✅ cron_manage_tool工具功能
- ✅ 错误处理

## 示例对话

用户：帮我设置一个明天早上9点的提醒

LLM响应（使用cron_manage工具）：
```json
{
  "action": "create",
  "name": "明天早上提醒",
  "target_user": "ivybridge",
  "message": "早上好！这是明天的提醒。",
  "target_time": "2024-03-13 09:00:00"
}
```

工具响应：
```
✅ 成功创建cron任务：明天早上提醒
   ID: a1b2c3d4e5f6
   目标用户: ivybridge
   执行时间: 2024-03-13 09:00:00
   状态: pending
```

## 注意事项

1. 时间格式必须为 `YYYY-MM-DD HH:MM:SS`
2. 任务名称必须唯一
3. 目标用户必须存在（否则任务会标记为error）
4. CronManager线程为守护线程，主程序退出时会自动停止
5. 每分钟检查一次，适合分钟级精度的定时任务