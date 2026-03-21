#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
from typing import Dict, Any
import os
import base64

logger = logging.getLogger(__name__)

_global_user_manager = None

ROOT_DIR = os.getenv("HOME_DIRECTORY", "home")
BASE_PATH = os.path.join(os.getcwd(), ROOT_DIR)


# from source.Users import UserManager
from source.Message import *

def set_tool_user_manager(user_manager):
    global _global_user_manager
    _global_user_manager = user_manager

def get_global_user_manager():
    return _global_user_manager

def read_file(path: str, user_id:str) -> str:
    try:
        abs_path = os.path.normpath(os.path.join(BASE_PATH, path))
        
        if not os.path.exists(abs_path):
            return f"Error: File '{path}' does not exist"
        
        if not os.path.isfile(abs_path):
            return f"Error: '{path}' not a file"
        
        file_size = os.path.getsize(abs_path)
        if file_size > 10 * 1024 * 1024:  # 10MB
            return f"Error: File '{path}' is too large({file_size}Bytes), exceeding 10MB limit"
        
        with open(abs_path, 'rb') as f:
            img_b64 = base64.b64encode(f.read()).decode()

        url = f"data:image/jpeg;base64,{img_b64}"

        user_manager = get_global_user_manager()
        user_manager.general_handle_new_message(
            user_id=user_id,
            incoming_message_queue=[
                Message(
                    role="user",
                    content=[
                        MultimodalContent(
                            type="image_url",
                            image_url=MultimodalContent.Url(url=url)
                        )
                    ]
                )
            ]
        )
        
        return "Successfully read image, image will be shown in next message"
        
    except PermissionError:
        return f"Error: No permission to access '{path}'"
    except Exception as e:
        return f"Error: Exception - {str(e)}"

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "read_image",
        "description": "读取指定的图片文件。支持相对路径（相对于根目录，根目录由环境变量HOME_DIRECTORY指定，默认为'home'），支持使用..访问上级目录。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要读取的文件路径（相对路径，相对于根目录，支持..访问上级目录）"
                },
                "user_id": {
                    "type": "string",
                    "description": "当前正在对话的用户id"
                }
            },
            "required": ["path","user_id"]
        }
    }
}

def execute_tool_call(tool_call: Dict[str, Any]) -> str:
    try:
        # 解析参数
        function_name = tool_call["function"]["name"]
        arguments_str = tool_call["function"]["arguments"]
        arguments = json.loads(arguments_str)
        
        # 验证工具名称
        if function_name != "read_image":
            return f"Error: Invalid tool '{function_name}'"
        
        # 提取参数
        path = arguments.get("path")
        user_id = arguments.get("user_id")
        
        # 验证必要参数
        if not path:
            return "Error: Excepting 'path'"
        if not user_id:
            return "Error: Excepting 'user_id'"
        
        # 执行工具
        return read_file(path, user_id)
        
    except json.JSONDecodeError:
        return "Error: Invalid JSON format"
    except KeyError as e:
        return f"Error: Incorrect tool call format, expecting {str(e)}"
    except Exception as e:
        return f"Error: Exception - {str(e)}"
