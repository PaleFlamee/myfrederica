#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
send_file_tool.py
供LLM使用的企业微信文件发送工具
通过企业微信向指定用户发送文件
"""

import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# 从环境变量获取根目录，默认为"home"
ROOT_DIR = os.getenv("HOME_DIRECTORY", "home")
BASE_PATH = os.path.join(os.getcwd(), ROOT_DIR)


def send_file_to_user(user_id: str, file_path: str, media_type: str = None) -> str:
    """
    通过企业微信向指定用户发送文件

    Args:
        user_id: 接收用户的企业微信ID
        file_path: 文件路径（相对路径相对于根目录，支持..访问上级目录）
        media_type: 文件类型（image/voice/video/file），如果为None则自动检测

    Returns:
        str: 成功时返回成功信息，失败时返回错误信息
    """
    try:
        # 如果是相对路径，则相对于根目录解析
        if not os.path.isabs(file_path):
            abs_path = os.path.normpath(os.path.join(BASE_PATH, file_path))
        else:
            abs_path = file_path

        if not os.path.exists(abs_path):
            return f"错误：文件不存在 '{file_path}'（完整路径：{abs_path}）"

        from source.WeChatClient import get_wechat_client
        wechat_client = get_wechat_client()

        success = wechat_client.send_file(user_id, abs_path, media_type)

        if success:
            file_name = os.path.basename(abs_path)
            return f"成功：已向用户 '{user_id}' 发送文件 '{file_name}'"
        else:
            return f"错误：向用户 '{user_id}' 发送文件失败，请检查日志获取详细信息"

    except Exception as e:
        logger.error(f"send_file_tool执行出错: {e}")
        return f"错误：发送文件时发生异常 - {str(e)}"


# 工具定义（符合OpenAI工具调用规范）
TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "send_file",
        "description": (
            "通过企业微信向指定用户发送文件。支持相对路径（相对于根目录，根目录由环境变量HOME_DIRECTORY指定，默认为'home'），"
            "支持使用..访问上级目录。文件类型会自动检测，也可手动指定。\n"
            "支持的文件类型：图片(jpg/jpeg/png/bmp/gif，最大10MB)、语音(amr，最大2MB)、"
            "视频(mp4/avi/mov/wmv/flv，最大10MB)、普通文件(其他格式，最大20MB)。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "接收文件的用户企业微信ID（即系统消息中的user_id）"
                },
                "file_path": {
                    "type": "string",
                    "description": "要发送的文件路径（相对路径相对于根目录，支持..访问上级目录）"
                },
                "media_type": {
                    "type": "string",
                    "enum": ["image", "voice", "video", "file"],
                    "description": "文件类型，不指定则根据扩展名自动检测"
                }
            },
            "required": ["user_id", "file_path"]
        }
    }
}


def execute_tool_call(name: str, arguments: dict) -> str:
    try:
        user_id = arguments.get("user_id")
        file_path = arguments.get("file_path")
        media_type = arguments.get("media_type")

        if not user_id:
            return "错误：缺少必要参数 'user_id'"
        if not file_path:
            return "错误：缺少必要参数 'file_path'"

        return send_file_to_user(user_id, file_path, media_type)

    except Exception as e:
        return f"错误：执行工具时发生异常 - {str(e)}"
