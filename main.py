from source.Users import *
from source.WeChatServerV2 import WeChatServer
from source.CronManagerV2 import CronManager
from tools.cron_manage_tool import set_tool_cron_manager
from tools.read_image_tool import set_tool_user_manager

logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

from source.Logger import setup_logger
setup_logger()
logger = logging.getLogger(__name__)

def main():
    # 创建UserManager
    user_manager: UserManager = UserManager()
    
    # 创建CronManager并设置全局实例
    cron_manager: CronManager = CronManager(user_manager)
    set_tool_cron_manager(cron_manager)
    set_tool_user_manager(user_manager)
    
    # 启动CronManager检查线程
    cron_manager.start()
    logger.info("CronManager已启动")
    
    # 启动WeChat服务器
    wechat_server = WeChatServer(user_manager)
    wechat_server.start()
    
    # 示例：可以在这里添加初始消息
    # um.new_message(
    #     user_id="ivybridge", 
    #     incoming_message_queue=[
    #         # Message(content="you are a helpful agent", role="system"),
    #         # Message(content="hello, plz test your tools", role="user")
    #     ]
    # )
    
    # while True:
    #     msg  = input(">>> ")
    #     user_manager.general_handle_new_message(
    #         user_id="ivybridge", 
    #         incoming_message_queue=[
    #             Message(content=msg, role="user")
    #         ]
    #     )
    while True:
        sleep(1)

if __name__ == "__main__":
    main()
