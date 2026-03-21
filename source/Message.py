from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass


@dataclass
class Function:
    name: str
    arguments: str


@dataclass
class ToolCall:
    id: str
    type: str = "function"
    function: Optional[Function] = None

@dataclass
class MultimodalContent:
    type: str # text | image_url
    text: Optional[str] = None
    @dataclass
    class Url:
        url:str
    image_url: Optional[MultimodalContent.Url] = None

@dataclass
class Message:
    role: str
    # content: str
    content: Union[str, List[MultimodalContent]]

    # token usage, for recv only
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None

    tool_calls: Optional[ToolCall] = None
    tool_call_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        use when summiting message to LLM
        """
        dicted_message = {
            "role": self.role,
            "content": []
        }
        if isinstance(self.content, list):
            for content in self.content:
                if content.type == "text":
                    dicted_message["content"].append({
                        "type": "text",
                        "text": content.text
                    })
                elif content.type == "image_url":
                    dicted_message["content"].append({
                        "type": "image_url",
                        "image_url": {
                            "url": content.image_url.url
                        }
                    })
        elif isinstance(self.content, str):
            dicted_message["content"].append({
                "type": "text",
                "text": self.content
            })
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

Assistant Message(Multimodal)
role: assistant
content: [
    {type: text, text: ...},
    {type: image_url, image_url: {url: ...}}
]

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