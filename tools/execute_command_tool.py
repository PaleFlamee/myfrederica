import subprocess
import json
from typing import Dict, Any

# ── 1. 工具定义（OpenAI function calling 格式）──────────────────────
TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "execute_command",
        "description": "在本机执行一条 Linux shell 命令，返回 stdout 和 stderr",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的 shell 命令，例如 'ls -la /tmp'"
                },
                "timeout": {
                    "type": "integer",
                    "description": "超时秒数，默认 30",
                    "default": 30
                }
            },
            "required": ["command"]
        }
    }
}


# ── 2. 实际执行函数 ──────────────────────────────────────────────────
def execute_command(command: str, timeout: int = 30) -> dict:
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return f"success\n\
stdout: {(result.stdout[:4096] + "[TRUNCATED]") if len(result.stdout) > 4096 else result.stdout}\n\
stderr: {(result.stderr[:4096] + "[TRUNCATED]") if len(result.stderr) > 4096 else result.stderr}\n\
returncode: {result.returncode}"
    except subprocess.TimeoutExpired:
        #return {"error": f"命令超时({timeout}s)", "returncode": -1}
        return f"error: command timeout ({timeout}s)"
    except Exception as e:
        return f"error: {str(e)}"

def execute_tool_call(tool_call: Dict[str, Any]) -> str:
    try:
        tool_call_data = json.loads(tool_call["function"]["arguments"])
        return execute_command(**tool_call_data)
    except json.JSONDecodeError as e:
        return f"错误：工具调用格式不正确 - 缺少字段: {str(e)}"
    except Exception as e:
        return f"错误：执行工具时发生异常 - {str(e)}"