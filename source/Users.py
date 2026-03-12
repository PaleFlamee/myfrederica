from typing import *
from threading import Thread
from openai import OpenAI
from dotenv import load_dotenv
import os
from time import sleep
import json
from .Utils import *
from .Message import *
import logging
logger = logging.getLogger(__name__)

# get env
load_dotenv()
LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE"))

USER_CONVERSATION_EXPIRE_TIMEOUT = datetime.timedelta(minutes=int(os.getenv("USER_CONVERSATION_EXPIRE_TIMEOUT", "1")))

HOME_DIRECTORY = os.getenv("HOME_DIRECTORY", "home")
SOUL_FILE = os.getenv("SOUL_FILE", "soul.md")

from tools.list_file_tool import execute_tool_call as execute_list, TOOL_DEFINITION as LIST_TOOL
from tools.read_file_tool import execute_tool_call as execute_read, TOOL_DEFINITION as READ_TOOL
from tools.create_file_or_folder_tool import execute_tool_call as execute_create, TOOL_DEFINITION as CREATE_TOOL
from tools.write_to_file_tool import execute_tool_call as execute_write, TOOL_DEFINITION as WRITE_TOOL
from tools.search_files_tool import execute_tool_call as execute_search, TOOL_DEFINITION as SEARCH_TOOL
from tools.delete_file_or_folder_tool import execute_tool_call as execute_delete, TOOL_DEFINITION as DELETE_TOOL
from tools.replace_in_file_tool import execute_tool_call as execute_replace, TOOL_DEFINITION as REPLACE_TOOL
from tools.duckduckgo_search_tool import execute_tool_call as execute_duckduckgo, TOOL_DEFINITION as DUCKDUCKGO_TOOL
from tools.fetch_url_tool import execute_tool_call as execute_fetch_url, TOOL_DEFINITION as FETCH_URL_TOOL
from tools.execute_command_tool import execute_tool_call as execute_command, TOOL_DEFINITION as EXECUTE_COMMAND_TOOL
def testing_tool(tool_calls:Dict[str,Any])->str:
    function_name = tool_calls["function"]["name"]
    arguments_str = tool_calls["function"]["arguments"]
    arguments = json.loads(arguments_str)
    
    # 验证工具名称
    if function_name != "testing_tool":
        return f"错误：未知的工具 '{function_name}'"
    
    # 提取参数
    test_str = arguments.get("test_str")
    display_message("Testing tool Recv", test_str)
    return "Successfully get " + test_str
TESTING_TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "testing_tool",
        "description": (
            "测试用工具，回显参数"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "test_str": {
                    "type": "string",
                    "description": "回显的参数"
                }
            },
            "required": ["test_str"]
        }
    }
}

TOOLS = [
    TESTING_TOOL_DEF,
    LIST_TOOL,
    READ_TOOL,
    CREATE_TOOL,
    WRITE_TOOL,
    SEARCH_TOOL,
    DELETE_TOOL,
    REPLACE_TOOL,
    DUCKDUCKGO_TOOL,
    FETCH_URL_TOOL,
    EXECUTE_COMMAND_TOOL
]
TOOL_EXECUTORS = {
    "testing_tool" : testing_tool,
    "list_files": execute_list,
    "read_file": execute_read,
    "create_file_or_folder": execute_create,
    "write_file": execute_write,
    "search_files": execute_search,
    "delete_file_or_folder": execute_delete,
    "replace_in_file": execute_replace,
    "duckduckgo_search": execute_duckduckgo,
    "fetch_url": execute_fetch_url,
    "execute_command": execute_command
}

client = OpenAI(
    api_key = LLM_API_KEY,
    base_url = LLM_BASE_URL
)
def get_llm_response(chat_history:List[Message]) -> Message:
    dicted_chat_history = [message.to_dict() for message in chat_history]
    response = client.chat.completions.create(
        messages = dicted_chat_history,
        model = LLM_MODEL,
        max_tokens = LLM_MAX_TOKENS,
        temperature = LLM_TEMPERATURE,
        stream = False,
        tools = TOOLS,
        tool_choice="auto"
    )
    # return response.choices[0].message
    return Message(
        role = response.choices[0].message.role,
        content = response.choices[0].message.content,
        tool_calls = response.choices[0].message.tool_calls[0] if response.choices[0].message.tool_calls else None,
        tool_call_id = response.choices[0].message.tool_calls[0].id if response.choices[0].message.tool_calls else None
    )



