#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
create_file_or_folder_tool.py
供LLM使用的文件/文件夹创建工具
支持通过tool_call调用，创建空文件或空文件夹
"""

import os
import json
import re
from typing import Dict, Any

# 从环境变量获取根目录，默认为"home"
ROOT_DIR = os.getenv("HOME_DIRECTORY", "home")
BASE_PATH = os.path.join(os.getcwd(), ROOT_DIR)

def validate_name(name: str) -> tuple[bool, str]:
    """
    验证文件/文件夹名称的合法性
    
    Args:
        name: 要验证的名称
    
    Returns:
        tuple[bool, str]: (是否有效, 错误信息)
    """
    # 检查是否为空
    if not name or not name.strip():
        return False, "名称不能为空"
    
    # 去除首尾空格
    name = name.strip()
    
    # 检查长度
    if len(name) > 255:
        return False, "名称长度不能超过255个字符"
    
    # 检查非法字符（Windows文件系统限制）
    illegal_chars = r'[<>:"/\\|?*]'
    if re.search(illegal_chars, name):
        return False, f"名称包含非法字符：<>:\"/\\|?*"
    
    # 检查保留名称（Windows）
    reserved_names = [
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    ]
    if name.upper() in reserved_names:
        return False, f"'{name}' 是系统保留名称"
    
    # 允许以点开头或结尾（支持隐藏文件等）
    # 检查连续空格
    if '  ' in name:
        return False, "名称不能包含连续空格"
    
    return True, name

def create_file_or_folder(name: str, type: str = "file", path: str = ".") -> str:
    """
    创建空文件或空文件夹
    
    Args:
        name: 文件或文件夹名称
        type: 创建类型，'file'（文件）或 'folder'（文件夹）
        path: 创建路径（相对路径，相对于根目录，支持..访问上级目录）
    
    Returns:
        str: 成功时返回成功信息，失败时返回错误信息
    """
    try:
        # 验证名称
        is_valid, validation_result = validate_name(name)
        if not is_valid:
            return f"错误：{validation_result}"
        
        # 构建目标路径（支持相对路径和 .. 访问上级目录）
        if path == ".":
            target_dir = BASE_PATH
        else:
            target_dir = os.path.normpath(os.path.join(BASE_PATH, path))
        
        # 确保目标目录存在（递归创建）
        os.makedirs(target_dir, exist_ok=True)
        
        # 构建完整路径
        full_path = os.path.join(target_dir, name)
        
        # 检查是否已存在
        if os.path.exists(full_path):
            existing_type = "文件" if os.path.isfile(full_path) else "文件夹"
            return f"错误：'{name}' 已存在（{existing_type}）"
        
        # 根据类型创建
        if type == "file":
            # 创建空文件
            with open(full_path, 'w', encoding='utf-8') as f:
                pass  # 创建空文件
            
            # 验证文件是否创建成功
            if os.path.exists(full_path) and os.path.isfile(full_path):
                file_size = os.path.getsize(full_path)
                return f"成功：已创建空文件 '{name}'（大小：{file_size}字节）"
            else:
                return f"错误：文件创建失败"
                
        elif type == "folder":
            # 创建文件夹
            os.makedirs(full_path, exist_ok=True)
            
            # 验证文件夹是否创建成功
            if os.path.exists(full_path) and os.path.isdir(full_path):
                return f"成功：已创建空文件夹 '{name}'"
            else:
                return f"错误：文件夹创建失败"
        else:
            return f"错误：不支持的类型 '{type}'，请使用 'file' 或 'folder'"
            
    except PermissionError:
        return f"错误：没有权限在路径 '{path}' 创建{type}"
    except Exception as e:
        return f"错误：创建{type}时发生异常 - {str(e)}"

# 工具定义（符合OpenAI工具调用规范）
TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "create_file_or_folder",
        "description": "创建空文件或空文件夹。支持相对路径（相对于根目录，根目录由环境变量HOME_DIRECTORY指定，默认为'home'），支持使用..访问上级目录，自动创建父目录。注意：名称应该是纯文件名（不含路径），路径通过 `path` 参数指定。",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "要创建的文件或文件夹名称（纯名称，不含路径）"
                },
                "type": {
                    "type": "string",
                    "description": "创建类型：'file'（文件）或 'folder'（文件夹），默认为'file'",
                    "enum": ["file", "folder"]
                },
                "path": {
                    "type": "string",
                    "description": "可选，创建路径（相对路径，相对于根目录，支持..访问上级目录），默认为当前目录。例如：path='myfolder' 或 path='../other_folder'"
                }
            },
            "required": ["name"]
        }
    }
}

def execute_tool_call(tool_call: Dict[str, Any]) -> str:
    """
    执行工具调用
    
    Args:
        tool_call: 包含工具调用信息的字典，格式为：
            {
                "id": "call_123",
                "type": "function",
                "function": {
                    "name": "create_file_or_folder",
                    "arguments": "{\"name\": \"test.txt\", \"type\": \"file\"}"
                }
            }
    
    Returns:
        str: 工具执行结果
    """
    try:
        # 解析参数
        function_name = tool_call["function"]["name"]
        arguments_str = tool_call["function"]["arguments"]
        arguments = json.loads(arguments_str)
        
        # 验证工具名称
        if function_name != "create_file_or_folder":
            return f"错误：未知的工具 '{function_name}'"
        
        # 提取参数
        name = arguments.get("name")
        type = arguments.get("type", "file")
        path = arguments.get("path", ".")
        
        # 验证必要参数
        if not name:
            return "错误：缺少必要参数 'name'"
        
        # 验证type参数
        if type not in ["file", "folder"]:
            return f"错误：参数 'type' 必须是 'file' 或 'folder'，收到 '{type}'"
        
        # 执行工具
        return create_file_or_folder(name, type, path)
        
    except json.JSONDecodeError:
        return "错误：无法解析工具参数（无效的JSON格式）"
    except KeyError as e:
        return f"错误：工具调用格式不正确 - 缺少字段: {str(e)}"
    except Exception as e:
        return f"错误：执行工具时发生异常 - {str(e)}"
