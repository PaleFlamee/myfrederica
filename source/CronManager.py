from typing import List, Dict, Any, Optional
import json
import hashlib
import time
import os
from datetime import datetime
from threading import Thread
import logging
from .Message import Message

logger = logging.getLogger(__name__)

class CronManager:
    """
    Cron任务管理器
    负责管理定时任务，检查并执行到期的cron任务
    """
    
    def __init__(self, user_manager, cron_file_path: str = "home/cron.json"):
        """
        初始化CronManager
        
        Args:
            user_manager: UserManager实例，用于向用户发送消息
            cron_file_path: cron任务存储文件路径
        """
        self.user_manager = user_manager
        self.cron_file_path = cron_file_path
        self.cron_tasks: List[Dict[str, Any]] = []
        self.running = False
        self.thread: Optional[Thread] = None
        
        # 确保cron文件存在
        self._ensure_cron_file()
        
        # 加载现有cron任务
        self.load_crons()
        
        logger.info(f"CronManager初始化完成，加载了 {len(self.cron_tasks)} 个cron任务")
    
    def _ensure_cron_file(self):
        """确保cron文件存在，如果不存在则创建"""
        if not os.path.exists(self.cron_file_path):
            os.makedirs(os.path.dirname(self.cron_file_path), exist_ok=True)
            default_data = {
                "cron_tasks": [],
                "version": "1.0",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            with open(self.cron_file_path, 'w', encoding='utf-8') as f:
                json.dump(default_data, f, indent=2, ensure_ascii=False)
            logger.info(f"创建cron文件: {self.cron_file_path}")
    
    @staticmethod
    def generate_cron_id(name: str, target_user: str, target_time: str, message: str) -> str:
        """
        生成cron任务ID（基于名称和其他参数的哈希）
        
        Args:
            name: 任务名称
            target_user: 目标用户ID
            target_time: 目标时间
            message: 消息内容
            
        Returns:
            12位哈希ID
        """
        data = f"{name}:{target_user}:{target_time}:{message}"
        return hashlib.md5(data.encode()).hexdigest()[:12]
    
    def load_crons(self):
        """从JSON文件加载cron任务"""
        try:
            with open(self.cron_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.cron_tasks = data.get("cron_tasks", [])
                logger.debug(f"从 {self.cron_file_path} 加载了 {len(self.cron_tasks)} 个cron任务")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"加载cron文件失败: {e}")
            self.cron_tasks = []
    
    def save_crons(self):
        """保存cron任务到JSON文件"""
        try:
            data = {
                "cron_tasks": self.cron_tasks,
                "version": "1.0",
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            with open(self.cron_file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.debug(f"保存了 {len(self.cron_tasks)} 个cron任务到 {self.cron_file_path}")
        except Exception as e:
            logger.error(f"保存cron文件失败: {e}")
    
    def add_cron_task(self, name: str, target_user: str, message: str, target_time: str, created_by: str = "system") -> Dict[str, Any]:
        """
        添加新的cron任务
        
        Args:
            name: 任务名称
            target_user: 目标用户ID
            message: 消息内容
            target_time: 执行时间（格式：YYYY-MM-DD HH:MM:SS）
            created_by: 创建者
            
        Returns:
            创建的cron任务信息
        """
        # 验证时间格式
        try:
            datetime.strptime(target_time, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            raise ValueError(f"时间格式错误，应为 YYYY-MM-DD HH:MM:SS，得到: {target_time}")
        
        # 检查是否已存在同名任务
        for task in self.cron_tasks:
            if task["name"] == name:
                raise ValueError(f"已存在同名cron任务: {name}")
        
        # 生成任务ID
        task_id = self.generate_cron_id(name, target_user, target_time, message)
        
        # 创建任务对象
        cron_task = {
            "id": task_id,
            "name": name,
            "target_user": target_user,
            "message": message,
            "target_time": target_time,
            "status": "pending",  # pending, executing, executed, error
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "created_by": created_by,
            "executed_at": None,
            "error_message": None
        }
        
        # 添加到列表并保存
        self.cron_tasks.append(cron_task)
        self.save_crons()
        
        logger.info(f"添加cron任务: {name} (ID: {task_id})，计划执行时间: {target_time}")
        return cron_task
    
    def delete_cron_task(self, name: str) -> bool:
        """
        删除cron任务
        
        Args:
            name: 任务名称
            
        Returns:
            是否成功删除
        """
        initial_count = len(self.cron_tasks)
        self.cron_tasks = [task for task in self.cron_tasks if task["name"] != name]
        
        if len(self.cron_tasks) < initial_count:
            self.save_crons()
            logger.info(f"删除cron任务: {name}")
            return True
        else:
            logger.warning(f"未找到cron任务: {name}")
            return False
    
    def list_cron_tasks(self, filter_status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        列出cron任务
        
        Args:
            filter_status: 可选的状态过滤器
            
        Returns:
            cron任务列表
        """
        if filter_status:
            return [task for task in self.cron_tasks if task["status"] == filter_status]
        return self.cron_tasks.copy()
    
    def get_cron_task(self, name: str) -> Optional[Dict[str, Any]]:
        """
        获取指定名称的cron任务
        
        Args:
            name: 任务名称
            
        Returns:
            cron任务信息或None
        """
        for task in self.cron_tasks:
            if task["name"] == name:
                return task
        return None
    
    def _check_and_execute_crons(self):
        """检查并执行到期的cron任务"""
        current_time = datetime.now()
        
        for task in self.cron_tasks:
            if task["status"] != "pending":
                continue
            
            try:
                target_time = datetime.strptime(task["target_time"], "%Y-%m-%d %H:%M:%S")
                
                # 检查是否到期
                if current_time >= target_time:
                    logger.info(f"执行cron任务: {task['name']} (ID: {task['id']})")
                    self._execute_cron_task(task)
                    
            except Exception as e:
                logger.error(f"检查cron任务 {task['name']} 时出错: {e}")
                task["status"] = "error"
                task["error_message"] = str(e)
                self.save_crons()
    
    def _execute_cron_task(self, task: Dict[str, Any]):
        """
        执行单个cron任务
        
        Args:
            task: cron任务信息
        """
        try:
            # 标记为执行中
            task["status"] = "executing"
            self.save_crons()
            
            # # 检查用户是否存在
            # if task["target_user"] not in self.user_manager.users:
            #     raise ValueError(f"用户不存在: {task['target_user']}")
            
            # # 创建消息并添加到用户的等待队列
            # message = Message(
            #     role="user",
            #     content=task["message"]
            # )
            
            # # 使用UserManager的new_message方法
            # user = self.user_manager.users[task["target_user"]]
            # user.new_message([message])
            self.user_manager.general_handle_new_message(task["target_user"], [Message(content=f"[CRON MESSAGE]{task["message"]}", role="user")])
            
            # 标记为已执行
            task["status"] = "executed"
            task["executed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.save_crons()
            
            logger.info(f"成功执行cron任务: {task['name']}，已发送消息给用户 {task['target_user']}")
            
        except Exception as e:
            logger.error(f"执行cron任务 {task['name']} 失败: {e}")
            task["status"] = "error"
            task["error_message"] = str(e)
            self.save_crons()
    
    def _check_loop(self):
        """检查循环（每分钟检查一次）"""
        logger.info("CronManager检查线程启动")
        
        while self.running:
            try:
                self._check_and_execute_crons()
            except Exception as e:
                logger.error(f"CronManager检查循环出错: {e}")
            
            # 每1/2分钟检查一次
            time.sleep(30)
    
    def start(self):
        """启动CronManager检查线程"""
        if self.running:
            logger.warning("CronManager已经在运行中")
            return
        
        self.running = True
        self.thread = Thread(target=self._check_loop, daemon=True)
        self.thread.start()
        logger.info("CronManager已启动")
    
    def stop(self):
        """停止CronManager检查线程"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("CronManager已停止")
    
    def cleanup_expired_tasks(self, days_to_keep: int = 30):
        """
        清理过期的已执行任务
        
        Args:
            days_to_keep: 保留天数
        """
        from datetime import timedelta
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(days=days_to_keep)
        
        initial_count = len(self.cron_tasks)
        self.cron_tasks = [
            task for task in self.cron_tasks
            if not (
                task["status"] == "executed" and 
                task.get("executed_at") and
                datetime.strptime(task["executed_at"], "%Y-%m-%d %H:%M:%S") < cutoff_time
            )
        ]
        
        removed_count = initial_count - len(self.cron_tasks)
        if removed_count > 0:
            self.save_crons()
            logger.info(f"清理了 {removed_count} 个过期cron任务")
    
    def __del__(self):
        """析构函数，确保线程停止"""
        self.stop()