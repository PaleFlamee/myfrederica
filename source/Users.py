from typing import *
from threading import Thread
from openai import OpenAI
from dotenv import load_dotenv
import os
from time import sleep
from .Utils import *
from .Message import *
import logging
logger = logging.getLogger(__name__)

# get env
config = get_config_instance()
LLM_API_KEY = config.llm_api_key
LLM_BASE_URL = config.llm_base_url
LLM_MODEL = config.llm_model
LLM_MAX_TOKENS = config.llm_max_tokens
LLM_TEMPERATURE = config.llm_temperature
LLM_ENABLE_THINKING = config.llm_enable_thinking
HOME_DIRECTORY = config.home_directory
USER_CONVERSATION_EXPIRE_TIMEOUT = config.user_conversation_expire_timeout

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
from tools.cron_manage_tool import execute_tool_call as execute_cron_manage, TOOL_DEFINITION as CRON_MANAGE_TOOL
from tools.search_markdown_tool import execute_tool_call as execute_search_markdown, TOOL_DEFINITION as SEARCH_MARKDOWN_TOOL
from tools.read_image_tool import execute_tool_call as execute_read_image, TOOL_DEFINITION as READ_IMAGE_TOOL

TOOLS = [
    CRON_MANAGE_TOOL,
    LIST_TOOL,
    READ_TOOL,
    CREATE_TOOL,
    WRITE_TOOL,
    SEARCH_TOOL,
    DELETE_TOOL,
    REPLACE_TOOL,
    DUCKDUCKGO_TOOL,
    FETCH_URL_TOOL,
    EXECUTE_COMMAND_TOOL,
    SEARCH_MARKDOWN_TOOL,
    READ_IMAGE_TOOL
]
TOOL_EXECUTORS = {
    "cron_manage": execute_cron_manage,
    "list_files": execute_list,
    "read_file": execute_read,
    "create_file_or_folder": execute_create,
    "write_file": execute_write,
    "search_files": execute_search,
    "delete_file_or_folder": execute_delete,
    "replace_in_file": execute_replace,
    "duckduckgo_search": execute_duckduckgo,
    "fetch_url": execute_fetch_url,
    "execute_command": execute_command,
    "search_markdown_titles": execute_search_markdown,
    "read_image": execute_read_image
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
        tool_choice = "auto",
        # dashscope only
        extra_body = {"enable_thinking": LLM_ENABLE_THINKING}
    )
    # return response.choices[0].message
    return Message(
        role = response.choices[0].message.role,
        content = response.choices[0].message.content,
        tool_calls = response.choices[0].message.tool_calls[0] if response.choices[0].message.tool_calls else None,
        tool_call_id = response.choices[0].message.tool_calls[0].id if response.choices[0].message.tool_calls else None,
        prompt_tokens = response.usage.prompt_tokens,
        completion_tokens = response.usage.completion_tokens
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
                    if (datetime.datetime.now()-self.last_active_time>=datetime.timedelta(seconds=10)) and (len(self.awaiting_queue) > 0):
                        # if anything in await queue
                        logger.debug(f"{self.user_id} awq msg count:{len(self.awaiting_queue)}")

                        self.merge_messages_awq()
                        logger.debug(f"{self.user_id} merge msgs done if any")

                        self.chat_history.extend(self.awaiting_queue)
                        for message in self.awaiting_queue:
                            self.session_file.write(general_output_msg(message))

                        self.awaiting_queue = []
                        logger.debug(f"{self.user_id} extended chat history & awq cleared")
                        # logger.debug(f"{self.user_id} chat history:"); logger.debug(general_output_msg_list(self.chat_history))
                        
                        # TODO: add exception handling
                        response:Message = get_llm_response(self.chat_history)
                        # logger.debug(f"{self.user_id} 1# response:"); logger.debug(general_output_msg(response))

                        self.process_tool_calls(response)

                        if self.is_farewell_caused_active:
                            self.session_file.close()
                            logger.info(f"{self.user_id} session file closed")
                            self.is_farewell_caused_active = False # execute only once 
                    else:
                        # no message in awqueue or waiting msg_merge_timeout
                        logger.debug(f"{self.user_id} no msg in awq or awting merge timeout")
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
        
        def merge_messages_awq(self): # merge (non-multimodal and user) msgs only
            # merged_content_str:str=""
            # for message in self.awaiting_queue:
            #     if message.role != "user":
            #         pass
            #     if isinstance(message.content, list):# multimodal
            #         # 
            pass

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
                # self.session_file.write(f"[{current_assistant_message.role}|tcid:{current_assistant_message.tool_calls.id[-5:-1]}]: {current_assistant_message.content}\n")
                self.session_file.write(general_output_msg(current_assistant_message))
                logger.debug(f"{self.user_id} append ast msg to chat history: ");# logger.debug(general_output_msg(current_assistant_message))
                tool_message = self.execute_tools(current_assistant_message.tool_calls)
                display_message("Tool Response", f"{self.user_id} {tool_message.content}")
                self.chat_history.append(tool_message) # append & write always together
                # self.session_file.write(f"[{tool_message.role}|tcid:{tool_message.tool_call_id[-5:-1]}]: {tool_message.content}\n")
                self.session_file.write(general_output_msg(tool_message))
                logger.debug(f"{self.user_id} append tool msg to chat history: ");# logger.debug(general_output_msg(tool_message))
                current_assistant_message = get_llm_response(self.chat_history)
                # logger.debug(f"{self.user_id} refresh ast msg:"); logger.debug(general_output_msg(current_assistant_message))
                self.process_tool_calls(current_assistant_message)
            else:
                logger.debug(f"{self.user_id} no tool calls")
                display_message("Assistant", f"{self.user_id} {current_assistant_message.content}")
                self.chat_history.append(current_assistant_message) # append & write, best friends together
                # self.session_file.write(f"[{current_assistant_message.role}|tcid:{current_assistant_message.tool_calls.id[-5:-1] if current_assistant_message.tool_calls else "None"}]: {current_assistant_message.content}\n")
                self.session_file.write(general_output_msg(current_assistant_message))
                logger.debug(f"{self.user_id} append ast msg to chat history: ");# logger.debug(general_output_msg(current_assistant_message))

                # tool-calls ends here, compress all tool-calls & responses, to compress chat history
                for index, message in enumerate(self.chat_history):
                    if message.role == "assistant":
                        if message.tool_calls: # if ast msg & tc exists
                            self.chat_history[index].tool_calls.function.arguments = f"{{\"Compressed arguments\":\"{message.tool_calls.function.arguments[0:30]}\"}}" if len(message.tool_calls.function.arguments) > 57 else message.tool_calls.function.arguments
                            continue
                    elif message.role == "tool":
                        self.chat_history[index].content = (message.content[0:30] + "[Compressed]" if len(message.content) > 42 else message.content)
                        continue
                    else:
                        continue
                
                logger.debug(f"{self.user_id} chat history (compressed):"); logger.debug(general_output_msg_list(self.chat_history))


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
            def _parse_segments(content: str) -> List[str]:
                """
                解析消息内容，根据 [SEGMENT] 标记分割成多个段
                """
                if not content:
                    return [""]
                
                # 使用 [SEGMENT] 作为分割标记
                segments = content.split("[SEGMENT]")
                
                return segments
            
            from .WeChatClient import get_wechat_client
            wechat_client=get_wechat_client()
            if message.role == "assistant":
                # message.content only can be a string here
                content_to_send = message.content
                segments:List[str] = _parse_segments(content_to_send)
                # token usage info
                segments[0] += f"\n---\nToken Usage: {message.prompt_tokens} in, {message.completion_tokens} out\n"
                if message.tool_calls:
                    segments[0] += f"Tool Call: {message.tool_calls.function.name}"
                if len(segments) > 1:
                    wechat_client.send_messages(self.user_id, segments)
                else:
                    wechat_client.send_text_message(self.user_id, segments[0])
            elif message.role == "tool":
                pass
            elif message.role == "user" or message.role == "system": # should never happen
                pass
            else: # ???
                raise ValueError(f"Invalid message role: {message.role}")
                

        def farewell(self) -> None:
            self.new_message([Message(role="user", content=f"\
[SYSTEM MESSAGE]\
{self.user_id} has been in silence for {USER_CONVERSATION_EXPIRE_TIMEOUT}. \
Summary anything notewothy, write them down to your memory. \
Also update `users/{self.user_id}-last-conversation-pick-up.md `\
so that you can easily pick up where you left off when {self.user_id} come back. \
And, if necessary, update `users/{self.user_id}.md` and `frederica`.\
After finish all of this, you can say goodbye to {self.user_id}.")])

        def new_message(self, incoming_message_queue:List[Message]) -> None:
            '''
            basic message handler, can be used either by UserManager.general_handle_new_message()
            or by self.new_message()
            '''
            # self.is_active = True
            # self.last_active_time = datetime.datetime.now()
            self.awaiting_queue.extend(incoming_message_queue) # together we are invincible
            # for incoming_message in incoming_message_queue:
            #     self.session_file.write(general_output_msg(incoming_message))
            logger.info(f"{self.user_id} Add msg to awq, msg count: {len(self.awaiting_queue)}")
            # logger.info(f"{self.user_id} Set last active time to {self.last_active_time}")
        

    users:Dict[str, User]

    def __init__(self):
        self.users = {}

    def general_handle_new_message(self, user_id:str, incoming_message_queue:List[Message]) -> None:
        '''
        Generic message handler
        '''
        def get_soul_content() -> str:
            soul_file = open(os.path.join(HOME_DIRECTORY, "soul"), "r", encoding="utf-8")
            soul_msg:str = soul_file.read()
            soul_file.close()
            return soul_msg
        def get_last_conversation_pick_up(user_id:str) -> str:
            if not os.path.exists(os.path.join(HOME_DIRECTORY, "users",user_id+"-last-conversation-pick-up.md")): # no pick up
                # create pick up file
                open(os.path.join(HOME_DIRECTORY, "users",user_id+"-last-conversation-pick-up.md"), "w", encoding="utf-8").close()
                return "None"
            else:
                pick_up_file = open(os.path.join(HOME_DIRECTORY, "users",user_id+"-last-conversation-pick-up.md"), "r", encoding="utf-8")
                pick_up_msg:str = pick_up_file.read()
                pick_up_file.close()
                return pick_up_msg
        def get_user_memory(user_id:str) -> str:
            if not os.path.exists(os.path.join(HOME_DIRECTORY, "users", f"{user_id}.md")): # no memory
                # create memory file
                open(os.path.join(HOME_DIRECTORY, "users", f"{user_id}.md"), "w", encoding="utf-8").close()
                return "None"
            else:
                user_memory_file = open(os.path.join(HOME_DIRECTORY, "users", f"{user_id}.md"), "r", encoding="utf-8")
                user_memory_msg:str = user_memory_file.read()
                user_memory_file.close()
                return user_memory_msg
        def get_frederica_message() -> str:
            frederica_message_file = open(os.path.join(HOME_DIRECTORY, "frederica"), "r", encoding="utf-8")
            frederica_message_content:str = frederica_message_file.read()
            frederica_message_file.close()
            return frederica_message_content
        
        incoming_message_queue = add_timestamp_to_msg_list(incoming_message_queue)

        if user_id not in self.users:
            # new user
            self.users[user_id] = self.User(user_id)
            logger.info(f"{user_id} joined the conversation")
            incoming_message_queue.insert(0, Message(role="system", content=f"\
<soul>{get_soul_content()}</soul>\n\
<user_id>{user_id}</user_id>\n\
<user_memory>{get_user_memory(user_id)}</user_memory>\n\
<last_conversation_pick_up>{get_last_conversation_pick_up(user_id)}</last_conversation_pick_up>\n\
<frederica_message>{get_frederica_message()}</frederica_message>\n"))
        elif self.users[user_id].is_active == False:
            # user be active again
            self.users[user_id].self_reset_active()
            logger.info(f"{user_id} reset active")
            incoming_message_queue.insert(0, Message(role="system", content=f"\
<soul>{get_soul_content()}</soul>\n\
<user_id>{user_id}</user_id>\n\
<user_memory>{get_user_memory(user_id)}</user_memory>\n\
<last_conversation_pick_up>{get_last_conversation_pick_up(user_id)}</last_conversation_pick_up>\n\
<frederica_message>{get_frederica_message()}</frederica_message>\n"))
        else: 
            # user still active
            self.users[user_id].last_active_time = datetime.datetime.now()
            pass
        self.users[user_id].new_message(incoming_message_queue)