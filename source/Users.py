from typing import *
from threading import Thread, Lock
from openai import OpenAI
import os
import json
from time import sleep
from .Utils import *
from .Message import *
from .MCPClient import ToolRegistry
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

def load_mcp_server_cfg(home_dir:str, cfg_file:str) -> Dict[str, Dict[str, Any]]:
    ms_cfg_path_abs = os.path.join(os.getcwd(), home_dir, cfg_file)
    if not os.path.exists(ms_cfg_path_abs):
        default_data = {
            "mcpServers": {}
        }
        with open(ms_cfg_path_abs, "w", encoding="utf-8") as f:
            json.dump(default_data, f, ensure_ascii=False, indent=4)
    with open(ms_cfg_path_abs, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["mcpServers"]

tool_registry = ToolRegistry(load_mcp_server_cfg(HOME_DIRECTORY, "local_mcp_servers.json"),load_mcp_server_cfg(HOME_DIRECTORY, "remote_mcp_servers.json"))
tools = tool_registry.get_tools()
logger.info(f"Registered {len(tools)} tools")
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
        tools = tools,
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
        awq_lock:Lock
        last_active_time:datetime
        is_active:bool
        is_farewell_caused_active:bool
        processing_thread:Optional[Thread]
        session_file:Optional[TextIO]
        def __init__(self, user_id):
            logger.info(f"Creating user {user_id}")
            self.user_id = user_id
            self.awq_lock = Lock()
            if os.path.exists(os.path.join(HOME_DIRECTORY, user_id)) == False:
                os.mkdir(os.path.join(HOME_DIRECTORY, user_id))
                os.mkdir(os.path.join(HOME_DIRECTORY, user_id, "sessions"))
                os.mkdir(os.path.join(HOME_DIRECTORY, user_id, "memories"))
                os.mkdir(os.path.join(HOME_DIRECTORY, user_id, "images"))
            self.processing_thread = Thread(
                target=self.process_loop,
                daemon=True
            )
            self.self_reset_active()
            self.processing_thread.start()


        def self_reset_active(self) -> None:
            self.chat_history = []
            with self.awq_lock:
                self.awaiting_queue = []
            self.last_active_time = datetime.datetime.now()
            self.is_active = True
            self.is_farewell_caused_active = False
            self.session_file = open(
                os.path.join(HOME_DIRECTORY, self.user_id, "sessions", f"{self.user_id}.{self.last_active_time.strftime("%Y-%m-%d.%H-%M-%S")}.txt"),
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
                        
                        with self.awq_lock:
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
                        
                        try:
                            response:Message = get_llm_response(self.chat_history)
                            # logger.debug(f"{self.user_id} 1# response:"); logger.debug(general_output_msg(response))
                            self.process_tool_calls(response)
                        except Exception as e:
                            logger.error(f"{self.user_id} LLM error: {e}")
                            from .WeChatClient import get_wechat_client
                            get_wechat_client().send_text_message(self.user_id, "（出了点问题，请稍后再试）")

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
            from json import dumps as json_dumps
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
                            if len(message.tool_calls.function.arguments) > 70:
                                compressed_args = json_dumps({
                                    "compressed": True,
                                    "original_length": len(message.tool_calls.function.arguments)
                                })
                                self.chat_history[index].tool_calls.function.arguments = compressed_args
                            continue
                    elif message.role == "tool":
                        self.chat_history[index].content = (message.content[0:50] + "[Compressed]" if len(message.content) > 70 else message.content)
                        continue
                    else:
                        continue
                
                logger.debug(f"{self.user_id} chat history (compressed):"); logger.debug(general_output_msg_list(self.chat_history))


        def execute_tools(self, tool_calls: ToolCall) -> Message:
            """Execute the tools called by the LLM."""
            logger.debug(f"{self.user_id} Executing tools...")
            
            args_dict = json.loads(tool_calls.function.arguments)
            tool_response = tool_registry.execute(tool_calls.function.name, args_dict)
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
                if not message.content and self.user_id!="ivybridge":
                    # if not ivybridge, ignore empty assistant message
                    return
                # message.content only can be a string here
                content_to_send = message.content
                segments:List[str] = _parse_segments(content_to_send)

                if self.user_id == "ivybridge":
                    # token usage info
                    segments[0] += f"\n---\nToken Usage: {message.prompt_tokens} in, {message.completion_tokens} out\n"
                    if message.tool_calls:
                        segments[0] += f"Tool Call: {message.tool_calls.function.name}"
                
                
                if len(segments) > 1:
                    wechat_client.send_text_messages(self.user_id, segments)
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
Summary anything notewothy, write them down to your memory about {self.user_id} ({self.user_id}/memories). \
Also update `{self.user_id}/{self.user_id}-last-conversation-pick-up.md `\
so that you can easily pick up where you left off when {self.user_id} come back. \
And, if necessary, update `{self.user_id}/{self.user_id}.md` and `frederica`.\
After finish all of this, you can say goodbye to {self.user_id}.")])

        def new_message(self, incoming_message_queue:List[Message]) -> None:
            '''
            basic message handler, can be used either by UserManager.general_handle_new_message()
            or by self.new_message()
            '''
            with self.awq_lock:
                self.awaiting_queue.extend(incoming_message_queue)
                logger.info(f"{self.user_id} Add msg to awq, msg count: {len(self.awaiting_queue)}")
        

    users:Dict[str, User]

    def __init__(self):
        self.users = {}

    def general_handle_new_message(self, user_id:str, incoming_message_queue:List[Message]) -> None:
        '''
        Generic message handler
        '''
        def get_soul_content() -> str:
            if not os.path.exists(os.path.join(HOME_DIRECTORY, "soul")): # no soul
                # create soul file
                open(os.path.join(HOME_DIRECTORY, "soul"), "w", encoding="utf-8").close()
                return "None"
            else:
                soul_file = open(os.path.join(HOME_DIRECTORY, "soul"), "r", encoding="utf-8")
                soul_msg:str = soul_file.read()
                soul_file.close()
                return soul_msg 
        def get_last_conversation_pick_up(user_id:str) -> str:
            if not os.path.exists(os.path.join(HOME_DIRECTORY, user_id,user_id+"-last-conversation-pick-up.md")): # no pick up
                # create pick up file
                open(os.path.join(HOME_DIRECTORY, user_id, user_id+"-last-conversation-pick-up.md"), "w", encoding="utf-8").close()
                return "None"
            else:
                pick_up_file = open(os.path.join(HOME_DIRECTORY, user_id,user_id+"-last-conversation-pick-up.md"), "r", encoding="utf-8")
                pick_up_msg:str = pick_up_file.read()
                pick_up_file.close()
                return pick_up_msg
        def get_user_memory(user_id:str) -> str:
            if not os.path.exists(os.path.join(HOME_DIRECTORY, user_id, f"{user_id}.md")): # no memory
                # create memory file
                open(os.path.join(HOME_DIRECTORY, user_id, f"{user_id}.md"), "w", encoding="utf-8").close()
                return "None"
            else:
                user_memory_file = open(os.path.join(HOME_DIRECTORY, user_id, f"{user_id}.md"), "r", encoding="utf-8")
                user_memory_msg:str = user_memory_file.read()
                user_memory_file.close()
                return user_memory_msg
        def get_frederica_message() -> str:
            if not os.path.exists(os.path.join(HOME_DIRECTORY, "frederica")): # no frederica
                # create frederica file
                open(os.path.join(HOME_DIRECTORY, "frederica"), "w", encoding="utf-8").close()
                return "None"
            else:
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