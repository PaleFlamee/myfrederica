#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cron_manage_tool.py
供LLM使用的cron任务管理工具
支持创建、删除、列出cron任务
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# 全局CronManager实例（将在main.py中设置）
_global_cron_manager = None

def set_global_cron_manager(cron_manager):
    """设置全局CronManager实例"""
    global _global_cron_manager
    _global_cron_manager = cron_manager

def get_global_cron_manager():
    """获取全局CronManager实例"""
    return _global_cron_manager

def cron_manage_tool_execute(tool_call: Dict[str, Any]) -> str:
    """
    Cron任务管理工具
    支持create、delete、list操作
    
    Args:
        tool_call: 包含工具调用信息的字典
        
    Returns:
        str: 工具执行结果
    """
    try:
        # 解析参数
        function_name = tool_call["function"]["name"]
        arguments_str = tool_call["function"]["arguments"]
        arguments = json.loads(arguments_str)
        
        # 验证工具名称
        if function_name != "cron_manage":
            return f"错误：未知的工具 '{function_name}'"
        
        # 获取CronManager实例
        cron_manager = get_global_cron_manager()
        if cron_manager is None:
            return "错误：CronManager未初始化，无法管理cron任务"
        
        # 提取参数
        action = arguments.get("action")
        
        if action == "create":
            # 创建cron任务
            name = arguments.get("name")
            target_user = arguments.get("target_user")
            message = arguments.get("message")
            target_time = arguments.get("target_time")
            
            if not all([name, target_user, message, target_time]):
                return "错误：创建cron任务需要提供name、target_user、message、target_time参数"
            
            # 获取当前用户作为创建者
            created_by = "system"  # 这里可以改进为从上下文获取实际用户
            
            cron_task = cron_manager.add_cron_task(
                name=name,
                target_user=target_user,
                message=message,
                target_time=target_time,
                created_by=created_by
            )
            
            return f"✅ 成功创建cron任务：{name}\n" \
                   f"   ID: {cron_task['id']}\n" \
                   f"   目标用户: {target_user}\n" \
                   f"   执行时间: {target_time}\n" \
                   f"   状态: {cron_task['status']}"
        
        elif action == "delete":
            # 删除cron任务
            name = arguments.get("name")
            
            if not name:
                return "错误：删除cron任务需要提供name参数"
            
            success = cron_manager.delete_cron_task(name)
            if success:
                return f"✅ 成功删除cron任务：{name}"
            else:
                return f"⚠️ 未找到cron任务：{name}"
        
        elif action == "list":
            # 列出cron任务
            filter_status = arguments.get("filter_status")
            
            tasks = cron_manager.list_cron_tasks(filter_status=filter_status)
            
            if not tasks:
                if filter_status:
                    return f"📋 没有状态为 '{filter_status}' 的cron任务"
                else:
                    return "📋 当前没有cron任务"
            
            result = f"📋 共找到 {len(tasks)} 个cron任务：\n\n"
            for i, task in enumerate(tasks, 1):
                result += f"{i}. {task['name']} (ID: {task['id']})\n"
                result += f"   目标用户: {task['target_user']}\n"
                result += f"   执行时间: {task['target_time']}\n"
                result += f"   状态: {task['status']}\n"
                result += f"   创建时间: {task['created_at']}\n"
                if task['executed_at']:
                    result += f"   执行时间: {task['executed_at']}\n"
                if task['error_message']:
                    result += f"   错误信息: {task['error_message']}\n"
                result += "\n"
            
            return result
        
        else:
            return f"错误：不支持的操作 '{action}'，支持的操作有：create、delete、list"
    
    except ValueError as e:
        return f"❌ 操作失败：{str(e)}"
    except json.JSONDecodeError:
        return "错误：无法解析工具参数（无效的JSON格式）"
    except KeyError as e:
        return f"错误：工具调用格式不正确 - 缺少字段: {str(e)}"
    except Exception as e:
        logger.error(f"cron_manage_tool执行出错: {e}")
        return f"❌ 系统错误：{str(e)}"

