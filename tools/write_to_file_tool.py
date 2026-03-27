#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
write_to_file_tool.py
供LLM使用的文件写入工具
支持通过tool_call调用，向指定文件写入内容
"""

import os
import json
from typing import Dict, Any

# 从环境变量获取根目录，默认为"home"
ROOT_DIR = os.getenv("HOME_DIRECTORY", "home")
BASE_PATH = os.path.join(os.getcwd(), ROOT_DIR)

def write_file(path: str, content: str, mode: str = "write") -> str:
    """
    向指定文件写入内容
    
    Args:
        path: 文件路径（相对路径，相对于根目录，支持..访问上级目录）
        content: 要写入的内容
        mode: 写入模式，'write'（覆盖）或 'append'（追加），默认为'write'
    
    Returns:
        str: 成功时返回成功信息，失败时返回错误信息
    """
    try:
        # 构建基于根目录的绝对路径（支持..访问上级目录）
        abs_path = os.path.normpath(os.path.join(BASE_PATH, path))
        
        # 检查内容大小（防止写入过大内容）
        content_size = len(content.encode('utf-8'))
        if content_size > 10 * 1024 * 1024:  # 10MB限制
            return f"错误：要写入的内容过大（{content_size}字节），超过10MB限制"
        
        # 确保父目录存在
        parent_dir = os.path.dirname(abs_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
        
        # 根据模式写入文件
        if mode == "write":
            # 覆盖模式
            with open(abs_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # 验证写入
            if os.path.exists(abs_path):
                file_size = os.path.getsize(abs_path)
                return f"成功：已写入文件 '{path}'（模式：覆盖，大小：{file_size}字节）"
            else:
                return f"错误：文件写入失败"
                
        elif mode == "append":
            # 追加模式
            file_exists = os.path.exists(abs_path)
            
            with open(abs_path, 'a', encoding='utf-8') as f:
                f.write(content)
            
            # 验证写入
            if os.path.exists(abs_path):
                file_size = os.path.getsize(abs_path)
                action = "追加到" if file_exists else "创建并写入"
                return f"成功：已{action}文件 '{path}'（模式：追加，大小：{file_size}字节）"
            else:
                return f"错误：文件追加失败"
        else:
            return f"错误：不支持的模式 '{mode}'，请使用 'write' 或 'append'"
            
    except PermissionError:
        return f"错误：没有权限写入文件 '{path}'"
    except Exception as e:
        return f"错误：写入文件时发生异常 - {str(e)}"

# 工具定义（符合OpenAI工具调用规范）
TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "向指定文件写入内容。支持相对路径（相对于根目录，根目录由环境变量HOME_DIRECTORY指定，默认为'home'），支持使用..访问上级目录，自动创建父目录。支持覆盖和追加两种模式。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要写入的文件路径（相对路径，相对于根目录，支持..访问上级目录）"
                },
                "content": {
                    "type": "string",
                    "description": "要写入文件的内容"
                },
                "mode": {
                    "type": "string",
                    "description": "写入模式：'write'（覆盖）或 'append'（追加），默认为'write'",
                    "enum": ["write", "append"]
                }
            },
            "required": ["path", "content"]
        }
    }
}

def execute_tool_call(arguments:dict) -> str:
    try:
        # 提取参数
        path = arguments.get("path")
        content = arguments.get("content")
        mode = arguments.get("mode", "write")
        
        # 验证必要参数
        if not path:
            return "错误：缺少必要参数 'path'"
        if content is None:
            return "错误：缺少必要参数 'content'"
        
        # 验证mode参数
        if mode not in ["write", "append"]:
            return f"错误：参数 'mode' 必须是 'write' 或 'append'，收到 '{mode}'"
        
        # 执行工具
        return write_file(path, content, mode)
        
    except json.JSONDecodeError:
        return "错误：无法解析工具参数（无效的JSON格式）"
    except KeyError as e:
        return f"错误：工具调用格式不正确 - 缺少字段: {str(e)}"
    except Exception as e:
        return f"错误：执行工具时发生异常 - {str(e)}"
