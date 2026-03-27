#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
monitor_cli.py - 监控和管理主程序的命令行工具
"""

import argparse
import json
import sys
import requests
from typing import Dict, Any, List
import datetime

class MonitorCLI:
    """监控命令行工具"""
    
    def __init__(self, base_url: str = "http://localhost:20721"):
        self.base_url = base_url
    
    def get_status(self, json_output: bool = False):
        """获取系统状态"""
        try:
            response = requests.get(f"{self.base_url}/api/status", timeout=5)
            response.raise_for_status()
            data = response.json()
            
            if json_output:
                print(json.dumps(data, indent=2, ensure_ascii=False))
                return
            
            print("=== 系统状态 ===")
            timestamp = data.get('timestamp', 'N/A')
            if timestamp != 'N/A':
                try:
                    dt = datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    pass
            print(f"时间: {timestamp}")
            
            # 系统信息
            system = data.get('system', {})
            if system and 'error' not in system:
                print(f"\n系统资源:")
                print(f"  CPU使用率: {system.get('cpu_percent', 'N/A')}%")
                print(f"  内存使用: {system.get('memory_used_mb', 'N/A'):.2f} MB ({system.get('memory_percent', 'N/A'):.1f}%)")
                print(f"  运行时间: {system.get('uptime', 'N/A'):.0f} 秒")
            elif system and 'error' in system:
                print(f"\n系统资源: 无法获取 ({system.get('error')})")
            
            # 用户信息
            users = data.get('users', {})
            print(f"\n用户状态:")
            print(f"  总用户数: {users.get('total', 0)}")
            print(f"  活跃用户: {users.get('active', 0)}")
            print(f"  非活跃用户: {users.get('inactive', 0)}")
            
            # 定时任务
            cron = data.get('cron', {})
            print(f"\n定时任务:")
            print(f"  总任务数: {cron.get('total_tasks', 0)}")
            print(f"  等待执行: {cron.get('pending_tasks', 0)}")
            print(f"  已执行: {cron.get('executed_tasks', 0)}")
            
            # 进程信息
            process = data.get('process', {})
            if process and 'error' not in process:
                print(f"\n进程信息:")
                print(f"  线程数: {process.get('threads', 'N/A')}")
                print(f"  打开文件数: {process.get('open_files', 'N/A')}")
                
        except requests.exceptions.ConnectionError:
            print("错误: 无法连接到API服务器，请确保主程序正在运行")
            sys.exit(1)
        except requests.exceptions.Timeout:
            print("错误: 连接超时，请检查API服务器是否正常运行")
            sys.exit(1)
        except Exception as e:
            print(f"错误: {e}")
            sys.exit(1)
    
    def list_users(self, detailed: bool = False, json_output: bool = False):
        """列出用户"""
        try:
            response = requests.get(f"{self.base_url}/api/users", timeout=5)
            response.raise_for_status()
            data = response.json()
            
            if json_output:
                print(json.dumps(data, indent=2, ensure_ascii=False))
                return
            
            users = data.get('users', [])
            print(f"=== 用户列表 (共{len(users)}个) ===")
            
            for user in users:
                print(f"\n用户ID: {user.get('user_id')}")
                status = "活跃" if user.get('is_active') else "非活跃"
                print(f"  状态: {status}")
                
                last_active = user.get('last_active_time', 'N/A')
                if last_active != 'N/A':
                    try:
                        dt = datetime.datetime.fromisoformat(last_active.replace('Z', '+00:00'))
                        last_active = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        pass
                print(f"  最后活跃: {last_active}")
                
                print(f"  等待队列: {user.get('awaiting_queue_size', 0)} 条消息")
                print(f"  聊天历史: {user.get('chat_history_length', 0)} 条记录")
                
        except requests.exceptions.ConnectionError:
            print("错误: 无法连接到API服务器")
            sys.exit(1)
        except Exception as e:
            print(f"错误: {e}")
            sys.exit(1)
    
    def get_user(self, user_id: str, json_output: bool = False):
        """获取特定用户信息"""
        try:
            response = requests.get(f"{self.base_url}/api/user/{user_id}", timeout=5)
            
            if response.status_code == 404:
                print(f"错误: 用户 '{user_id}' 不存在")
                sys.exit(1)
            
            response.raise_for_status()
            data = response.json()
            
            if json_output:
                print(json.dumps(data, indent=2, ensure_ascii=False))
                return
            
            print(f"=== 用户信息: {user_id} ===")
            print(f"状态: {'活跃' if data.get('is_active') else '非活跃'}")
            print(f"告别触发活跃: {'是' if data.get('is_farewell_caused_active') else '否'}")
            
            last_active = data.get('last_active_time', 'N/A')
            if last_active != 'N/A':
                try:
                    dt = datetime.datetime.fromisoformat(last_active.replace('Z', '+00:00'))
                    last_active = dt.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    pass
            print(f"最后活跃: {last_active}")
            
            print(f"等待队列大小: {data.get('awaiting_queue_size', 0)}")
            print(f"聊天历史长度: {data.get('chat_history_length', 0)}")
            
            if 'processing_thread_alive' in data:
                print(f"处理线程状态: {'运行中' if data['processing_thread_alive'] else '已停止'}")
                
        except requests.exceptions.ConnectionError:
            print("错误: 无法连接到API服务器")
            sys.exit(1)
        except Exception as e:
            print(f"错误: {e}")
            sys.exit(1)
    
    def send_message(self, user_id: str, message: str):
        """发送消息给用户"""
        try:
            payload = {
                "user_id": user_id,
                "message": message
            }
            
            response = requests.post(
                f"{self.base_url}/api/message",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("success"):
                print(f"✓ 消息已发送给用户 {user_id}")
            else:
                print(f"✗ 发送失败: {data.get('message', 'Unknown error')}")
                
        except requests.exceptions.ConnectionError:
            print("错误: 无法连接到API服务器")
            sys.exit(1)
        except Exception as e:
            print(f"错误: {e}")
            sys.exit(1)
    
    def list_cron(self, json_output: bool = False):
        """列出定时任务"""
        try:
            response = requests.get(f"{self.base_url}/api/cron", timeout=5)
            response.raise_for_status()
            data = response.json()
            
            tasks = data.get('tasks', [])
            
            if json_output:
                print(json.dumps(data, indent=2, ensure_ascii=False))
                return
            
            print(f"=== 定时任务列表 (共{len(tasks)}个) ===")
            
            for i, task in enumerate(tasks, 1):
                print(f"\n{i}. {task.get('name', 'Unnamed')} (ID: {task.get('id', 'N/A')})")
                print(f"   目标用户: {task.get('target_user', 'N/A')}")
                print(f"   执行时间: {task.get('target_time', 'N/A')}")
                print(f"   状态: {task.get('status', 'N/A')}")
                print(f"   重复: {task.get('repeat', 'never')}")
                print(f"   创建时间: {task.get('created_at', 'N/A')}")
                print(f"   创建者: {task.get('created_by', 'system')}")
                
                if task.get('last_executed_at'):
                    print(f"   上次执行: {task.get('last_executed_at')}")
                if task.get('error_message'):
                    print(f"   错误信息: {task.get('error_message')}")
                    
        except requests.exceptions.ConnectionError:
            print("错误: 无法连接到API服务器")
            sys.exit(1)
        except Exception as e:
            print(f"错误: {e}")
            sys.exit(1)
    
    def add_cron(self, name: str, target_user: str, message: str, target_time: str, repeat: str = "never"):
        """添加定时任务"""
        try:
            payload = {
                "action": "add",
                "name": name,
                "target_user": target_user,
                "message": message,
                "target_time": target_time,
                "repeat": repeat
            }
            
            response = requests.post(
                f"{self.base_url}/api/cron",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            result = data.get('result', '')
            if 'success' in result.lower():
                print(f"✓ {result}")
            else:
                print(f"✗ {result}")
                
        except requests.exceptions.ConnectionError:
            print("错误: 无法连接到API服务器")
            sys.exit(1)
        except Exception as e:
            print(f"错误: {e}")
            sys.exit(1)
    
    def delete_cron(self, name: str = None, task_id: str = None):
        """删除定时任务"""
        if not name and not task_id:
            print("错误: 需要提供任务名称或ID")
            sys.exit(1)
            
        try:
            payload = {
                "action": "delete"
            }
            
            if name:
                payload["name"] = name
            if task_id:
                payload["id"] = task_id
            
            response = requests.post(
                f"{self.base_url}/api/cron",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get('success'):
                identifier = name if name else task_id
                print(f"✓ 成功删除定时任务: {identifier}")
            else:
                print(f"✗ 删除失败: 任务未找到")
                
        except requests.exceptions.ConnectionError:
            print("错误: 无法连接到API服务器")
            sys.exit(1)
        except Exception as e:
            print(f"错误: {e}")
            sys.exit(1)
    
    def restart_user(self, user_id: str):
        """重启用户会话"""
        try:
            payload = {
                "user_id": user_id
            }
            
            response = requests.post(
                f"{self.base_url}/api/user/restart",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 404:
                print(f"错误: 用户 '{user_id}' 不存在")
                sys.exit(1)
                
            response.raise_for_status()
            data = response.json()
            
            if data.get("success"):
                print(f"✓ 用户 {user_id} 会话已重启")
            else:
                print(f"✗ 重启失败: {data.get('message', 'Unknown error')}")
                
        except requests.exceptions.ConnectionError:
            print("错误: 无法连接到API服务器")
            sys.exit(1)
        except Exception as e:
            print(f"错误: {e}")
            sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="监控和管理主程序的命令行工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s status                    # 查看系统状态
  %(prog)s users                     # 列出所有用户
  %(prog)s user ivybridge            # 查看特定用户信息
  %(prog)s send ivybridge "Hello"    # 发送消息给用户
  %(prog)s cron list                 # 列出定时任务
  %(prog)s cron add --name "提醒" --user ivybridge --message "吃饭时间" --time "2024-03-12 18:00:00"
  %(prog)s restart ivybridge         # 重启用户会话
        """
    )
    
    parser.add_argument(
        "--url", 
        default="http://localhost:20721",
        help="API服务器地址 (默认: http://localhost:20721)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="以JSON格式输出"
    )
    
    # 子命令
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # status 命令
    status_parser = subparsers.add_parser("status", help="查看系统状态")
    
    # users 命令
    users_parser = subparsers.add_parser("users", help="列出所有用户")
    users_parser.add_argument("--detailed", action="store_true", help="显示详细信息")
    
    # user 命令
    user_parser = subparsers.add_parser("user", help="查看特定用户信息")
    user_parser.add_argument("user_id", help="用户ID")
    
    # send 命令
    send_parser = subparsers.add_parser("send", help="发送消息给用户")
    send_parser.add_argument("user_id", help="用户ID")
    send_parser.add_argument("message", help="消息内容")
    
    # cron 命令组
    cron_parser = subparsers.add_parser("cron", help="定时任务管理")
    cron_subparsers = cron_parser.add_subparsers(dest="cron_command", help="定时任务命令")
    
    # cron list
    cron_list_parser = cron_subparsers.add_parser("list", help="列出定时任务")
    
    # cron add
    cron_add_parser = cron_subparsers.add_parser("add", help="添加定时任务")
    cron_add_parser.add_argument("--name", required=True, help="任务名称")
    cron_add_parser.add_argument("--user", required=True, dest="target_user", help="目标用户")
    cron_add_parser.add_argument("--message", required=True, help="消息内容")
    cron_add_parser.add_argument("--time", required=True, dest="target_time", help="执行时间 (格式: YYYY-MM-DD HH:MM:SS)")
    cron_add_parser.add_argument("--repeat", choices=["daily", "never"], default="never", help="重复模式")
    
    # cron delete
    cron_delete_parser = cron_subparsers.add_parser("delete", help="删除定时任务")
    cron_delete_parser.add_argument("--name", help="任务名称")
    cron_delete_parser.add_argument("--id", help="任务ID")
    
    # restart 命令
    restart_parser = subparsers.add_parser("restart", help="重启用户会话")
    restart_parser.add_argument("user_id", help="用户ID")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    cli = MonitorCLI(base_url=args.url)
    
    try:
        if args.command == "status":
            cli.get_status(json_output=args.json)
        elif args.command == "users":
            cli.list_users(detailed=args.detailed, json_output=args.json)
        elif args.command == "user":
            cli.get_user(args.user_id, json_output=args.json)
        elif args.command == "send":
            cli.send_message(args.user_id, args.message)
        elif args.command == "cron":
            if args.cron_command == "list":
                cli.list_cron(json_output=args.json)
            elif args.cron_command == "add":
                cli.add_cron(
                    name=args.name,
                    target_user=args.target_user,
                    message=args.message,
                    target_time=args.target_time,
                    repeat=args.repeat
                )
            elif args.cron_command == "delete":
                cli.delete_cron(name=args.name, task_id=args.id)
            else:
                cron_parser.print_help()
        elif args.command == "restart":
            cli.restart_user(args.user_id)
    except KeyboardInterrupt:
        print("\n操作已取消")
        sys.exit(0)

if __name__ == "__main__":
    main()