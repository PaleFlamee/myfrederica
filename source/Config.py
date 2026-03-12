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
        self.llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "10240"))
        self.llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "1.5"))

        # users session config
        self.user_conversation_expire_timeout: datetime.timedelta = datetime.timedelta(minutes=int(os.getenv("USER_CONVERSATION_EXPIRE_TIMEOUT", "30")))

        # wechat config
        self.wechat_work_corpid = os.getenv("WECHAT_WORK_CORPID","no_wechat_work_corpid")
        self.wechat_work_corpsecret = os.getenv("WECHAT_WORK_CORPSECRET","no_wechat_work_corpsecret")
        self.wechat_work_agentid = os.getenv("WECHAT_WORK_AGENTID","no_wechat_work_agentid")
        self.wechat_work_callback_token = os.getenv("WECHAT_WORK_CALLBACK_TOKEN","no_wechat_work_callback_token")
        self.wechat_work_encoding_aes_key = os.getenv("WECHAT_WORK_ENCODING_AES_KEY","no_wechat_work_encoding_aes_key")

    def get_llm_config(self) -> dict:
        return {
            "api_key": self.llm_api_key,
            "base_url": self.llm_base_url,
            "model": self.llm_model,
            "max_tokens": self.llm_max_tokens,
            "temperature": self.llm_temperature
        }
    
    def get_user_session_config(self) -> dict:
        return {
            "user_conversation_expire_timeout": self.user_conversation_expire_timeout
        }

    def get_wechat_config(self) -> dict:
        return {
            "corpid": self.wechat_work_corpid,
            "corpsecret": self.wechat_work_corpsecret,
            "agentid": self.wechat_work_agentid,
            "callback_token": self.wechat_work_callback_token,
            "encoding_aes_key": self.wechat_work_encoding_aes_key
        }
