from logging import getLogger
from typing import List, Dict, Any, Optional
import json
from time import sleep
import os
from datetime import datetime, timedelta
from threading import Thread
from .Message import Message
from .Utils import get_config_instance
import hashlib
from threading import Lock

logger = getLogger(__name__)
config = get_config_instance()
'''
cron:

id:str
name:str
message:str
target_user:str
target_time:datetime
status: disabled: manual disabled
        pending: waiting to execute
        executing: executing
        executed_disabled: disabled after execution
        failed: failed
repeat: daily | never
created_by:str
created_at:datetime
last_executed_at:datetime
error_message:str
'''


class CronManager:

    def __init__(self, user_manager):
        self.user_manager = user_manager
        global config
        self.cron_file_path = os.path.join(config.home_directory, "cron.json")
        self.crons: List[Dict[str, Any]] = []
        self.running = False
        self.check_loop_thread: Optional[Thread] = None
        self.lock = Lock()
        
        # ensure cron file exists
        if not os.path.exists(self.cron_file_path):
            os.makedirs(os.path.dirname(self.cron_file_path), exist_ok=True)
            default_data = {
                "crons": [],
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            with open(self.cron_file_path, 'w', encoding='utf-8') as f:
                json.dump(default_data, f, indent=2, ensure_ascii=False)
            logger.info(f"create cron file: {self.cron_file_path}")
        
        self.check_loop_thread = Thread(target=self.check_loop, name="CronCheckLoopThread", daemon=True)
        self.reload_crons()

    def start(self):
        self.running = True
        self.check_loop_thread.start()

    def check_loop(self):
        while self.running:
            self.check_and_execute_crons()
            sleep(30)

    def reload_crons(self):
        with self.lock:
            self.reload_crons_unsafe()

    def reload_crons_unsafe(self):
        try:
            with open(self.cron_file_path, 'r', encoding='utf-8') as f:
                self.crons = json.load(f)["crons"]
        except Exception as e:
            logger.error(f"load cron failed: {e}")
            self.crons = []

    def save_crons(self):
        with self.lock:
            self.save_crons_unsafe()

    def save_crons_unsafe(self):
        try:
            with open(self.cron_file_path, 'w', encoding='utf-8') as f:
                json.dump({"crons": self.crons}, f, ensure_ascii=False, indent=1)
        except Exception as e:
            logger.error(f"save cron failed: {e}")
        

    
    def find_crons(self, status_filter:Optional[str] = None, user_filter:Optional[str]=None) -> List[Dict[str, Any]]:
        self.reload_crons()
        if not status_filter and not user_filter:
            return self.crons
        elif status_filter and user_filter:
            return [cron for cron in self.crons if cron["status"] == status_filter and cron["target_user"] == user_filter]
        elif status_filter:
            return [cron for cron in self.crons if cron["status"] == status_filter]
        elif user_filter:
            return [cron for cron in self.crons if cron["target_user"] == user_filter]
    
    def delete_cron(self, name: Optional[str], id: Optional[str]) -> bool:
        with self.lock:
            self.reload_crons_unsafe()
            if name and id:
                for cron in self.crons:
                    if cron["name"] == name and cron["id"] == id:
                        self.crons.remove(cron)
                        self.save_crons_unsafe()
                        return True
            elif name:
                for cron in self.crons:
                    if cron["name"] == name:
                        self.crons.remove(cron)
                        self.save_crons_unsafe()
                        return True
            elif id:
                for cron in self.crons:
                    if cron["id"] == id:
                        self.crons.remove(cron)
                        self.save_crons_unsafe()
                        return True
            return False

    def check_and_execute_crons(self):
        def execute_cron(user_manager, cron:Dict[str, Any]) -> None:
            user_manager.general_handle_new_message(
                user_id=cron["target_user"],
                incoming_message_queue=[
                    Message(content="[CRON MESSAGE]"+cron["message"], role="user")
                ]
            )

        with self.lock:
            self.reload_crons_unsafe()
            current_time = datetime.now()
            
            for cron in self.crons:
                if cron["status"] != "pending":
                    continue

                target_time = datetime.strptime(cron["target_time"], "%Y-%m-%d %H:%M:%S")
                
                if current_time >= target_time:
                    cron["status"]="executing"
                    self.save_crons_unsafe()

                    logger.info(f"Execute cron task: {cron['name']} (ID: {cron['id']})")

                    execute_cron(self.user_manager, cron)
                    
                    cron["last_executed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    if cron["repeat"] == "daily":
                        cron["target_time"] = (target_time + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
                        cron["status"]="pending"
                    else:
                        cron["target_time"] = None
                        cron["status"] = "executed_disabled"
                    self.save_crons_unsafe()
                    continue

    def add_cron(self, 
                 name: str, 
                 target_user: str, 
                 message: str, 
                 target_time: str, 
                 repeat: str = "never", 
                 created_by: str = "system") -> str:
        with self.lock:
            self.reload_crons_unsafe()
            if name in [cron["name"] for cron in self.crons]:
                return "Add cron failed. Cron task name already exists."
            id = hashlib.md5(f"{name}{target_user}{target_time}{message}".encode("utf-8")).hexdigest()[:12]
            self.crons.append({
                "id": id,
                "name": name,
                "target_user": target_user,
                "message": message,
                "target_time": target_time,
                "status": "pending",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "created_by": created_by,
                "last_executed_at": None,
                "error_message": None,
                "repeat": repeat
            })
            self.save_crons_unsafe()
            return f"Add cron success. Task ID: {id}."
    

  