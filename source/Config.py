import os
from typing import *
from dotenv import load_dotenv
import datetime

class Config:
    def __init__(self):
        load_dotenv()
        # llm config
        self.llm_base_url: str = os.getenv("LLM_BASE_URL", "no_llm_base_url")
        self.llm_api_key: str = os.getenv("LLM_API_KEY", "no_llm_api_key")
        self.llm_model: str = os.getenv("LLM_MODEL", "no_llm_model")
        self.llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "8192"))
        self.llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "1.5"))
        self.llm_enable_thinking: bool = bool(os.getenv("LLM_ENABLE_THINKING", "false"))

        # users session config
        self.user_conversation_expire_timeout: datetime.timedelta = datetime.timedelta(minutes=int(os.getenv("USER_CONVERSATION_EXPIRE_TIMEOUT", "15")))

        # home directory
        self.home_directory = os.getenv("HOME_DIRECTORY", "home")

        # wechat config
        self.wechat_work_corpid = os.getenv("WECHAT_WORK_CORPID","no_wechat_work_corpid")
        self.wechat_work_corpsecret = os.getenv("WECHAT_WORK_CORPSECRET","no_wechat_work_corpsecret")
        self.wechat_work_agentid = os.getenv("WECHAT_WORK_AGENTID","no_wechat_work_agentid")
        self.wechat_work_callback_token = os.getenv("WECHAT_WORK_CALLBACK_TOKEN","no_wechat_work_callback_token")
        self.wechat_work_encoding_aes_key = os.getenv("WECHAT_WORK_ENCODING_AES_KEY","no_wechat_work_encoding_aes_key")

        # server config
        self.server_host = os.getenv("SERVER_HOST", "no_server_host")
        self.server_port = int(os.getenv("SERVER_PORT", "no_server_port"))
        self.server_max_connections = int(os.getenv("SERVER_MAX_CONNECTIONS", "no_server_max_connections"))
        self.server_concurrent_requests = int(os.getenv("SERVER_CONCURRENT_REQUESTS", "no_server_concurrent_requests"))
        self.server_requset_timeout = int(os.getenv("SERVER_REQUEST_TIMEOUT", "no_server_request_timeout"))
        self.server_connection_timeout = int(os.getenv("SERVER_CONNECTION_TIMEOUT", "no_server_connection_timeout"))
        self.server_max_request_size = int(os.getenv("SERVER_MAX_REQUEST_SIZE", "no_server_max_request_size"))
        self.server_rate_limit_window = int(os.getenv("SERVER_RATE_LIMIT_WINDOW", "no_server_rate_limit_window"))
        self.server_rate_limit_max_requests = int(os.getenv("SERVER_RATE_LIMIT_MAX_REQUESTS", "no_server_rate_limit_max"))
