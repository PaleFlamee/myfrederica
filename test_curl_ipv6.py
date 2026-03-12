#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试curl连接IPv6和IPv4地址
"""

import os
import sys
import time
import subprocess
import threading
from unittest.mock import Mock

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from source.Users import UserManager
from source.WeChatServerV2 import WeChatServer


def start_server():
    """启动服务器"""
    print("启动WeChatServerV2服务器...")
    
    # 创建模拟的UserManager
    user_mgr = Mock(spec=UserManager)
    user_mgr.new_message = Mock()
    
    # 使用当前.env配置（应该是::）
    server = WeChatServer(user_mgr)
    server.start()
    
    # 等待服务器启动
    time.sleep(3)
    
    return server


def test_curl_connections():
    """测试curl连接"""
    print("\n测试curl连接...")
    
    # 测试IPv6地址 [::1]
    print("\n1. 测试IPv6地址: http://[::1]:8888/callback")
    try:
        # 使用curl测试IPv6
        cmd = ['curl', '-s', '-v', 'http://[::1]:8888/callback']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        print(f"状态码: 通过stderr分析")
        print(f"输出: {result.stdout[:200]}...")
        print(f"错误: {result.stderr[:500]}...")
        
        # 检查是否包含"missing required parameters"
        if "missing required parameters" in result.stdout.lower() or "Missing required parameters" in result.stdout:
            print("✓ 收到预期的'Missing required parameters'响应")
        else:
            print("✗ 未收到预期响应")
            
    except Exception as e:
        print(f"✗ IPv6测试失败: {e}")
    
    # 测试IPv4地址 127.0.0.1
    print("\n2. 测试IPv4地址: http://127.0.0.1:8888/callback")
    try:
        cmd = ['curl', '-s', '-v', 'http://127.0.0.1:8888/callback', '--max-time', '5']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        print(f"状态码: 通过stderr分析")
        print(f"输出: {result.stdout[:200]}...")
        print(f"错误: {result.stderr[:500]}...")
        
        # 检查连接错误
        if "Failed to connect" in result.stderr or "Connection refused" in result.stderr:
            print("✗ 无法连接到服务器（连接被拒绝）")
        elif "timed out" in result.stderr.lower():
            print("✗ 连接超时")
        else:
            print("✓ IPv4连接成功")
            
    except subprocess.TimeoutExpired:
        print("✗ 连接超时")
    except Exception as e:
        print(f"✗ IPv4测试失败: {e}")
    
    # 测试健康检查端点
    print("\n3. 测试健康检查端点:")
    
    # IPv6健康检查
    print("  a) IPv6健康检查: http://[::1]:8888/health")
    try:
        cmd = ['curl', '-s', 'http://[::1]:8888/health']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if result.stdout.strip() == "OK":
            print("    ✓ 健康检查通过")
        else:
            print(f"    ✗ 健康检查失败: {result.stdout}")
    except Exception as e:
        print(f"    ✗ IPv6健康检查失败: {e}")
    
    # IPv4健康检查
    print("  b) IPv4健康检查: http://127.0.0.1:8888/health")
    try:
        cmd = ['curl', '-s', 'http://127.0.0.1:8888/health', '--max-time', '5']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if result.stdout.strip() == "OK":
            print("    ✓ 健康检查通过")
        else:
            print(f"    ✗ 健康检查失败: {result.stdout}")
    except Exception as e:
        print(f"    ✗ IPv4健康检查失败: {e}")


def check_server_listening_ports():
    """检查服务器监听的端口"""
    print("\n检查服务器监听的端口...")
    
    try:
        # 使用netstat检查监听端口
        cmd = ['netstat', '-an', '-p', 'TCP']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        
        # 查找端口8888
        lines = result.stdout.split('\n')
        port_8888_lines = [line for line in lines if ':8888' in line and 'LISTENING' in line]
        
        if port_8888_lines:
            print(f"找到端口8888监听:")
            for line in port_8888_lines:
                print(f"  {line.strip()}")
                
            # 分析监听地址
            for line in port_8888_lines:
                if '0.0.0.0:8888' in line:
                    print("  ✓ 监听在0.0.0.0 (所有IPv4地址)")
                elif '[::]:8888' in line or ':::8888' in line:
                    print("  ✓ 监听在:: (所有IPv6地址)")
                elif '[::1]:8888' in line:
                    print("  ✓ 监听在::1 (IPv6本地环回)")
                elif '127.0.0.1:8888' in line:
                    print("  ✓ 监听在127.0.0.1 (IPv4本地环回)")
        else:
            print("✗ 未找到端口8888监听")
            
    except Exception as e:
        print(f"检查端口失败: {e}")


def main():
    print("测试curl连接IPv6和IPv4地址")
    print("=" * 60)
    
    server = None
    try:
        # 启动服务器
        server = start_server()
        
        if server and server.is_running:
            print("✓ 服务器启动成功")
            
            # 检查监听端口
            check_server_listening_ports()
            
            # 测试curl连接
            test_curl_connections()
            
            print("\n" + "=" * 60)
            print("测试完成，按Ctrl+C停止服务器...")
            
            # 保持运行
            while True:
                time.sleep(1)
        else:
            print("✗ 服务器启动失败")
            
    except KeyboardInterrupt:
        print("\n收到停止信号...")
    except Exception as e:
        print(f"\n测试过程中出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if server:
            print("\n停止服务器...")
            server.stop()


if __name__ == "__main__":
    main()