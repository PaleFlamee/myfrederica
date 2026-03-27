#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
APIServer.py - 为主程序提供HTTP API接口
"""

import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from typing import Dict, Any, Optional
from urllib.parse import urlparse, parse_qs
import time
import datetime

logger = logging.getLogger(__name__)

class APIRequestHandler(BaseHTTPRequestHandler):
    """HTTP请求处理器"""
    
    def __init__(self, *args, user_manager=None, cron_manager=None, **kwargs):
        self.user_manager = user_manager
        self.cron_manager = cron_manager
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """处理GET请求"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        # API路由
        if path == "/api/status":
            self._handle_status()
        elif path == "/api/users":
            self._handle_get_users()
        elif path == "/api/cron":
            self._handle_get_cron()
        elif path.startswith("/api/user/"):
            user_id = path.split("/")[-1]
            self._handle_get_user(user_id)
        else:
            self._send_error(404, "Not Found")
    
    def do_POST(self):
        """处理POST请求"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        # 读取请求体
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        data = json.loads(body) if body else {}
        
        # API路由
        if path == "/api/message":
            self._handle_send_message(data)
        elif path == "/api/cron":
            self._handle_manage_cron(data)
        elif path == "/api/user/restart":
            self._handle_restart_user(data)
        else:
            self._send_error(404, "Not Found")
    
    def _handle_status(self):
        """处理状态查询"""
        try:
            status = self._collect_system_status()
            self._send_json_response(200, status)
        except Exception as e:
            logger.error(f"Error collecting status: {e}")
            self._send_error(500, f"Internal Server Error: {str(e)}")
    
    def _handle_get_users(self):
        """获取用户列表"""
        try:
            users_info = self._collect_users_info()
            self._send_json_response(200, users_info)
        except Exception as e:
            logger.error(f"Error getting users: {e}")
            self._send_error(500, f"Internal Server Error: {str(e)}")
    
    def _handle_get_user(self, user_id):
        """获取特定用户信息"""
        try:
            user_info = self._collect_user_info(user_id)
            if user_info:
                self._send_json_response(200, user_info)
            else:
                self._send_error(404, f"User {user_id} not found")
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            self._send_error(500, f"Internal Server Error: {str(e)}")
    
    def _handle_get_cron(self):
        """获取定时任务列表"""
        try:
            if self.cron_manager:
                tasks = self.cron_manager.find_crons()
                self._send_json_response(200, {"tasks": tasks})
            else:
                self._send_error(500, "Cron manager not available")
        except Exception as e:
            logger.error(f"Error getting cron tasks: {e}")
            self._send_error(500, f"Internal Server Error: {str(e)}")
    
    def _handle_send_message(self, data):
        """发送消息给用户"""
        try:
            user_id = data.get("user_id")
            message = data.get("message")
            
            if not user_id or not message:
                self._send_error(400, "Missing user_id or message")
                return
            
            # 使用UserManager发送消息
            from source.Message import Message
            self.user_manager.general_handle_new_message(
                user_id=user_id,
                incoming_message_queue=[
                    Message(content=f"[MANUAL MESSAGE] {message}", role="user")
                ]
            )
            
            self._send_json_response(200, {
                "success": True,
                "message": f"Message sent to {user_id}"
            })
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self._send_error(500, f"Internal Server Error: {str(e)}")
    
    def _handle_manage_cron(self, data):
        """管理定时任务"""
        try:
            action = data.get("action")
            
            if action == "list":
                tasks = self.cron_manager.find_crons()
                self._send_json_response(200, {"tasks": tasks})
            elif action == "add":
                # 添加定时任务
                result = self.cron_manager.add_cron(
                    name=data.get("name"),
                    target_user=data.get("target_user"),
                    message=data.get("message"),
                    target_time=data.get("target_time"),
                    repeat=data.get("repeat", "never"),
                    created_by="api"
                )
                self._send_json_response(200, {"result": result})
            elif action == "delete":
                # 删除定时任务
                success = self.cron_manager.delete_cron(
                    name=data.get("name"),
                    id=data.get("id")
                )
                self._send_json_response(200, {"success": success})
            else:
                self._send_error(400, f"Unknown action: {action}")
        except Exception as e:
            logger.error(f"Error managing cron: {e}")
            self._send_error(500, f"Internal Server Error: {str(e)}")
    
    def _handle_restart_user(self, data):
        """重启用户会话"""
        try:
            user_id = data.get("user_id")
            if not user_id:
                self._send_error(400, "Missing user_id")
                return
            
            if user_id in self.user_manager.users:
                # 重置用户活跃状态
                self.user_manager.users[user_id].self_reset_active()
                self._send_json_response(200, {
                    "success": True,
                    "message": f"User {user_id} restarted"
                })
            else:
                self._send_error(404, f"User {user_id} not found")
        except Exception as e:
            logger.error(f"Error restarting user: {e}")
            self._send_error(500, f"Internal Server Error: {str(e)}")
    
    def _collect_system_status(self) -> Dict[str, Any]:
        """收集系统状态信息"""
        try:
            import psutil
        except ImportError:
            psutil = None
        
        # 用户状态
        active_users = 0
        total_users = len(self.user_manager.users) if self.user_manager.users else 0
        if self.user_manager.users:
            active_users = sum(1 for user in self.user_manager.users.values() 
                             if hasattr(user, 'is_active') and user.is_active)
        
        # 定时任务状态
        cron_tasks = self.cron_manager.find_crons() if self.cron_manager else []
        pending_crons = len([t for t in cron_tasks if t.get("status") == "pending"])
        
        status_data = {
            "timestamp": datetime.datetime.now().isoformat(),
            "users": {
                "total": total_users,
                "active": active_users,
                "inactive": total_users - active_users
            },
            "cron": {
                "total_tasks": len(cron_tasks),
                "pending_tasks": pending_crons,
                "executed_tasks": len([t for t in cron_tasks if t.get("status") == "executed_disabled"])
            }
        }
        
        # 如果psutil可用，添加系统资源信息
        if psutil:
            try:
                process = psutil.Process()
                memory_info = process.memory_info()
                
                status_data["system"] = {
                    "uptime": time.time() - psutil.boot_time(),
                    "cpu_percent": psutil.cpu_percent(interval=0.1),
                    "memory_used_mb": memory_info.rss / 1024 / 1024,
                    "memory_percent": process.memory_percent()
                }
                
                status_data["process"] = {
                    "threads": process.num_threads(),
                    "open_files": len(process.open_files()) if hasattr(process, 'open_files') else 0
                }
            except Exception as e:
                logger.warning(f"Failed to collect system metrics: {e}")
                status_data["system"] = {"error": str(e)}
                status_data["process"] = {"error": str(e)}
        
        return status_data
    
    def _collect_users_info(self) -> Dict[str, Any]:
        """收集用户信息"""
        users_info = []
        
        if self.user_manager and hasattr(self.user_manager, 'users'):
            for user_id, user in self.user_manager.users.items():
                user_data = {
                    "user_id": user_id,
                    "is_active": getattr(user, 'is_active', False),
                    "last_active_time": getattr(user, 'last_active_time', None),
                    "awaiting_queue_size": len(getattr(user, 'awaiting_queue', [])) if hasattr(user, 'awaiting_queue') else 0,
                    "chat_history_length": len(getattr(user, 'chat_history', [])) if hasattr(user, 'chat_history') else 0
                }
                
                # 转换datetime为字符串
                if user_data["last_active_time"] and hasattr(user_data["last_active_time"], 'isoformat'):
                    user_data["last_active_time"] = user_data["last_active_time"].isoformat()
                
                users_info.append(user_data)
        
        return {"users": users_info, "count": len(users_info)}
    
    def _collect_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """收集特定用户信息"""
        if not self.user_manager or user_id not in self.user_manager.users:
            return None
        
        user = self.user_manager.users[user_id]
        user_info = {
            "user_id": user_id,
            "is_active": getattr(user, 'is_active', False),
            "is_farewell_caused_active": getattr(user, 'is_farewell_caused_active', False),
            "awaiting_queue_size": len(getattr(user, 'awaiting_queue', [])),
            "chat_history_length": len(getattr(user, 'chat_history', [])),
        }
        
        # 处理最后活跃时间
        last_active = getattr(user, 'last_active_time', None)
        if last_active:
            if hasattr(last_active, 'isoformat'):
                user_info["last_active_time"] = last_active.isoformat()
            else:
                user_info["last_active_time"] = str(last_active)
        
        # 检查处理线程状态
        processing_thread = getattr(user, 'processing_thread', None)
        if processing_thread:
            user_info["processing_thread_alive"] = getattr(processing_thread, 'is_alive', lambda: False)()
        
        return user_info
    
    def _send_json_response(self, status_code: int, data: Dict[str, Any]):
        """发送JSON响应"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'))
    
    def _send_error(self, status_code: int, message: str):
        """发送错误响应"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        error_response = {
            "error": True,
            "code": status_code,
            "message": message
        }
        self.wfile.write(json.dumps(error_response, ensure_ascii=False).encode('utf-8'))
    
    def log_message(self, format, *args):
        """自定义日志格式"""
        logger.info(f"HTTP {self.address_string()} - {format % args}")

class APIServer:
    """API服务器类"""
    
    def __init__(self, host: str = "localhost", port: int = 8080):
        self.host = host
        self.port = port
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[Thread] = None
        self.user_manager = None
        self.cron_manager = None
    
    def set_managers(self, user_manager, cron_manager):
        """设置管理器实例"""
        self.user_manager = user_manager
        self.cron_manager = cron_manager
    
    def start(self):
        """启动API服务器"""
        def handler_factory(*args, **kwargs):
            return APIRequestHandler(
                *args, 
                user_manager=self.user_manager,
                cron_manager=self.cron_manager,
                **kwargs
            )
        
        try:
            self.server = HTTPServer((self.host, self.port), handler_factory)
            self.thread = Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            logger.info(f"API server started on http://{self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to start API server: {e}")
            return False
    
    def stop(self):
        """停止API服务器"""
        if self.server:
            self.server.shutdown()
            logger.info("API server stopped")