#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
search_markdown_tool.py
供LLM使用的Markdown标题搜索工具
专门搜索Markdown文件的各级别标题，按照标题层级返回搜索结果
支持三种搜索方式：单文件搜索、文件夹搜索、文件夹递归搜索
"""

import os
import json
import re
import fnmatch
from typing import Dict, Any, List, Tuple, Optional

# 从环境变量获取根目录，默认为"home"
ROOT_DIR = os.getenv("HOME_DIRECTORY", "home")
BASE_PATH = os.path.join(os.getcwd(), ROOT_DIR)

def get_markdown_files_to_search(path: str, recursive: bool = False) -> List[Tuple[str, str]]:
    """
    获取要搜索的Markdown文件列表
    
    Args:
        path: 搜索路径（文件或目录，支持..访问上级目录）
        recursive: 是否递归搜索子目录（仅当path为目录时有效）
        
    Returns:
        List[Tuple[str, str]]: Markdown文件列表，每个元素为(相对路径, 绝对路径)
    """
    # 构建基于根目录的绝对路径（支持..访问上级目录）
    abs_path = os.path.normpath(os.path.join(BASE_PATH, path))
    
    # 如果是文件，检查是否为.md文件
    if os.path.isfile(abs_path):
        if not abs_path.lower().endswith('.md'):
            return []
        rel_path = os.path.relpath(abs_path, BASE_PATH)
        return [(rel_path, abs_path)]
    
    # 如果是目录，收集目录下的.md文件
    md_files = []
    
    if recursive:
        # 递归搜索
        for root, dirs, files in os.walk(abs_path):
            for file in files:
                if file.lower().endswith('.md'):
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, BASE_PATH)
                    md_files.append((rel_path, file_path))
    else:
        # 非递归搜索
        for item in os.listdir(abs_path):
            item_path = os.path.join(abs_path, item)
            if os.path.isfile(item_path) and item.lower().endswith('.md'):
                rel_path = os.path.relpath(item_path, BASE_PATH)
                md_files.append((rel_path, item_path))
    
    return md_files

def parse_markdown_structure(content: str) -> List[Dict[str, Any]]:
    """
    解析Markdown文档结构，提取标题层级关系
    
    Args:
        content: Markdown文档内容
        
    Returns:
        List[Dict]: 标题结构列表，每个元素包含：
            - level: 标题级别（1-6）
            - title: 标题文本（不含#号）
            - start_line: 标题开始行号
            - end_line: 标题结束行号（下一个同级或更高级标题之前）
            - content: 标题下的所有内容
            - parent_titles: 上级标题链列表
    """
    lines = content.splitlines()
    structure = []
    title_stack = []  # 存储当前标题层级栈，每个元素为(level, title)
    
    # 正则表达式匹配Markdown标题
    title_pattern = re.compile(r'^(#{1,6})\s+(.+)$')
    
    current_section = {
        'level': 0,  # 0表示文档开始
        'title': '文档开始',
        'start_line': 1,
        'end_line': len(lines),
        'content': '',
        'parent_titles': []
    }
    
    for i, line in enumerate(lines, 1):
        match = title_pattern.match(line)
        if match:
            level = len(match.group(1))  # #的数量
            title = match.group(2).strip()
            
            # 结束上一个标题段
            if current_section['level'] > 0:
                current_section['end_line'] = i - 1
                # 提取该标题段的内容
                start_idx = current_section['start_line'] - 1
                end_idx = current_section['end_line']
                section_lines = lines[start_idx:end_idx]
                # 移除标题行本身
                if section_lines and title_pattern.match(section_lines[0]):
                    section_lines = section_lines[1:]
                current_section['content'] = '\n'.join(section_lines).strip()
                structure.append(current_section.copy())
            
            # 更新标题栈
            while title_stack and title_stack[-1][0] >= level:
                title_stack.pop()
            
            # 构建父标题链
            parent_titles = [title for _, title in title_stack]
            title_stack.append((level, title))
            
            # 开始新的标题段
            current_section = {
                'level': level,
                'title': title,
                'start_line': i,
                'end_line': len(lines),  # 临时值，会在遇到下一个标题时更新
                'content': '',
                'parent_titles': parent_titles
            }
    
    # 处理最后一个标题段
    if current_section['level'] > 0:
        current_section['end_line'] = len(lines)
        start_idx = current_section['start_line'] - 1
        end_idx = current_section['end_line']
        section_lines = lines[start_idx:end_idx]
        # 移除标题行本身
        if section_lines and title_pattern.match(section_lines[0]):
            section_lines = section_lines[1:]
        current_section['content'] = '\n'.join(section_lines).strip()
        structure.append(current_section)
    
    return structure

def search_markdown_titles(path: str, keyword: str, recursive: bool = False, 
                          title_level: Optional[int] = None, 
                          include_content: bool = True) -> str:
    """
    在Markdown文件中搜索标题关键词，按照标题层级返回搜索结果
    
    支持三种搜索方式：
    1. 单文件搜索：path指向一个具体.md文件
    2. 文件夹搜索：path指向目录，recursive=False
    3. 文件夹递归搜索：path指向目录，recursive=True
    
    Args:
        path: 搜索路径（可以是文件或目录，支持..访问上级目录）
        keyword: 要搜索的关键词（在标题中搜索）
        recursive: 是否递归搜索子目录（仅当path为目录时有效）
        title_level: 可选，限制搜索的标题级别（如2表示只搜索##级标题）
        include_content: 是否返回标题下的完整内容，默认为True
    
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
        
        keyword = keyword.strip().lower()
        
        if title_level is not None and (title_level < 1 or title_level > 6):
            return f"错误：标题级别必须在1-6之间，收到 {title_level}"
        
        # 获取要搜索的Markdown文件列表
        md_files = get_markdown_files_to_search(path, recursive)
        
        if not md_files:
            # 检查是否是目录但没有.md文件
            if os.path.isdir(abs_path):
                return f"信息：在路径 '{path}' 中未找到Markdown文件（.md）"
            else:
                return f"信息：路径 '{path}' 不是有效的Markdown文件（.md）或目录"
        
        # 对文件进行排序（按相对路径）
        md_files.sort(key=lambda x: x[0])
        
        # 搜索关键词
        all_results = []
        total_matches = 0
        
        for rel_path, file_path in md_files:
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
                
                # 解析Markdown结构
                structure = parse_markdown_structure(content)
                
                # 搜索匹配的标题
                file_matches = []
                
                for section in structure:
                    # 检查标题级别过滤
                    if title_level is not None and section['level'] != title_level:
                        continue
                    
                    # 在标题中搜索关键词（不区分大小写）
                    if keyword in section['title'].lower():
                        # 构建标题层级链
                        title_chain = []
                        for parent_title in section['parent_titles']:
                            title_chain.append(parent_title)
                        title_chain.append(section['title'])
                        
                        # 构建层级表示
                        level_markers = ['#', '##', '###', '####', '#####', '######']
                        level_indicator = level_markers[section['level'] - 1] if section['level'] <= 6 else '#' * section['level']
                        
                        file_matches.append({
                            'level': section['level'],
                            'title': section['title'],
                            'title_chain': title_chain,
                            'level_indicator': level_indicator,
                            'start_line': section['start_line'],
                            'content': section['content'] if include_content else '',
                            'content_length': len(section['content']) if include_content else 0
                        })
                
                if file_matches:
                    total_matches += len(file_matches)
                    file_result = [f"文件: {rel_path} (大小: {file_size}字节)"]
                    
                    for i, match in enumerate(file_matches, 1):
                        file_result.append(f"匹配 {i}/{len(file_matches)}:")
                        file_result.append(f"  标题层级: {' > '.join(match['title_chain'])}")
                        file_result.append(f"  匹配标题: {match['level_indicator']} {match['title']}")
                        file_result.append(f"  位置: 第{match['start_line']}行")
                        
                        if include_content and match['content']:
                            # 限制内容长度
                            max_content_chars = 1000
                            content_preview = match['content']
                            if len(content_preview) > max_content_chars:
                                content_preview = content_preview[:max_content_chars] + "...\n[内容被截断，超过1000字符限制]"
                            
                            file_result.append(f"  标题内容 (字符数: {match['content_length']}):")
                            # 缩进内容
                            content_lines = content_preview.split('\n')
                            for line in content_lines:
                                if line.strip():
                                    file_result.append(f"    {line}")
                                else:
                                    file_result.append("")  # 空行
                        elif include_content:
                            file_result.append(f"  标题内容: (空)")
                        
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
            
            level_info = f"（标题级别: {title_level}）" if title_level is not None else ""
            return f"信息：在 {len(md_files)} 个Markdown文件中未找到包含关键词 '{keyword}' 的标题{level_info}\n搜索模式: {search_mode}"
        
        # 确定搜索模式描述
        if os.path.isfile(abs_path):
            search_mode = "单文件搜索"
        elif recursive:
            search_mode = "文件夹递归搜索"
        else:
            search_mode = "文件夹搜索"
        
        result_lines = [
            f"搜索完成：在 {len(md_files)} 个Markdown文件中找到 {total_matches} 处标题匹配",
            f"关键词: '{keyword}'",
            f"搜索路径: '{path}' (模式: {search_mode})",
            f"标题级别限制: {f'仅{title_level}级标题' if title_level is not None else '所有级别标题'}",
            f"包含内容: {'是' if include_content else '否'}",
            "=" * 60,
            ""
        ]
        
        result_lines.extend(all_results)
        
        return "\n".join(result_lines)
            
    except PermissionError:
        return f"错误：没有权限访问路径 '{path}'"
    except Exception as e:
        return f"错误：搜索Markdown文件时发生异常 - {str(e)}"

