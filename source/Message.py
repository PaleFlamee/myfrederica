from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class Function:
    """工具调用函数"""
    name: str
    arguments: str


@dataclass
class ToolCall:
    """工具调用"""
    id: str
    type: str = "function"
    function: Optional[Function] = None


@dataclass
class Message:
    """消息类"""
    role: str
    content: str

    # token usage, for recv only
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None

    tool_calls: Optional[ToolCall] = None  # dpsk的文档没说request有这个字段,还要填东西
    tool_call_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        use when summiting message to LLM
        """
        dicted_message = {
            "role": self.role,
            "content": self.content
        }
        if self.tool_calls:
            dicted_message["tool_calls"] = [{
                "id": self.tool_calls.id,
                "type": self.tool_calls.type,
                "function": {
                    "name": self.tool_calls.function.name,
                    "arguments": self.tool_calls.function.arguments
                }
            }]
        if self.tool_call_id:
            dicted_message["tool_call_id"] = self.tool_call_id
        return dicted_message

'''
Assistant Message(Tool Call):
role: assistant
content: ... | None
tcid: None
tool_calls:
    id: ...
    type: function
    function:
        name: ...
        arguments: ...

Assitant Message(No Tool Call):
role: assistant
content: ...
tcid: None
tool_calls: None

Tool Call Message:
role: tool
content: ...
tcid: ...
tool_calls: None

User / System Message:
role: user / system
content: ...
tcid: None
tool_calls: None

'''