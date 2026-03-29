#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cron_manage_tool.py
供LLM使用的cron任务管理工具
支持创建、删除、列出cron任务
适配 CronManagerV2
"""

import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# 全局CronManager实例（将在main.py中设置）
_global_cron_manager = None


def set_tool_cron_manager(cron_manager):
    """设置全局CronManager实例"""
    global _global_cron_manager
    _global_cron_manager = cron_manager


def get_global_cron_manager():
    """获取全局CronManager实例"""
    return _global_cron_manager


def cron_manage_tool_execute(function_name:str, arguments:dict) -> str:
    try:
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
            return _handle_create(cron_manager, arguments)
        elif action == "delete":
            return _handle_delete(cron_manager, arguments)
        elif action == "list":
            return _handle_list(cron_manager, arguments)
        else:
            return f"错误：不支持的操作 '{action}'，支持的操作有：create、delete、list"
    
    except json.JSONDecodeError:
        return "错误：无法解析工具参数（无效的JSON格式）"
    except KeyError as e:
        return f"错误：工具调用格式不正确 - 缺少字段: {str(e)}"
    except Exception as e:
        logger.error(f"cron_manage_tool执行出错: {e}")
        return f"❌ 系统错误：{str(e)}"


def _handle_create(cron_manager, arguments: Dict[str, Any]) -> str:
    """处理创建cron任务"""
    name = arguments.get("name")
    target_user = arguments.get("target_user")
    message = arguments.get("message")
    target_time = arguments.get("target_time")
    repeat = arguments.get("repeat", "never")
    
    if not all([name, target_user, message, target_time]):
        return "错误：创建cron任务需要提供name、target_user、message、target_time参数"
    
    # 验证 repeat 参数
    if repeat not in ["daily", "never"]:
        return f"错误：repeat参数必须是 'daily' 或 'never'，收到: '{repeat}'"
    
    # 获取当前用户作为创建者
    created_by = arguments.get("created_by", "system")
    
    # 调用 CronManagerV2 的 add_cron 方法
    result = cron_manager.add_cron(
        name=name,
        target_user=target_user,
        message=message,
        target_time=target_time,
        repeat=repeat,
        created_by=created_by
    )
    
    # add_cron 返回字符串结果
    if "success" in result.lower():
        return f"✅ {result}\n" \
               f"   名称: {name}\n" \
               f"   目标用户: {target_user}\n" \
               f"   执行时间: {target_time}\n" \
               f"   重复: {repeat}"
    else:
        return f"❌ {result}"


def _handle_delete(cron_manager, arguments: Dict[str, Any]) -> str:
    """处理删除cron任务"""
    name = arguments.get("name")
    task_id = arguments.get("id")
    
    if not name and not task_id:
        return "错误：删除cron任务需要提供name或id参数（至少一个）"
    
    # 调用 CronManagerV2 的 delete_cron 方法
    success = cron_manager.delete_cron(name=name, id=task_id)
    
    if success:
        identifier = name if name else task_id
        return f"✅ 成功删除cron任务：{identifier}"
    else:
        identifier = f"name='{name}'" if name else f"id='{task_id}'"
        if name and task_id:
            identifier = f"name='{name}', id='{task_id}'"
        return f"⚠️ 未找到cron任务：{identifier}"


def _handle_list(cron_manager, arguments: Dict[str, Any]) -> str:
    """处理列出cron任务"""
    filter_status = arguments.get("filter_status")
    filter_user = arguments.get("filter_user")
    
    # 调用 CronManagerV2 的 find_crons 方法
    tasks = cron_manager.find_crons(
        status_filter=filter_status,
        user_filter=filter_user
    )
    
    if not tasks:
        filters = []
        if filter_status:
            filters.append(f"状态='{filter_status}'")
        if filter_user:
            filters.append(f"用户='{filter_user}'")
        
        if filters:
            return f"📋 没有符合条件的cron任务（{', '.join(filters)}）"
        else:
            return "📋 当前没有cron任务"
    
    result = f"📋 共找到 {len(tasks)} 个cron任务：\n\n"
    for i, task in enumerate(tasks, 1):
        result += f"{i}. {task['name']} (ID: {task['id']})\n"
        result += f"   目标用户: {task['target_user']}\n"
        result += f"   执行时间: {task.get('target_time', 'N/A')}\n"
        result += f"   状态: {task['status']}\n"
        result += f"   重复: {task.get('repeat', 'never')}\n"
        result += f"   创建时间: {task['created_at']}\n"
        result += f"   创建者: {task.get('created_by', 'system')}\n"
        if task.get('last_executed_at'):
            result += f"   上次执行: {task['last_executed_at']}\n"
        if task.get('error_message'):
            result += f"   错误信息: {task['error_message']}\n"
        result += "\n"
    
    return result


# 工具定义（符合OpenAI工具调用规范）
TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "cron_manage",
        "description": (
            "管理定时任务（cron任务）。支持创建、删除、列出cron任务。\n"
            "创建任务示例：{\"action\": \"create\", \"name\": \"Remind ivybridge to eat\", \"target_user\": \"ivybridge\", "
            "\"message\": \"Frederica, seeing this message means a cron to remind ivybridge to eat has been triggered.\", "
            "\"target_time\": \"2024-03-12 18:00:00\", \"repeat\": \"daily\"}\n"
            "删除任务示例：{\"action\": \"delete\", \"name\": \"Remind ivybridge to eat\"} 或 {\"action\": \"delete\", \"id\": \"abc123def456\"}\n"
            "列出任务示例：{\"action\": \"list\"} 或 {\"action\": \"list\", \"filter_status\": \"pending\", \"filter_user\": \"ivybridge\"}"
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
                    "description": "任务名称（create时必填，delete时可选）"
                },
                "id": {
                    "type": "string",
                    "description": "任务ID（delete时可选，可通过name或id删除）"
                },
                "target_user": {
                    "type": "string",
                    "description": "目标用户ID（create时必填）"
                },
                "message": {
                    "type": "string",
                    "description": "定时任务触发时发送给Frederica的提醒信息（create时必填）"
                },
                "target_time": {
                    "type": "string",
                    "description": "执行时间，格式：YYYY-MM-DD HH:MM:SS（create时必填）"
                },
                "repeat": {
                    "type": "string",
                    "enum": ["daily", "never"],
                    "description": "重复模式：daily每天重复、never只执行一次（create时可选，默认never）"
                },
                "filter_status": {
                    "type": "string",
                    "enum": ["pending", "executing", "executed_disabled", "disabled", "failed"],
                    "description": "按状态过滤（list时可选）"
                },
                "filter_user": {
                    "type": "string",
                    "description": "按目标用户过滤（list时可选）"
                }
            },
            "required": ["action"]
        }
    }
}


def execute_tool_call(name:str, arguments_dict:dict) -> str:
    return cron_manage_tool_execute(name, arguments_dict)


if __name__ == "__main__":
    # 简单测试
    print("=== cron_manage_tool 测试 ===")
    print("工具定义:")
    print(json.dumps(TOOL_DEFINITION, indent=2, ensure_ascii=False))
