from typing import List, Optional
from .Message import Message
import datetime


def general_output_msg_list(msg_list: List[Message], is_print: bool = False) -> str:
    """处理消息列表"""
    output: str = ""
    for msg in msg_list:
        output += "\n"
        output += general_output_msg_single(msg, is_print)
    return output


def general_output_msg_single(msg: Message, is_print: bool = False) -> str:
    """处理单个消息"""
    # 安全地获取 tool_call_id
    tool_call_id_str = msg.tool_call_id if msg.tool_call_id else "None"
    
    # 安全地获取 tool_calls 信息
    tool_call_info = ""
    if msg.tool_calls:
        func_name = msg.tool_calls.function.name# if msg.tool_calls.function else ""
        func_args = msg.tool_calls.function.arguments# if msg.tool_calls.function else ""
        tool_id = msg.tool_calls.id# if msg.tool_calls.id else ""
        tool_call_info = f"|{tool_id}|{func_name}|{func_args}"
    
    output = f"[r:{msg.role}][tcid:{tool_call_id_str}]Opt[tcif:{tool_call_info}][cont]:{msg.content}"
    
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
        message.content = datetime.datetime.now().strftime("<%Y-%m-%d@%H:%M:%S>") + message.content
        msgs_with_timestamp.append(message)
    return msgs_with_timestamp