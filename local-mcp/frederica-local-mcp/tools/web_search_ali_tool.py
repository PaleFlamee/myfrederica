#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
web_search_ali_tool.py
供LLM使用的阿里云OpenSearch网络搜索工具
支持通过tool_call调用，进行网络搜索并返回格式化的搜索结果
"""

import json
import time
import os
from typing import Dict, Any, List
import requests
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def web_search_ali(query: str, max_results: int = 5) -> str:
    """
    使用阿里云OpenSearch进行网络搜索
    
    Args:
        query: 搜索关键词
        max_results: 最大返回结果数，默认为5，范围1-10
    
    Returns:
        str: 格式化的搜索结果或错误信息
    """
    try:
        # 验证参数
        if not query or not query.strip():
            return "错误：搜索关键词不能为空"
        
        query = query.strip()
        
        # 验证max_results范围
        if not isinstance(max_results, int):
            return f"错误：max_results必须是整数，收到 '{type(max_results).__name__}'"
        
        if max_results < 1:
            return f"错误：max_results必须大于0，收到 {max_results}"
        
        if max_results > 10:
            return f"错误：max_results不能超过10，收到 {max_results}"
        
        # 获取配置
        api_key = os.getenv("ALI_OPENSEARCH_API_KEY")
        host = os.getenv("ALI_OPENSEARCH_HOST")
        workspace = os.getenv("ALI_OPENSEARCH_WORKSPACE", "default")
        service_id = os.getenv("ALI_OPENSEARCH_SERVICE_ID", "ops-web-search-001")
        
        # 验证配置
        if not api_key:
            return "错误：未配置阿里云OpenSearch API密钥，请在.env文件中设置ALI_OPENSEARCH_API_KEY"
        
        if not host:
            return "错误：未配置阿里云OpenSearch服务地址，请在.env文件中设置ALI_OPENSEARCH_HOST"
        
        # 构建API URL
        url = f"{host}/v3/openapi/workspaces/{workspace}/web-search/{service_id}"
        
        # 请求头
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        # 请求体
        data = {
            "query": query,
            "top_k": max_results,
            "query_rewrite": True,
            "content_type": "snippet"
        }
        
        # 执行搜索（带重试机制）
        max_retries = 2
        retry_delay = 1  # 秒
        
        for attempt in range(max_retries):
            try:
                response = requests.post(url, headers=headers, json=data, timeout=30)
                
                # 检查响应状态
                if response.status_code == 200:
                    result_data = response.json()
                    break  # 成功则跳出循环
                else:
                    error_msg = f"API请求失败，状态码: {response.status_code}"
                    if response.text:
                        try:
                            error_json = response.json()
                            error_msg += f", 错误信息: {error_json}"
                        except:
                            error_msg += f", 响应内容: {response.text[:200]}"
                    
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    else:
                        return f"错误：{error_msg}"
                        
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    return "错误：API请求超时（30秒）"
            except requests.exceptions.ConnectionError:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    return "错误：无法连接到阿里云OpenSearch服务，请检查网络连接和服务地址"
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    return f"错误：API请求异常 - {str(e)}"
        
        # 检查是否有结果
        if "result" not in result_data or "search_result" not in result_data["result"]:
            return f"信息：未找到关于 '{query}' 的搜索结果"
        
        search_results = result_data["result"]["search_result"]
        
        if not search_results:
            return f"信息：未找到关于 '{query}' 的搜索结果"
        
        # 格式化结果
        formatted_results = []
        formatted_results.append(f"搜索结果（共找到 {len(search_results)} 条）：")
        
        for i, result in enumerate(search_results, 1):
            title = result.get('title', '无标题')
            link = result.get('link', '无链接')
            snippet = result.get('snippet', '无摘要')
            content = result.get('content', '')
            
            # 优先使用snippet，如果没有则使用content
            body = snippet if snippet else content
            
            # 限制摘要长度
            if body and len(body) > 2048:
                body = body[:2048] + "..."
            
            formatted_results.append(f"{i}. 标题：{title}")
            formatted_results.append(f"   URL：{link}")
            formatted_results.append(f"   摘要：{body}")
            
            # 如果不是最后一条结果，添加空行分隔
            if i < len(search_results):
                formatted_results.append("")
        
        return "\n".join(formatted_results)
        
    except ImportError:
        return "错误：未安装requests库，请运行 'pip install requests>=2.28.0'"
    except Exception as e:
        return f"错误：搜索过程中发生异常 - {str(e)}"

# 工具定义（符合OpenAI工具调用规范）
TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "web_search_ali",
        "description": "使用阿里云OpenSearch进行网络搜索。返回包含标题、URL和摘要的格式化搜索结果。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词"
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大返回结果数。默认为5，最小为1，最大为10",
                    "minimum": 1,
                    "maximum": 10
                }
            },
            "required": ["query"]
        }
    }
}

def execute_tool_call(arguments:dict) -> str:
    try:
        # 提取参数
        query = arguments.get("query")
        max_results = arguments.get("max_results", 5)
        
        # 验证必要参数
        if not query:
            return "错误：缺少必要参数 'query'"
        
        # 验证max_results参数类型
        if not isinstance(max_results, int):
            return f"错误：参数 'max_results' 必须是整数，收到 '{type(max_results).__name__}'"
        
        # 执行工具
        return web_search_ali(query, max_results)
        
    except json.JSONDecodeError:
        return "错误：无法解析工具参数（无效的JSON格式）"
    except KeyError as e:
        return f"错误：工具调用格式不正确 - 缺少字段: {str(e)}"
    except Exception as e:
        return f"错误：执行工具时发生异常 - {str(e)}"

def demo_basic_usage():
    """
    演示基本用法
    """
    print("=== 阿里云OpenSearch搜索工具基本演示 ===\n")
    
    # 测试1：基本搜索
    print("1. 基本搜索（查询'Python编程'，默认5条结果）:")
    result = web_search_ali("Python编程")
    print(f"   结果前300字符:\n{result[:300]}...\n")
    
    # 测试2：限制结果数量
    print("2. 限制结果数量（查询'人工智能'，3条结果）:")
    result = web_search_ali("人工智能", max_results=3)
    print(f"   结果前300字符:\n{result[:300]}...\n")
    
    # 测试3：空查询
    print("3. 测试空查询:")
    result = web_search_ali("")
    print(f"   结果: {result}\n")
    
    # 测试4：无效的max_results
    print("4. 测试无效的max_results（查询'test'，max_results=0）:")
    result = web_search_ali("test", max_results=0)
    print(f"   结果: {result}\n")
    
    # 测试5：工具调用
    print("5. 模拟工具调用:")
    tool_call = {
        "id": "call_demo_001",
        "type": "function",
        "function": {
            "name": "web_search_ali",
            "arguments": json.dumps({
                "query": "机器学习",
                "max_results": 2
            })
        }
    }
    result = execute_tool_call(tool_call)
    print(f"   工具调用结果前400字符:\n{result[:400]}...\n")
    
    print("=== 演示完成 ===")

if __name__ == "__main__":
    # 运行基本演示
    demo_basic_usage()