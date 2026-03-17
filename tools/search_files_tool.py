#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
search_files_tool.py
供LLM使用的文件搜索工具
支持三种搜索方式：单文件搜索、文件夹搜索、文件夹递归搜索
支持所有文本文件类型，不再限制.md文件
"""

import os
import json
import fnmatch
from typing import Dict, Any, List, Tuple, Optional

# 从环境变量获取根目录，默认为"home"
ROOT_DIR = os.getenv("HOME_DIRECTORY", "home")
BASE_PATH = os.path.join(os.getcwd(), ROOT_DIR)

def get_files_to_search(path: str, recursive: bool = False, file_pattern: Optional[str] = None) -> List[Tuple[str, str]]:
    """
    获取要搜索的文件列表
    
    Args:
        path: 搜索路径（文件或目录）
        recursive: 是否递归搜索子目录（仅当path为目录时有效）
        file_pattern: 文件名匹配模式（如 *.py, *.txt）
        
    Returns:
        List[Tuple[str, str]]: 文件列表，每个元素为(相对路径, 绝对路径)
    """
    # 构建基于根目录的绝对路径（支持..访问上级目录）
    abs_path = os.path.normpath(os.path.join(BASE_PATH, path))
    
    # 如果是文件，直接返回该文件
    if os.path.isfile(abs_path):
        rel_path = os.path.relpath(abs_path, BASE_PATH)
        return [(rel_path, abs_path)]
    
    # 如果是目录，收集目录下的文件
    files_to_search = []
    
    if recursive:
        # 递归搜索
        for root, dirs, files in os.walk(abs_path):
            for file in files:
                if file_pattern and not fnmatch.fnmatch(file, file_pattern):
                    continue
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, BASE_PATH)
                files_to_search.append((rel_path, file_path))
    else:
        # 非递归搜索
        for item in os.listdir(abs_path):
            item_path = os.path.join(abs_path, item)
            if os.path.isfile(item_path):
                if file_pattern and not fnmatch.fnmatch(item, file_pattern):
                    continue
                rel_path = os.path.relpath(item_path, BASE_PATH)
                files_to_search.append((rel_path, item_path))
    
    return files_to_search

def search_files(path: str, keyword: str, recursive: bool = False, 
                 context_lines_before: int = 3, context_lines_after: int = 3, 
                 max_context_chars: int = 200, file_pattern: Optional[str] = None) -> str:
    """
    在指定路径中搜索关键词，支持三种搜索方式：
    1. 单文件搜索：path指向一个具体文件
    2. 文件夹搜索：path指向目录，recursive=False
    3. 文件夹递归搜索：path指向目录，recursive=True
    
    Args:
        path: 搜索路径（可以是文件或目录，支持..访问上级目录）
        keyword: 要搜索的关键词
        recursive: 是否递归搜索子目录（仅当path为目录时有效）
        context_lines_before: 关键词前的上下文行数，默认为3
        context_lines_after: 关键词后的上下文行数，默认为3
        max_context_chars: 每个匹配项返回的最大字符数，默认为200
        file_pattern: 文件名匹配模式（如 *.py, *.txt），默认搜索所有文件
    
    Returns:
        str: 成功时返回搜索结果，失败时返回错误信息
    """
    try:
        # 构建基于根目录的绝对路径（支持..访问上级目录）
        abs_path = os.path.normpath(os.path.join(BASE_PATH, path))
        
        # 检查路径是否存在
        if not os.path.exists(abs_path):
            return f"错误：路径 '{path}' 不存在"
        
        # 验证参数
        if not keyword or not keyword.strip():
            return "错误：关键词不能为空"
        
        keyword = keyword.strip()
        
        if context_lines_before < 0:
            return f"错误：关键词前的上下文行数不能为负数，收到 {context_lines_before}"
        
        if context_lines_after < 0:
            return f"错误：关键词后的上下文行数不能为负数，收到 {context_lines_after}"
        
        if max_context_chars < 100:
            return f"错误：最大字符数至少为100，收到 {max_context_chars}"
        
        # 获取要搜索的文件列表
        files_to_search = get_files_to_search(path, recursive, file_pattern)
        
        if not files_to_search:
            # 检查是否是目录但没有文件
            if os.path.isdir(abs_path):
                pattern_info = f"（匹配模式: {file_pattern}）" if file_pattern else ""
                return f"信息：在路径 '{path}' 中未找到文件{pattern_info}"
            else:
                return f"信息：路径 '{path}' 不是有效的文件或目录"
        
        # 对文件进行排序（按相对路径）
        files_to_search.sort(key=lambda x: x[0])
        
        # 搜索关键词
        all_results = []
        total_matches = 0
        
        for rel_path, file_path in files_to_search:
            try:
                # 检查文件大小
                file_size = os.path.getsize(file_path)
                if file_size > 10 * 1024 * 1024:  # 10MB限制
                    all_results.append(f"文件: {rel_path} (大小: {file_size}字节，超过10MB限制，跳过)")
                    continue
                
                # 读取文件内容
                content = None
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except UnicodeDecodeError:
                    # 尝试GBK编码
                    try:
                        with open(file_path, 'r', encoding='gbk') as f:
                            content = f.read()
                    except:
                        all_results.append(f"文件: {rel_path} (错误：无法解码文件内容)")
                        continue
                except Exception as e:
                    all_results.append(f"文件: {rel_path} (错误：读取文件失败 - {str(e)})")
                    continue
                
                # 分割行并搜索关键词
                lines = content.splitlines()
                file_matches = []
                
                for line_num, line in enumerate(lines, 1):
                    if keyword in line:
                        # 计算上下文行范围
                        start_line = max(1, line_num - context_lines_before)
                        end_line = min(len(lines), line_num + context_lines_after)
                        
                        # 收集上下文行
                        context = []
                        for ctx_line_num in range(start_line, end_line + 1):
                            ctx_line = lines[ctx_line_num - 1]
                            prefix = "-> " if ctx_line_num == line_num else "   "
                            context.append(f"{prefix}{ctx_line_num}: {ctx_line}")
                        
                        # 合并上下文
                        context_text = "\n".join(context)
                        
                        # 检查字符数限制
                        if len(context_text) > max_context_chars:
                            # 截断并添加指示
                            context_text = context_text[:max_context_chars] + "...\n[上下文被截断，超过字符限制]"
                        
                        file_matches.append({
                            'line_num': line_num,
                            'context': context_text,
                            'context_chars': len(context_text)
                        })
                
                if file_matches:
                    total_matches += len(file_matches)
                    file_result = [f"文件: {rel_path} (大小: {file_size}字节)"]
                    
                    for i, match in enumerate(file_matches, 1):
                        file_result.append(f"匹配 {i}/{len(file_matches)}:")
                        file_result.append(f"  行号: {match['line_num']}")
                        file_result.append(f"  上下文 (字符数: {match['context_chars']}/{max_context_chars}):")
                        file_result.append(f"    " + match['context'].replace("\n", "\n    "))
                        file_result.append("")  # 空行分隔
                    
                    all_results.append("\n".join(file_result).strip())
                    
            except PermissionError:
                all_results.append(f"文件: {rel_path} (错误：没有权限读取文件)")
            except Exception as e:
                all_results.append(f"文件: {rel_path} (错误：处理文件时发生异常 - {str(e)})")
        
        # 构建最终结果
        if total_matches == 0:
            # 确定搜索模式描述
            if os.path.isfile(abs_path):
                search_mode = "单文件搜索"
            elif recursive:
                search_mode = "文件夹递归搜索"
            else:
                search_mode = "文件夹搜索"
            
            pattern_info = f"（匹配模式: {file_pattern}）" if file_pattern else ""
            return f"信息：在 {len(files_to_search)} 个文件中未找到关键词 '{keyword}'{pattern_info}\n搜索模式: {search_mode}"
        
        # 确定搜索模式描述
        if os.path.isfile(abs_path):
            search_mode = "单文件搜索"
        elif recursive:
            search_mode = "文件夹递归搜索"
        else:
            search_mode = "文件夹搜索"
        
        result_lines = [
            f"搜索完成：在 {len(files_to_search)} 个文件中找到 {total_matches} 处匹配",
            f"关键词: '{keyword}'",
            f"搜索路径: '{path}' (模式: {search_mode})",
            f"文件匹配模式: {file_pattern if file_pattern else '所有文件'}",
            f"上下文设置: 前{context_lines_before}行/后{context_lines_after}行，最大字符数: {max_context_chars}",
            "=" * 60,
            ""
        ]
        
        result_lines.extend(all_results)
        
        return "\n".join(result_lines)
            
    except PermissionError:
        return f"错误：没有权限访问路径 '{path}'"
    except Exception as e:
        return f"错误：搜索文件时发生异常 - {str(e)}"

# 工具定义（符合OpenAI工具调用规范）
TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "search_files",
        "description": "在指定路径中搜索特定关键词，返回关键词所在的文件和上下文。支持三种搜索方式：单文件搜索、文件夹搜索、文件夹递归搜索。支持所有文本文件类型，可通过file_pattern参数过滤文件类型。支持相对路径（相对于根目录，根目录由环境变量HOME_DIRECTORY指定，默认为'home'），支持使用..访问上级目录。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要搜索的路径（可以是文件或目录，支持..访问上级目录）"
                },
                "keyword": {
                    "type": "string",
                    "description": "要搜索的关键词"
                },
                "recursive": {
                    "type": "boolean",
                    "description": "搜索目录时是否递归搜索子目录（仅当path为目录时有效）。默认为false"
                },
                "context_lines_before": {
                    "type": "integer",
                    "description": "关键词前的上下文行数。默认为3，最小为0",
                    "minimum": 0
                },
                "context_lines_after": {
                    "type": "integer",
                    "description": "关键词后的上下文行数。默认为3，最小为0",
                    "minimum": 0
                },
                "max_context_chars": {
                    "type": "integer",
                    "description": "每个匹配项返回的最大字符数。默认为200，最小为100",
                    "minimum": 100
                },
                "file_pattern": {
                    "type": "string",
                    "description": "文件名匹配模式（如 *.py, *.txt, *.md），默认搜索所有文件"
                }
            },
            "required": ["path", "keyword"]
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
                    "name": "search_files",
                    "arguments": "{\"path\": \".\", \"keyword\": \"test\"}"
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
        if function_name != "search_files":
            return f"错误：未知的工具 '{function_name}'"
        
        # 提取参数
        path = arguments.get("path")
        keyword = arguments.get("keyword")
        recursive = arguments.get("recursive", False)
        context_lines_before = arguments.get("context_lines_before", 3)
        context_lines_after = arguments.get("context_lines_after", 3)
        max_context_chars = arguments.get("max_context_chars", 200)
        file_pattern = arguments.get("file_pattern")
        
        # 验证必要参数
        if not path:
            return "错误：缺少必要参数 'path'"
        if not keyword:
            return "错误：缺少必要参数 'keyword'"
        
        # 执行工具
        return search_files(path, keyword, recursive, context_lines_before, 
                           context_lines_after, max_context_chars, file_pattern)
        
    except json.JSONDecodeError:
        return "错误：无法解析工具参数（无效的JSON格式）"
    except KeyError as e:
        return f"错误：工具调用格式不正确 - 缺少字段: {str(e)}"
    except Exception as e:
        return f"错误：执行工具时发生异常 - {str(e)}"
