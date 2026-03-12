from source.Users import *
from source.WeChatServerV2 import WeChatServer

logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

from source.Logger import setup_logger
setup_logger()
logger = logging.getLogger(__name__)

def main():
    um:UserManager=UserManager()
    wechat_server = WeChatServer(um)
    wechat_server.start()
    # um.new_message(
    #     user_id="ivybridge", 
    #     incoming_message_queue=[
    #         # Message(content="you are a helpful agent", role="system"),
    #         # Message(content="hello, plz test your tools", role="user")
    #     ]
    # )
    while True:
        msg:str=input(">")
        um.general_handle_new_message(
            user_id="ivybridge", 
            incoming_message_queue=[
                Message(content=msg, role="user")
            ]
        )

if __name__ == "__main__":
    main()