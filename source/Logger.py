import logging
import logging.config
import logging.handlers
import queue
import atexit
def setup_logger() -> logging.handlers.QueueListener:
    # 1. 定义日志配置（dictConfig 是最灵活的现代方式）
    LOGGING_CONFIG = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '<%(asctime)s>{%(levelname)s}[%(name)s]: %(message)s',
                'datefmt': '%Y-%m-%d@%H:%M:%S'
            },
        },
        'handlers': {
            'console': {
                'level': 'DEBUG',
                'class': 'logging.StreamHandler',
                'formatter': 'standard'
            },
            'file': {
                'encoding': 'utf-8',
                'level': 'DEBUG',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': 'app.log',
                'maxBytes': 10_485_760,  # 10 MB
                'backupCount': 5,
                'formatter': 'standard'
            }
        },
        'root': {
            'level': 'INFO',
            'handlers': []  # 稍后替换为 QueueHandler
        }
    }

    # 2. 应用配置
    logging.config.dictConfig(LOGGING_CONFIG)

    # 3. 建立队列和监听器
    log_queue = queue.Queue(-1)
    queue_handler = logging.handlers.QueueHandler(log_queue)

    # 获取 root logger 并替换 handlers
    root_logger = logging.getLogger()
    root_logger.handlers = [queue_handler]

    # 从配置中获取已创建的 handler 实例（Python 3.12+）
    console_handler = logging.getHandlerByName('console')
    file_handler = logging.getHandlerByName('file')

    # 启动监听器（独立线程处理实际写入）
    listener = logging.handlers.QueueListener(
        log_queue, console_handler, file_handler
    )
    listener.start()

    # 确保程序退出时停止监听器
    atexit.register(listener.stop)

    return listener

# 4. 使用示例
if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logger.info("应用启动")
    logger.debug("调试信息")
    try:
        1 / 0
    except ZeroDivisionError:
        logger.exception("捕获异常")