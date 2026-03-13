from source.Users import *
from source.WeChatServerV2 import WeChatServer
from source.CronManager import CronManager

logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

from source.Logger import setup_logger
setup_logger()
logger = logging.getLogger(__name__)

def main():
    # 创建UserManager
    um: UserManager = UserManager()
    
    # 创建CronManager并设置全局实例
    cron_manager = CronManager(um, "home/cron.json")
    set_global_cron_manager(cron_manager)
    
    # 启动CronManager检查线程
    cron_manager.start()
    logger.info("CronManager已启动")
    
    # 启动WeChat服务器
    wechat_server = WeChatServer(um)
    wechat_server.start()
    
    # 示例：可以在这里添加初始消息
    # um.new_message(
    #     user_id="ivybridge", 
    #     incoming_message_queue=[
    #         # Message(content="you are a helpful agent", role="system"),
    #         # Message(content="hello, plz test your tools", role="user")
    #     ]
    # )
    
    # 主循环：处理控制台输入
    while True:
        try:
            msg: str = input("> ")
            if msg.lower() == "exit":
                logger.info("收到退出命令，正在关闭...")
                cron_manager.stop()
                break
            elif msg.lower() == "cron list":
                # 快捷命令：列出cron任务
                if cron_manager:
                    tasks = cron_manager.list_cron_tasks()
                    if tasks:
                        print(f"\n📋 当前有 {len(tasks)} 个cron任务：")
                        for task in tasks:
                            print(f"  - {task['name']} (状态: {task['status']}, 目标时间: {task['target_time']})")
                    else:
                        print("📋 当前没有cron任务")
                continue
            elif msg.lower() == "cron cleanup":
                # 快捷命令：清理过期任务
                if cron_manager:
                    cron_manager.cleanup_expired_tasks(days_to_keep=7)
                    print("✅ 已清理7天前的过期cron任务")
                continue
            
            um.general_handle_new_message(
                user_id="ivybridge", 
                incoming_message_queue=[
                    Message(content=msg, role="user")
                ]
            )
        except KeyboardInterrupt:
            logger.info("收到中断信号，正在关闭...")
            cron_manager.stop()
            break
        except Exception as e:
            logger.error(f"处理输入时出错: {e}")
            print(f"错误: {e}")

if __name__ == "__main__":
    main()