# 工具定义（符合OpenAI工具调用规范）
TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "search_markdown_titles",
        "description": "在Markdown文件中搜索标题关键词，按照标题层级返回搜索结果。仅搜索Markdown文件（.md扩展名），专门搜索各级别标题（#、##、###等）。当在某个标题下找到关键词时，返回该标题下的所有内容和所在的上级标题名称。支持三种搜索方式：单文件搜索、文件夹搜索、文件夹递归搜索。支持相对路径（相对于根目录，根目录由环境变量HOME_DIRECTORY指定，默认为'home'），支持使用..访问上级目录。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要搜索的路径（可以是Markdown文件或目录，支持..访问上级目录）"
                },
                "keyword": {
                    "type": "string",
                    "description": "要搜索的关键词（在标题中搜索）"
                },
                "recursive": {
                    "type": "boolean",
                    "description": "搜索目录时是否递归搜索子目录（仅当path为目录时有效）。默认为false"
                },
                "title_level": {
                    "type": "integer",
                    "description": "可选，限制搜索的标题级别（1-6），如2表示只搜索##级标题。默认为搜索所有级别",
                    "minimum": 1,
                    "maximum": 6
                },
                "include_content": {
                    "type": "boolean",
                    "description": "是否返回标题下的完整内容。默认为true"
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
                    "name": "search_markdown_titles",
                    "arguments": "{\"path\": \".\", \"keyword\": \"测试\"}"
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
        if function_name != "search_markdown_titles":
            return f"错误：未知的工具 '{function_name}'"
        
        # 提取参数
        path = arguments.get("path")
        keyword = arguments.get("keyword")
        recursive = arguments.get("recursive", False)
        title_level = arguments.get("title_level")
        include_content = arguments.get("include_content", True)
        
        # 验证必要参数
        if not path:
            return "错误：缺少必要参数 'path'"
        if not keyword:
            return "错误：缺少必要参数 'keyword'"
        
        # 执行工具
        return search_markdown_titles(path, keyword, recursive, title_level, include_content)
        
    except json.JSONDecodeError:
        return "错误：无法解析工具参数（无效的JSON格式）"
    except KeyError as e:
        return f"错误：工具调用格式不正确 - 缺少字段: {str(e)}"
    except Exception as e:
        return f"错误：执行工具时发生异常 - {str(e)}"
