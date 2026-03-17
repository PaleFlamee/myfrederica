#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
delete_file_or_folder_tool.py
供LLM使用的文件/文件夹删除工具
支持通过tool_call调用，删除指定的文件或文件夹
"""

import os
import json
import shutil
from typing import Dict, Any

# 从环境变量获取根目录，默认为"home"
ROOT_DIR = os.getenv("HOME_DIRECTORY", "home")
BASE_PATH = os.path.join(os.getcwd(), ROOT_DIR)

def delete_file_or_folder(path: str, force: bool = False) -> str:
    """
    删除指定的文件或文件夹
    
    Args:
        path: 要删除的文件或文件夹路径（相对路径，相对于根目录，支持..访问上级目录）
        force: 是否强制删除非空文件夹，默认为False
        
    Returns:
        str: 成功时返回成功信息，失败时返回错误信息
    """
    try:
        # 构建基于根目录的绝对路径（支持..访问上级目录）
        abs_path = os.path.normpath(os.path.join(BASE_PATH, path))
        
        # 检查路径是否存在
        if not os.path.exists(abs_path):
            return f"错误：路径 '{path}' 不存在"
        
        # 检查是否为根目录（防止误删整个根目录）
        if os.path.normpath(abs_path) == os.path.normpath(BASE_PATH):
            return "错误：不能删除根目录"
        
        # 判断是文件还是文件夹
        is_file = os.path.isfile(abs_path)
        is_dir = os.path.isdir(abs_path)
        
        if is_file:
            # 删除文件
            file_size = os.path.getsize(abs_path)
            os.remove(abs_path)
            
            # 验证文件是否删除成功
            if not os.path.exists(abs_path):
                return f"成功：已删除文件 '{path}'（原大小：{file_size}字节）"
            else:
                return f"错误：文件删除失败"
                
        elif is_dir:
            # 检查文件夹是否为空
            is_empty = len(os.listdir(abs_path)) == 0
            
            if is_empty:
                # 删除空文件夹
                os.rmdir(abs_path)
                
                # 验证文件夹是否删除成功
                if not os.path.exists(abs_path):
                    return f"成功：已删除空文件夹 '{path}'"
                else:
                    return f"错误：空文件夹删除失败"
            else:
                # 非空文件夹，需要force参数
                if not force:
                    item_count = len(os.listdir(abs_path))
                    return f"错误：文件夹 '{path}' 非空（包含 {item_count} 个项目），如需删除请设置 force=true"
                
                # 使用shutil.rmtree递归删除非空文件夹
                shutil.rmtree(abs_path)
                
                # 验证文件夹是否删除成功
                if not os.path.exists(abs_path):
                    return f"成功：已强制删除非空文件夹 '{path}'"
                else:
                    return f"错误：非空文件夹删除失败"
        else:
            # 既不是文件也不是文件夹（可能是符号链接等）
            return f"错误：'{path}' 不是常规文件或文件夹"
            
    except PermissionError:
        return f"错误：没有权限删除路径 '{path}'"
    except shutil.Error as e:
        return f"错误：删除文件夹时发生异常 - {str(e)}"
    except Exception as e:
        return f"错误：删除操作时发生异常 - {str(e)}"

# 工具定义（符合OpenAI工具调用规范）
TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "delete_file_or_folder",
        "description": "删除指定的文件或文件夹。支持相对路径（相对于根目录，根目录由环境变量HOME_DIRECTORY指定，默认为'home'），支持使用..访问上级目录。注意：删除非空文件夹需要设置force=true参数。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要删除的文件或文件夹路径（相对路径，相对于根目录，支持..访问上级目录）"
                },
                "force": {
                    "type": "boolean",
                    "description": "是否强制删除非空文件夹。默认为false（仅删除空文件夹或文件）"
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
                    "name": "delete_file_or_folder",
                    "arguments": "{\"path\": \"test.txt\", \"force\": false}"
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
        if function_name != "delete_file_or_folder":
            return f"错误：未知的工具 '{function_name}'"
        
        # 提取参数
        path = arguments.get("path")
        force = arguments.get("force", False)
        
        # 验证必要参数
        if not path:
            return "错误：缺少必要参数 'path'"
        
        # 验证force参数类型
        if not isinstance(force, bool):
            return f"错误：参数 'force' 必须是布尔值，收到 '{force}'"
        
        # 执行工具
        return delete_file_or_folder(path, force)
        
    except json.JSONDecodeError:
        return "错误：无法解析工具参数（无效的JSON格式）"
    except KeyError as e:
        return f"错误：工具调用格式不正确 - 缺少字段: {str(e)}"
    except Exception as e:
        return f"错误：执行工具时发生异常 - {str(e)}"
