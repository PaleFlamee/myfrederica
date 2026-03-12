#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
execute_command_tool.py
供LLM使用的Linux命令执行工具
支持通过tool_call调用，执行Linux命令并返回结果
注意：这是一个实验性项目，允许执行危险命令，但需要confirm_dangerous参数确认
"""

import subprocess
import os
import signal
import time
import re
import json
from typing import Dict, Any, List, Tuple
import shlex
import sys

# 默认配置
DEFAULT_TIMEOUT = 30  # 默认超时时间（秒）
MAX_TIMEOUT = 300     # 最大超时时间（秒）
MAX_OUTPUT_SIZE = 1024 * 1024  # 最大输出大小（1MB）
DEFAULT_WORKING_DIR = os.getcwd()  # 默认工作目录：当前项目目录

# 危险命令模式（用于检测危险命令）
DANGEROUS_PATTERNS = [
    r'rm\s+.*-rf',          # rm -rf（递归强制删除）
    r'rm\s+.*-r\s+.*-f',    # rm -r -f
    r'dd\s+',               # dd命令（磁盘操作）
    r'chmod\s+.*777\s+',    # 危险权限设置
    r'chmod\s+.*777$',      # 危险权限设置（行尾）
    r'mkfs\s+',             # 磁盘格式化
    r'fdisk\s+',            # 磁盘分区
    r'>\s+/dev/',           # 输出到设备文件
    r'\|\s*sh\s*$',         # 管道到shell
    r'\$\s*\(',             # 命令替换
    r'wget\s+.*\|\s*sh',    # 下载并执行
    r'curl\s+.*\|\s*sh',    # 下载并执行
    r':\(\)\{:\|:\&\};\:',  # fork炸弹
    r'mv\s+/\s+',           # 移动根目录
    r'cp\s+/\s+',           # 复制根目录
]

def is_dangerous_command(full_command: str) -> bool:
    """
    检测命令是否危险
    
    Args:
        full_command: 完整的命令字符串
        
    Returns:
        bool: 如果命令危险返回True，否则返回False
    """
    # 转换为小写进行不区分大小写的匹配
    command_lower = full_command.lower()
    
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, command_lower):
            return True
    
    # 检查是否包含sudo
    if 'sudo' in command_lower:
        return True
    
    return False

def execute_linux_command(
    command: str,
    args: List[str] = None,
    timeout: int = DEFAULT_TIMEOUT,
    working_directory: str = None,
    confirm_dangerous: bool = False
) -> str:
    """
    执行Linux命令并返回结果
    
    Args:
        command: 要执行的命令
        args: 命令参数列表
        timeout: 超时时间（秒）
        working_directory: 工作目录路径
        confirm_dangerous: 确认为危险命令
        
    Returns:
        str: 命令执行结果或错误信息
    """
    try:
        import platform
        
        # 构建完整命令字符串（用于危险检测）
        full_args = [command] + (args or [])
        full_command_str = ' '.join([shlex.quote(arg) for arg in full_args])
        
        # 检查是否为危险命令
        if is_dangerous_command(full_command_str) and not confirm_dangerous:
            return (
                f"错误：检测到危险命令 '{full_command_str}'\n"
                f"要执行此命令，必须设置 confirm_dangerous=true 参数以确认理解风险。\n"
                f"危险操作包括：删除文件、磁盘操作、权限修改、下载执行等。"
            )
        
        # 验证超时时间
        if not isinstance(timeout, int) or timeout <= 0:
            return f"错误：超时时间必须为正整数，收到 '{timeout}'"
        
        if timeout > MAX_TIMEOUT:
            return f"错误：超时时间不能超过{MAX_TIMEOUT}秒，收到 {timeout}秒"
        
        # 确定工作目录
        if working_directory:
            if not os.path.isdir(working_directory):
                return f"错误：工作目录不存在 '{working_directory}'"
            cwd = working_directory
        else:
            cwd = DEFAULT_WORKING_DIR
        
        # 准备执行命令
        cmd_list = [command]
        if args:
            cmd_list.extend(args)
        
        # 在Windows上，对于内部命令需要使用cmd.exe /c
        if platform.system() == "Windows":
            # 检查是否是Windows内部命令
            windows_internal_commands = [
                'dir', 'echo', 'del', 'copy', 'move', 'ren', 'type',
                'cd', 'md', 'rd', 'cls', 'ver', 'vol', 'path', 'prompt',
                'set', 'time', 'date', 'pause', 'rem', 'break', 'call',
                'for', 'goto', 'if', 'shift', 'start', 'choice'
            ]
            
            if command.lower() in windows_internal_commands:
                # 使用cmd.exe /c执行内部命令
                cmd_list = ['cmd.exe', '/c'] + cmd_list
                full_command_str = f'cmd.exe /c {full_command_str}'
        
        # 执行命令
        start_time = time.time()
        
        try:
            # 使用subprocess.run执行命令
            result = subprocess.run(
                cmd_list,
                cwd=cwd,
                timeout=timeout,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'  # 替换无法解码的字符
            )
            
            execution_time = time.time() - start_time
            
            # 构建结果
            output_parts = []
            output_parts.append(f"命令执行完成（耗时: {execution_time:.2f}秒）")
            output_parts.append(f"工作目录: {cwd}")
            output_parts.append(f"完整命令: {full_command_str}")
            output_parts.append(f"退出码: {result.returncode}")
            
            # 添加标准输出
            if result.stdout:
                # 限制输出大小
                if len(result.stdout) > MAX_OUTPUT_SIZE:
                    output_parts.append(f"标准输出（前{MAX_OUTPUT_SIZE}字节）:")
                    output_parts.append(result.stdout[:MAX_OUTPUT_SIZE] + "\n...（输出被截断）")
                else:
                    output_parts.append("标准输出:")
                    output_parts.append(result.stdout)
            else:
                output_parts.append("标准输出: （空）")
            
            # 添加标准错误
            if result.stderr:
                # 限制输出大小
                if len(result.stderr) > MAX_OUTPUT_SIZE:
                    output_parts.append(f"标准错误（前{MAX_OUTPUT_SIZE}字节）:")
                    output_parts.append(result.stderr[:MAX_OUTPUT_SIZE] + "\n...（输出被截断）")
                else:
                    output_parts.append("标准错误:")
                    output_parts.append(result.stderr)
            elif result.returncode != 0:
                output_parts.append("标准错误: （空，但命令返回非零退出码）")
            else:
                output_parts.append("标准错误: （空）")
            
            # 如果是危险命令且已确认，添加警告
            if is_dangerous_command(full_command_str) and confirm_dangerous:
                output_parts.append("\n⚠️ 警告：已执行危险命令，请确认操作意图正确。")
            
            return "\n".join(output_parts)
            
        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            return (
                f"错误：命令执行超时（超过{timeout}秒，实际运行{execution_time:.2f}秒）\n"
                f"命令: {full_command_str}\n"
                f"工作目录: {cwd}\n"
                f"提示：可以尝试增加timeout参数值，但最大不能超过{MAX_TIMEOUT}秒。"
            )
            
        except FileNotFoundError:
            return f"错误：命令未找到 '{command}'\n请检查命令是否存在且位于PATH环境变量中。"
            
        except PermissionError:
            return f"错误：没有权限执行命令 '{command}'\n请检查文件权限。"
    
    except Exception as e:
        return f"错误：执行命令时发生异常 - {str(e)}"

# 工具定义（符合OpenAI工具调用规范）
TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "execute_command",
        "description": (
            "执行Linux命令并返回结果。对于危险命令（如rm -rf, dd, chmod 777等），"
            "必须设置confirm_dangerous=true以确认理解风险。"
            "支持设置超时时间（默认30秒，最大300秒）和工作目录。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的命令（如'ls', 'ps', 'cat', 'pwd'等）"
                },
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "命令参数列表（如['-la', '/tmp']）"
                },
                "timeout": {
                    "type": "integer",
                    "description": f"超时时间（秒），默认{DEFAULT_TIMEOUT}，最大{MAX_TIMEOUT}",
                    "minimum": 1,
                    "maximum": MAX_TIMEOUT
                },
                "working_directory": {
                    "type": "string",
                    "description": "工作目录路径，默认为当前项目目录"
                },
                "confirm_dangerous": {
                    "type": "boolean",
                    "description": "确认为危险命令，必须为true才能执行危险操作"
                }
            },
            "required": ["command"]
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
                    "name": "execute_command",
                    "arguments": "{\"command\": \"ls\", \"args\": [\"-la\"]}"
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
        if function_name != "execute_command":
            return f"错误：未知的工具 '{function_name}'"
        
        # 提取参数
        command = arguments.get("command")
        args = arguments.get("args", [])
        timeout = arguments.get("timeout", DEFAULT_TIMEOUT)
        working_directory = arguments.get("working_directory")
        confirm_dangerous = arguments.get("confirm_dangerous", False)
        
        # 验证必要参数
        if not command:
            return "错误：缺少必要参数 'command'"
        
        # 验证参数类型
        if not isinstance(args, list):
            return f"错误：参数 'args' 必须是数组，收到 '{type(args).__name__}'"
        
        # 验证args中的每个元素都是字符串
        for i, arg in enumerate(args):
            if not isinstance(arg, str):
                return f"错误：参数 'args[{i}]' 必须是字符串，收到 '{type(arg).__name__}'"
        
        if not isinstance(timeout, int):
            return f"错误：参数 'timeout' 必须是整数，收到 '{type(timeout).__name__}'"
        
        if not isinstance(confirm_dangerous, bool):
            return f"错误：参数 'confirm_dangerous' 必须是布尔值，收到 '{type(confirm_dangerous).__name__}'"
        
        # 执行工具
        return execute_linux_command(
            command=command,
            args=args,
            timeout=timeout,
            working_directory=working_directory,
            confirm_dangerous=confirm_dangerous
        )
        
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
    import platform
    
    system = platform.system()
    print(f"=== 命令执行工具基本演示（系统: {system}） ===\n")
    
    if system == "Windows":
        # Windows系统测试
        print("1. 基本命令（执行 'dir'）:")
        result = execute_linux_command("dir")
        print(f"   结果:\n{result[:200]}...\n")
        
        print("2. 带参数的命令（执行 'echo Hello World'）:")
        result = execute_linux_command("echo", ["Hello", "World"])
        print(f"   结果前300字符:\n{result[:300]}...\n")
        
        print("3. 危险命令测试（执行 'del /f /q test.txt'，未确认）:")
        result = execute_linux_command("del", ["/f", "/q", "test.txt"])
        print(f"   结果:\n{result}\n")
        
        print("4. 危险命令测试（执行 'echo test > test.txt'，已确认）:")
        result = execute_linux_command("echo", ["test"], confirm_dangerous=True)
        print(f"   结果:\n{result}\n")
        
        print("5. 超时测试（执行 'timeout /t 2'，超时1秒）:")
        result = execute_linux_command("timeout", ["/t", "2"], timeout=1)
        print(f"   结果:\n{result}\n")
        
        print("6. 系统信息命令（执行 'systeminfo'）:")
        result = execute_linux_command("systeminfo")
        print(f"   结果前200字符:\n{result[:200]}...\n")
        
    else:
        # Linux/Unix系统测试
        print("1. 基本命令（执行 'pwd'）:")
        result = execute_linux_command("pwd")
        print(f"   结果:\n{result[:200]}...\n")
        
        print("2. 带参数的命令（执行 'ls -la'）:")
        result = execute_linux_command("ls", ["-la"])
        print(f"   结果前300字符:\n{result[:300]}...\n")
        
        print("3. 危险命令测试（执行 'rm -rf /tmp/test'，未确认）:")
        result = execute_linux_command("rm", ["-rf", "/tmp/test"])
        print(f"   结果:\n{result}\n")
        
        print("4. 危险命令测试（执行 'echo test > /tmp/test.txt'，已确认）:")
        result = execute_linux_command("echo", ["test"], confirm_dangerous=True)
        print(f"   结果:\n{result}\n")
        
        print("5. 超时测试（执行 'sleep 2'，超时1秒）:")
        result = execute_linux_command("sleep", ["2"], timeout=1)
        print(f"   结果:\n{result}\n")
        
        print("6. 系统信息命令（执行 'uname -a'）:")
        result = execute_linux_command("uname", ["-a"])
        print(f"   结果前200字符:\n{result[:200]}...\n")
    
    # 通用测试
    print("7. 不存在的命令测试（执行 'nonexistentcommand'）:")
    result = execute_linux_command("nonexistentcommand")
    print(f"   结果:\n{result}\n")
    
    print("8. 模拟工具调用（执行 'echo Test Tool Call'）:")
    tool_call = {
        "id": "call_demo_001",
        "type": "function",
        "function": {
            "name": "execute_command",
            "arguments": json.dumps({
                "command": "echo",
                "args": ["Test", "Tool", "Call"],
                "timeout": 10
            })
        }
    }
    result = execute_tool_call(tool_call)
    print(f"   工具调用结果前200字符:\n{result[:200]}...\n")
    
    print("=== 演示完成 ===")

if __name__ == "__main__":
    # 运行基本演示
    demo_basic_usage()