from typing import List, Optional
from .Message import Message
import datetime
from .Config import Config

def general_output_msg_list(msg_list: List[Message], is_print: bool = False) -> str:
    """处理消息列表"""
    output: str = ""
    for msg in msg_list:
        output += general_output_msg_single(msg, is_print)
    return output


def general_output_msg_single(msg: Message, is_print: bool = False) -> str:
    """处理单个消息"""
    # 安全地获取 tool_call_id
    tool_call_id_str = msg.tool_call_id[-5:-1] if msg.tool_call_id else "None"
    
    # 安全地获取 tool_calls 信息
    tool_call_info:str = "None"
    if msg.tool_calls:
        func_name = msg.tool_calls.function.name# if msg.tool_calls.function else ""
        func_args = msg.tool_calls.function.arguments# if msg.tool_calls.function else ""
        tool_id = msg.tool_calls.id[-5:-1] # if msg.tool_calls.id else ""
        tool_call_info = f"{tool_id}|{func_name}|{func_args}"

    opt_content:str = ""
    if isinstance(msg.content, str):
        opt_content = msg.content
    else:
        for content in msg.content:
            if content.type == "text":
                opt_content += f"<text>{content.text}"
            elif content.type == "image_url":
                opt_content += f"<image>{content.image_url.url[:20]}..."
    
    output = f"[r:{msg.role}][tcid:{tool_call_id_str}][tkn:{msg.prompt_tokens}|{msg.completion_tokens}][tcif:{tool_call_info}][cont]:{opt_content}\n"
    
    if is_print:
        print(output)
    return output


# 为了向后兼容，保留 general_output_msg 作为单个消息处理的别名
general_output_msg = general_output_msg_single


def display_message(role: str, content: str, indent: int = 0):
    """
    显示格式化消息
    
    Args:
        role: 消息角色 (User, Assistant, Tool Call, Tool Result, ...)
        content: 要写入的内容
        indent: 缩进级别
    """
    if role == "Debug":
        return
    indent_str = " " * indent
    print(f"{indent_str}[{role}] > {content}")

def add_timestamp_to_msg_list(messages: List[Message]) -> List[Message]:
    msgs_with_timestamp: List[Message] = []
    for message in messages:
        if isinstance(message.content, str):  # content is a string
            message.content = datetime.datetime.now().strftime("<%Y-%m-%d@%H:%M:%S>") + message.content
        else: # content is a list(multimodal)
            for content in message.content:
                if content.type == "text":
                    content.text = datetime.datetime.now().strftime("<%Y-%m-%d@%H:%M:%S>") + content.text
        msgs_with_timestamp.append(message)
    return msgs_with_timestamp

global_config_inst: Optional[Config] = None
def get_config_instance() -> Config:
    global global_config_inst
    if global_config_inst is None:
        global_config_inst = Config()
    return global_config_inst