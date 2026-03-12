#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试WeChatServerV2的IPv6支持
"""

import os
import sys
import time
import threading
import socket
import requests
from unittest.mock import Mock

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from source.Users import UserManager
from source.WeChatServerV2 import WeChatServer


def test_ipv6_support():
    """测试IPv6支持"""
    print("=" * 60)
    print("测试WeChatServerV2 IPv6支持")
    print("=" * 60)
    
    # 创建模拟的UserManager
    user_mgr = Mock(spec=UserManager)
    user_mgr.new_message = Mock()
    
    # 测试不同的监听地址配置
    test_configs = [
        {
            "name": "IPv6双栈 (::)",
            "host": "::",
            "port": 8889,
            "expected_type": "双栈服务器 (IPv4 + IPv6)"
        },
        {
            "name": "IPv4所有地址 (0.0.0.0)",
            "host": "0.0.0.0",
            "port": 8890,
            "expected_type": "标准服务器 (IPv4)"
        },
        {
            "name": "IPv6本地环回 (::1)",
            "host": "::1",
            "port": 8891,
            "expected_type": "IPv6服务器"
        },
        {
            "name": "IPv4本地环回 (127.0.0.1)",
            "host": "127.0.0.1",
            "port": 8892,
            "expected_type": "IPv4服务器"
        }
    ]
    
    servers = []
    
    try:
        for config in test_configs:
            print(f"\n测试配置: {config['name']}")
            print(f"监听地址: {config['host']}:{config['port']}")
            
            # 设置环境变量
            os.environ["SERVER_HOST"] = config["host"]
            os.environ["SERVER_PORT"] = str(config["port"])
            
            # 创建服务器实例
            server = WeChatServer(user_mgr)
            
            # 检查服务器配置
            print(f"服务器实际配置:")
            print(f"  - 主机: {server.host}")
            print(f"  - 端口: {server.port}")
            
            # 验证配置
            assert server.host == config["host"], f"主机配置不匹配: {server.host} != {config['host']}"
            assert server.port == config["port"], f"端口配置不匹配: {server.port} != {config['port']}"
            
            # 启动服务器（在独立线程中）
            print("启动服务器...")
            server.start()
            
            # 等待服务器启动
            time.sleep(2)
            
            # 检查服务器是否在运行
            if server.is_running:
                print("✓ 服务器启动成功")
                
                # 测试健康检查端点
                try:
                    # 根据主机地址构建正确的URL
                    if config['host'] == '::':
                        # IPv6双栈，可以使用IPv4地址连接
                        health_url = f"http://127.0.0.1:{config['port']}/health"
                    elif config['host'] == '0.0.0.0':
                        # IPv4所有地址，使用本地环回
                        health_url = f"http://127.0.0.1:{config['port']}/health"
                    elif config['host'] == '::1':
                        # IPv6本地环回，需要特殊格式
                        health_url = f"http://[::1]:{config['port']}/health"
                    else:
                        # 其他地址
                        health_url = f"http://{config['host']}:{config['port']}/health"
                    
                    print(f"测试健康检查: {health_url}")
                    
                    # 给服务器更多时间启动
                    time.sleep(3)
                    
                    response = requests.get(health_url, timeout=10)
                    if response.status_code == 200 and response.text == "OK":
                        print("✓ 健康检查通过")
                    else:
                        print(f"✗ 健康检查失败: {response.status_code} - {response.text}")
                except Exception as e:
                    print(f"✗ 健康检查请求失败: {e}")
                    # 尝试使用IPv4回退
                    if config['host'] in ['::', '::1']:
                        try:
                            fallback_url = f"http://127.0.0.1:{config['port']}/health"
                            print(f"尝试IPv4回退: {fallback_url}")
                            response = requests.get(fallback_url, timeout=5)
                            if response.status_code == 200 and response.text == "OK":
                                print("✓ IPv4回退健康检查通过")
                            else:
                                print(f"✗ IPv4回退失败: {response.status_code}")
                        except Exception as e2:
                            print(f"✗ IPv4回退也失败: {e2}")
                
                servers.append(server)
            else:
                print("✗ 服务器启动失败")
        
        print("\n" + "=" * 60)
        print("所有测试完成")
        print("=" * 60)
        
        # 显示运行中的服务器
        print(f"\n运行中的服务器数量: {len(servers)}")
        for i, server in enumerate(servers):
            print(f"服务器 {i+1}: {server.host}:{server.port}")
        
        # 保持运行一段时间以便观察
        print("\n服务器正在运行，按 Ctrl+C 停止...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n收到停止信号...")
        
    except Exception as e:
        print(f"\n测试过程中出错: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 停止所有服务器
        print("\n停止所有服务器...")
        for server in servers:
            try:
                server.stop()
                print(f"已停止服务器: {server.host}:{server.port}")
            except Exception as e:
                print(f"停止服务器时出错: {e}")
        
        print("\n测试完成")


def check_system_ipv6_support():
    """检查系统IPv6支持"""
    print("\n检查系统IPv6支持:")
    
    # 检查socket是否支持IPv6
    try:
        has_ipv6 = socket.has_ipv6
        print(f"系统支持IPv6: {has_ipv6}")
    except:
        print("无法检测IPv6支持")
    
    # 尝试创建IPv6 socket
    try:
        ipv6_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        ipv6_socket.close()
        print("✓ 可以创建IPv6 socket")
    except Exception as e:
        print(f"✗ 无法创建IPv6 socket: {e}")
    
    # 检查本地IPv6地址
    try:
        ipv6_addresses = []
        for info in socket.getaddrinfo('localhost', 80, socket.AF_INET6):
            ipv6_addresses.append(info[4][0])
        
        if ipv6_addresses:
            print(f"本地IPv6地址: {', '.join(set(ipv6_addresses))}")
        else:
            print("未找到本地IPv6地址")
    except Exception as e:
        print(f"获取IPv6地址失败: {e}")


if __name__ == "__main__":
    print("WeChatServerV2 IPv6支持测试")
    print("=" * 60)
    
    # 检查系统IPv6支持
    check_system_ipv6_support()
    
    # 运行IPv6支持测试
    test_ipv6_support()