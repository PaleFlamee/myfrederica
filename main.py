import logging
from source.Logger import setup_logger
setup_logger()
logger = logging.getLogger(__name__)

from source.Users import *
from source.WeChatServerV2 import WeChatServer, WeChatBotServer
from source.CronManagerV2 import CronManager
from tools.cron_manage_tool import set_tool_cron_manager
# from tools.read_image_tool import set_tool_user_manager
from APIServer import APIServer

# logging.getLogger("openai").setLevel(logging.WARNING)
# logging.getLogger("httpx").setLevel(logging.WARNING)
# logging.getLogger("httpcore").setLevel(logging.WARNING)
# logging.getLogger("urllib3").setLevel(logging.WARNING)

def main():
    user_manager: UserManager = UserManager()
    cron_manager: CronManager = CronManager(user_manager)

    set_tool_cron_manager(cron_manager)
    cron_manager.start()

    bot_server:WeChatBotServer = WeChatBotServer(user_manager)
    wechat_server: WeChatServer = WeChatServer(user_manager, bot_server)
    wechat_server.start()
    
    # 启动API服务器
    api_server = APIServer(host="localhost", port=20721)
    api_server.set_managers(user_manager, cron_manager)
    if api_server.start():
        logger.info("API服务器已启动，可通过 http://localhost:20721 访问")
        logger.info("使用 monitor_cli.py 工具进行监控和管理")
    else:
        logger.error("API服务器启动失败")
    
    # um.new_message(
    #     user_id="ivybridge", 
    #     incoming_message_queue=[
    #         # Message(content="you are a helpful agent", role="system"),
    #         # Message(content="hello, plz test your tools", role="user")
    #     ]
    # )
    
    # if linux, just run forever, and the response will be sent to wechat
    if os.name != "nt":
        while True:
            sleep(1)
    # if windows, you can input message in console, and the response will be printed in console
    while True:
        msg  = input(">>> ")
        user_manager.general_handle_new_message(
            user_id="ivybridge", 
            incoming_message_queue=[
                Message(content=msg, role="user")
            ]
        )

if __name__ == "__main__":
    main()
