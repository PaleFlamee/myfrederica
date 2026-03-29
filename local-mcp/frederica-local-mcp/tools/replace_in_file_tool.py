#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
replace_in_file_tool.py
供LLM使用的文件内容替换工具
支持通过tool_call调用，在指定文件中搜索并替换文本内容
"""

import os
from typing import Dict, Any

# 从环境变量获取根目录，默认为"home"
ROOT_DIR = os.getenv("HOME_DIRECTORY", "home")
BASE_PATH = os.path.join(os.getcwd(), ROOT_DIR)

def replace_in_file(path: str, search_text: str, replace_text: str, replace_all: bool = False) -> str:
    """
    在指定文件中搜索并替换文本内容

    Args:
        path: 文件路径（相对路径，相对于根目录，支持..访问上级目录）
        search_text: 要搜索的文本内容（精确匹配，区分大小写）
        replace_text: 要替换成的文本内容
        replace_all: 是否替换所有匹配项，默认为False（只替换第一个）

    Returns:
        str: 成功时返回替换统计信息，失败时返回错误信息
    """
    try:
        # 验证搜索文本（不 strip，保留原始内容以支持精确匹配）
        if not search_text:
            return "错误：搜索文本不能为空"

        # 构建基于根目录的绝对路径（支持..访问上级目录）
        abs_path = os.path.normpath(os.path.join(BASE_PATH, path))

        # 检查文件是否存在
        if not os.path.exists(abs_path):
            return f"错误：文件 '{path}' 不存在"

        # 检查是否为文件
        if not os.path.isfile(abs_path):
            return f"错误：'{path}' 不是文件"

        # 检查文件大小（10MB限制）
        file_size = os.path.getsize(abs_path)
        if file_size > 10 * 1024 * 1024:
            return f"错误：文件 '{path}' 过大（{file_size}字节），超过10MB限制"

        # 读取文件内容，同时记录编码供写入使用
        content = None
        encoding_used = 'utf-8'
        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                encoding_used = 'gbk'
                with open(abs_path, 'r', encoding='gbk') as f:
                    content = f.read()
            except Exception:
                return f"错误：无法解码文件 '{path}' 的内容（不支持的文件编码）"
        except Exception as e:
            return f"错误：读取文件 '{path}' 失败 - {str(e)}"

        # 统计原始匹配次数
        original_count = content.count(search_text)

        if original_count == 0:
            return f"信息：在文件 '{path}' 中未找到搜索文本"

        # 执行替换
        if replace_all:
            new_content = content.replace(search_text, replace_text)
            replaced_count = original_count
        else:
            new_content = content.replace(search_text, replace_text, 1)
            replaced_count = 1

        # 检查替换后内容是否有变化
        if content == new_content:
            return f"信息：文件 '{path}' 内容未发生变化（搜索文本与替换文本相同）"

        # 写入文件（使用第一次读取时确定的编码）
        try:
            with open(abs_path, 'w', encoding=encoding_used) as f:
                f.write(new_content)
        except PermissionError:
            return f"错误：没有权限写入文件 '{path}'"
        except Exception as e:
            return f"错误：写入文件 '{path}' 时发生异常 - {str(e)}"

        # 写入后重新获取文件大小
        new_file_size = os.path.getsize(abs_path)
        mode_desc = "全部替换" if replace_all else "替换第一个匹配项"
        result = [
            f"成功：在文件 '{path}' 中替换了 {replaced_count} 处匹配",
            f"替换模式：{mode_desc}",
            f"文件大小：{new_file_size}字节",
        ]
        if not replace_all and original_count > 1:
            result.append(f"提示：文件中还有 {original_count - 1} 处匹配未替换")

        return "\n".join(result)

    except PermissionError:
        return f"错误：没有权限访问文件 '{path}'"
    except Exception as e:
        return f"错误：替换文件内容时发生异常 - {str(e)}"


# 工具定义（符合OpenAI工具调用规范）
TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "replace_in_file",
        "description": "在指定文件中搜索并替换文本内容。支持相对路径（相对于根目录，根目录由环境变量HOME_DIRECTORY指定，默认为'home'），支持使用..访问上级目录。精确匹配，区分大小写，保留原始空白字符。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要操作的文件路径（相对路径，相对于根目录，支持..访问上级目录）"
                },
                "search_text": {
                    "type": "string",
                    "description": "要搜索的文本内容（精确匹配，区分大小写，空白字符和缩进均参与匹配）"
                },
                "replace_text": {
                    "type": "string",
                    "description": "要替换成的文本内容"
                },
                "replace_all": {
                    "type": "boolean",
                    "description": "是否替换所有匹配项。默认为false（只替换第一个匹配项）"
                }
            },
            "required": ["path", "search_text", "replace_text"]
        }
    }
}


def execute_tool_call(arguments: dict) -> str:
    try:
        path = arguments.get("path")
        search_text = arguments.get("search_text")
        replace_text = arguments.get("replace_text")
        replace_all = arguments.get("replace_all", False)

        if not path:
            return "错误：缺少必要参数 'path'"
        if not search_text:
            return "错误：缺少必要参数 'search_text'"
        if replace_text is None:
            return "错误：缺少必要参数 'replace_text'"

        if not isinstance(replace_all, bool):
            return f"错误：参数 'replace_all' 必须是布尔值，收到 '{type(replace_all).__name__}'"

        return replace_in_file(path, search_text, replace_text, replace_all)

    except KeyError as e:
        return f"错误：工具调用格式不正确 - 缺少字段: {str(e)}"
    except Exception as e:
        return f"错误：执行工具时发生异常 - {str(e)}"
