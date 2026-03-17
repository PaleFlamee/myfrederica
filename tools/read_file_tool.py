#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
read_file_tool.py
供LLM使用的文件读取工具
支持通过tool_call调用，读取指定文件的内容
"""

import os
import json
from typing import Dict, Any

# 从环境变量获取根目录，默认为"home"
ROOT_DIR = os.getenv("HOME_DIRECTORY", "home")
BASE_PATH = os.path.join(os.getcwd(), ROOT_DIR)

def read_file(path: str) -> str:
    """
    读取指定文件的内容
    
    Args:
        path: 相对路径（相对于根目录，支持..访问上级目录）
    
    Returns:
        str: 成功时返回文件内容，失败时返回错误信息
    """
    try:
        # 构建基于根目录的绝对路径（支持..访问上级目录）
        abs_path = os.path.normpath(os.path.join(BASE_PATH, path))
        
        # 检查路径是否存在
        if not os.path.exists(abs_path):
            return f"错误：文件 '{path}' 不存在"
        
        # 检查是否为文件
        if not os.path.isfile(abs_path):
            return f"错误：'{path}' 不是文件"
        
        # 检查文件大小（防止读取过大文件）
        file_size = os.path.getsize(abs_path)
        if file_size > 10 * 1024 * 1024:  # 10MB限制
            return f"错误：文件 '{path}' 过大（{file_size}字节），超过10MB限制"
        
        # 读取文件内容
        with open(abs_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 返回文件内容
        return content
        
    except PermissionError:
        return f"错误：没有权限读取文件 '{path}'"
    except UnicodeDecodeError:
        # 尝试其他编码
        try:
            with open(abs_path, 'r', encoding='gbk') as f:
                content = f.read()
            return content
        except:
            return f"错误：无法解码文件 '{path}' 的内容（尝试了UTF-8和GBK编码）"
    except Exception as e:
        return f"错误：读取文件时发生异常 - {str(e)}"

# 工具定义（符合OpenAI工具调用规范）
TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "读取指定文件的内容并返回全文。支持相对路径（相对于根目录，根目录由环境变量HOME_DIRECTORY指定，默认为'home'），支持使用..访问上级目录。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要读取的文件路径（相对路径，相对于根目录，支持..访问上级目录）"
                }
            },
            "required": ["path"]
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
                    "name": "read_file",
                    "arguments": "{\"path\": \"example.md\"}"
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
        if function_name != "read_file":
            return f"错误：未知的工具 '{function_name}'"
        
        # 提取参数
        path = arguments.get("path")
        
        # 验证必要参数
        if not path:
            return "错误：缺少必要参数 'path'"
        
        # 执行工具
        return read_file(path)
        
    except json.JSONDecodeError:
        return "错误：无法解析工具参数（无效的JSON格式）"
    except KeyError as e:
        return f"错误：工具调用格式不正确 - 缺少字段: {str(e)}"
    except Exception as e:
        return f"错误：执行工具时发生异常 - {str(e)}"