# 工具定义（符合OpenAI工具调用规范）
TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "cron_manage",
        "description": (
            "管理定时任务（cron任务）。支持创建、删除、列出cron任务。\n"
            "创建任务示例：{\"action\": \"create\", \"name\": \"Remind ivybridge to eat\", \"target_user\": \"ivybridge\", \"message\": \"Frederica, seeing this message means a cron to remind ivybridge to eat has been triggered.\", \"target_time\": \"2024-03-12 18:00:00\"}\n"
            "删除任务示例：{\"action\": \"delete\", \"name\": \"Remind ivybridge to eat\"}\n"
            "列出任务示例：{\"action\": \"list\"} 或 {\"action\": \"list\", \"filter_status\": \"pending\"}"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "delete", "list"],
                    "description": "操作类型：create创建、delete删除、list列出"
                },
                "name": {
                    "type": "string",
                    "description": "任务名称（create/delete时必填）"
                },
                "target_user": {
                    "type": "string",
                    "description": "目标用户ID（create时必填）"
                },
                "message": {
                    "type": "string",
                    "description": "定时任务触发时用来提示Frederica的信息（create时必填）"
                },
                "target_time": {
                    "type": "string",
                    "description": "执行时间，格式：YYYY-MM-DD HH:MM:SS（create时必填）"
                },
                "filter_status": {
                    "type": "string",
                    "enum": ["pending", "executing", "executed", "error"],
                    "description": "过滤状态（list时可选）"
                }
            },
            "required": ["action"]
        }
    }
}

def execute_tool_call(tool_call: Dict[str, Any]) -> str:
    """
    执行工具调用（兼容现有工具系统）
    
    Args:
        tool_call: 包含工具调用信息的字典
        
    Returns:
        str: 工具执行结果
    """
    return cron_manage_tool_execute(tool_call)

def demo_llm_interaction():
    """
    演示LLM如何调用此工具
    """
    print("=== LLM Cron任务管理工具演示 ===\n")
    
    # 模拟CronManager
    class MockCronManager:
        def __init__(self):
            self.tasks = []
            self.task_id_counter = 1
        
        def add_cron_task(self, name, target_user, message, target_time, created_by):
            task = {
                "id": f"mock_id_{self.task_id_counter}",
                "name": name,
                "target_user": target_user,
                "message": message,
                "target_time": target_time,
                "status": "pending",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "created_by": created_by,
                "executed_at": None,
                "error_message": None
            }
            self.tasks.append(task)
            self.task_id_counter += 1
            return task
        
        def delete_cron_task(self, name):
            initial_count = len(self.tasks)
            self.tasks = [task for task in self.tasks if task["name"] != name]
            return len(self.tasks) < initial_count
        
        def list_cron_tasks(self, filter_status=None):
            if filter_status:
                return [task for task in self.tasks if task["status"] == filter_status]
            return self.tasks.copy()
    
    # 设置全局CronManager
    mock_cm = MockCronManager()
    set_global_cron_manager(mock_cm)
    
    # 模拟LLM的工具调用请求
    tool_calls = [
        {
            "id": "call_001",
            "type": "function",
            "function": {
                "name": "cron_manage",
                "arguments": json.dumps({
                    "action": "create",
                    "name": "测试任务",
                    "target_user": "test_user",
                    "message": "这是一条测试消息",
                    "target_time": "2024-03-12 18:00:00"
                })
            }
        },
        {
            "id": "call_002",
            "type": "function",
            "function": {
                "name": "cron_manage",
                "arguments": json.dumps({
                    "action": "list"
                })
            }
        },
        {
            "id": "call_003",
            "type": "function",
            "function": {
                "name": "cron_manage",
                "arguments": json.dumps({
                    "action": "delete",
                    "name": "测试任务"
                })
            }
        },
        {
            "id": "call_004",
            "type": "function",
            "function": {
                "name": "cron_manage",
                "arguments": json.dumps({
                    "action": "create",
                    "name": "不完整任务"
                    # 缺少其他必要参数
                })
            }
        }
    ]
    
    # 执行每个工具调用
    for i, tool_call in enumerate(tool_calls, 1):
        print(f"演示 {i}:")
        print(f"  工具调用: {tool_call['function']['name']}({tool_call['function']['arguments']})")
        result = execute_tool_call(tool_call)
        print(f"  执行结果:\n{result}")
        print("-" * 50)
    
    print("\n=== 工具定义（供LLM使用）===")
    print(json.dumps(TOOL_DEFINITION, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    # 运行演示
    demo_llm_interaction()