class UserManager:
    class User:
        user_id:str
        chat_history:List[Message]
        awaiting_queue:List[Message]
        last_active_time:datetime
        is_active:bool
        is_farewell_caused_active:bool
        processing_thread:Optional[Thread]
        session_file:Optional[TextIO]
        def __init__(self, user_id):
            logger.info(f"Creating user {user_id}")
            self.user_id = user_id
            self.processing_thread = Thread(
                target=self.process_loop,
                daemon=True
            )
            self.self_reset_active()
            self.processing_thread.start()


        def self_reset_active(self) -> None:
            self.chat_history = []
            self.awaiting_queue = []
            self.last_active_time = datetime.datetime.now()
            self.is_active = True
            self.is_farewell_caused_active = False
            self.session_file = open(
                os.path.join(HOME_DIRECTORY, "sessions", f"{self.user_id}.{self.last_active_time.strftime("%Y-%m-%d.%H-%M-%S")}.txt"),
                "a",
                encoding="utf-8",
                buffering=1
            )
        def process_loop(self) -> None:
            '''
            Process loop for each user
            '''
            while True:
                logger.debug(f"{self.user_id} processing loop")
                while self.is_active or self.is_farewell_caused_active:
                    if len(self.awaiting_queue) > 0:
                        # if anything in await queue
                        logger.debug(f"{self.user_id} awq msg count:{len(self.awaiting_queue)}")
                        self.chat_history.extend(self.awaiting_queue)
                        self.awaiting_queue = []
                        logger.debug(f"{self.user_id} extended chat history & awq cleared")
                        logger.debug(f"{self.user_id} chat history:"); logger.debug(general_output_msg_list(self.chat_history))
                        
                        response:Message = get_llm_response(self.chat_history)
                        logger.debug(f"{self.user_id} 1# response:"); logger.debug(general_output_msg(response))
                        self.process_tool_calls(response)
                        if self.is_farewell_caused_active:
                            self.session_file.close()
                            logger.info(f"{self.user_id} session file closed")
                            self.is_farewell_caused_active = False # execute only once 
                    else:
                        # no message in awqueue
                        logger.debug(f"{self.user_id} no msg in awq")
                        if self.is_active and datetime.datetime.now() - self.last_active_time > USER_CONVERSATION_EXPIRE_TIMEOUT:
                            # this block execute only once
                            # stop processing thread
                            self.is_active = False
                            self.is_farewell_caused_active = True
                            logger.info(f"{self.user_id} is no longer active, set fwactive to True")
                            self.farewell()
                            # logger.debug(f"{self.user_id} processing thread stopped")
                        
                    sleep(1) # gap between active check
                sleep(1) # for safety
        def process_tool_calls(self, current_assistant_message:Message) -> None: # Recursively process tool calls
            # handle new ast msg here
            self.send_message(current_assistant_message)

            logger.debug(f"{self.user_id} enter tool call processing")
            logger.debug(f"{self.user_id} current ast msg:"); logger.debug(general_output_msg(current_assistant_message))
            if current_assistant_message.tool_calls:
                logger.debug(f"{self.user_id} tool call")
                display_message("Assistant", f"{self.user_id} {current_assistant_message.content}")
                display_message("Tool Call", f"{self.user_id} {current_assistant_message.tool_calls.function.name} & {current_assistant_message.tool_calls.function.arguments}", 2)
                self.chat_history.append(current_assistant_message) # append & write always together
                self.session_file.write(f"[{current_assistant_message.role}|tool_call_id:{current_assistant_message.tool_calls.id}]: {current_assistant_message.content}\n")
                logger.debug(f"{self.user_id} append ast msg to chat history: "); logger.debug(general_output_msg(current_assistant_message))
                tool_message = self.execute_tools(current_assistant_message.tool_calls)
                display_message("Tool Response", f"{self.user_id} {tool_message}")
                self.chat_history.append(tool_message) # append & write always together
                self.session_file.write(f"[{tool_message.role}|tool_call_id:{tool_message.tool_call_id}]: {tool_message.content}\n")
                logger.debug(f"{self.user_id} append tool msg to chat history: "); logger.debug(general_output_msg(tool_message))
                current_assistant_message = get_llm_response(self.chat_history)
                logger.debug(f"{self.user_id} refresh ast msg:"); logger.debug(general_output_msg(current_assistant_message))
                self.process_tool_calls(current_assistant_message)
            else:
                logger.debug(f"{self.user_id} no tool calls")
                display_message("Assistant", f"{self.user_id} {current_assistant_message.content}")
                self.chat_history.append(current_assistant_message) # append & write always together
                self.session_file.write(f"[{current_assistant_message.role}|tool_call_id:{current_assistant_message.tool_calls.id if current_assistant_message.tool_calls else "None"}]: {current_assistant_message.content}\n")
                logger.debug(f"{self.user_id} append ast msg to chat history: "); logger.debug(general_output_msg(current_assistant_message))
                logger.debug(f"{self.user_id} chat history:"); logger.debug(general_output_msg_list(self.chat_history))

        def execute_tools(self, tool_calls: ToolCall) -> Message:
            """Execute the tools called by the LLM."""
            logger.debug(f"{self.user_id} Executing tools...")
            
            dicted_tool_call = {
                "id": tool_calls.id,
                "type": "function",
                "function": {
                    "name": tool_calls.function.name,
                    "arguments": tool_calls.function.arguments
                }
            }
            tool_response = TOOL_EXECUTORS[dicted_tool_call["function"]["name"]](dicted_tool_call)
            logger.debug(f"{self.user_id} tool executed, cont:"); logger.debug(tool_response)
            return Message(
                role="tool", 
                content=tool_response,
                tool_call_id=tool_calls.id,
                tool_calls=None
            )

        def send_message(self, message: Message) -> None:
            from .WeChatClient import get_wechat_client
            wechat_client=get_wechat_client()
            if message.role == "assistant":
                content_to_send = message.content
                if message.tool_calls:
                    content_to_send += f"\n---\nTool Call: {message.tool_calls.function.name}"
                wechat_client.send_text_message(
                    self.user_id, 
                    content_to_send
                )
            elif message.role == "tool":
                pass
            elif message.role == "user" or message.role == "system": # should never happen
                pass
            else: # ???
                raise ValueError(f"Invalid message role: {message.role}")
                

        def farewell(self) -> None:
            self.new_message([Message(role="user", content=f"\
[SYSTEM MESSAGE]\
{self.user_id} has been in silence for {USER_CONVERSATION_EXPIRE_TIMEOUT} minutes. \
Summary anything notewothy, write them down to your memory, \
so that you can easily pick up where you left off when {self.user_id} come back. \
After finish all of this, you can say goodbye to {self.user_id}.")])

        def new_message(self, incoming_message_queue:List[Message]) -> None:
            '''
            basic message handler, can be used either by UserManager.general_handle_new_message()
            or by self.new_message()
            '''
            # self.is_active = True
            # self.last_active_time = datetime.datetime.now()
            self.awaiting_queue.extend(incoming_message_queue) # together we are invincible
            for incoming_message in incoming_message_queue:
                self.session_file.write(f"[{incoming_message.role}|tool_call_id:{incoming_message.tool_calls.id if incoming_message.tool_calls else "None"}]: {incoming_message.content}\n")
            logger.info(f"{self.user_id} Add msg to awq, msg count: {len(self.awaiting_queue)}")
            logger.info(f"{self.user_id} Set last active time to {self.last_active_time}")
        

    users:Dict[str, User]

    def __init__(self) -> UserManager:
        self.users = {}

    def general_handle_new_message(self, user_id:str, incoming_message_queue:List[Message]) -> None:
        '''
        Generic message handler
        '''
        def soul_content() -> str:
            soul_file = open(os.path.join(HOME_DIRECTORY,SOUL_FILE), "r", encoding="utf-8")
            soul_msg:str = soul_file.read()
            soul_file.close()
            return soul_msg
        
        incoming_message_queue = add_timestamp_to_msg_list(incoming_message_queue)

        if user_id not in self.users:
            # new user
            self.users[user_id] = self.User(user_id)
            logger.info(f"{user_id} joined the conversation")
            incoming_message_queue.insert(0, Message(role="system", content=f"{soul_content()}user_id: {user_id}"))
        elif self.users[user_id].is_active == False:
            # user be active again
            self.users[user_id].self_reset_active()
            logger.info(f"{user_id} reset active")
            incoming_message_queue.insert(0, Message(role="system", content=f"{soul_content()}user_id: {user_id}"))
        else: 
            # user still active
            pass
        self.users[user_id].new_message(incoming_message_queue)