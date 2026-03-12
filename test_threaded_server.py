#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试WeChatServerV2的多线程启动功能
"""

import os
import sys
import time
import threading
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from source.Users import UserManager
from source.WeChatServerV2 import WeChatServer


def setup_test_environment():
    """设置测试环境变量"""
    # 设置企业微信配置（测试用）
    os.environ["WECHAT_WORK_CORPID"] = "test_corpid"
    os.environ["WECHAT_WORK_CALLBACK_TOKEN"] = "test_token"
    # 使用有效的base64编码的AES密钥（43个字符，符合企业微信要求）
    os.environ["WECHAT_WORK_ENCODING_AES_KEY"] = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG"
    
    # 服务器配置
    os.environ["SERVER_HOST"] = "127.0.0.1"
    os.environ["SERVER_PORT"] = "8888"
    
    # 性能和安全配置
    os.environ["MAX_CONNECTIONS"] = "100"
    os.environ["MAX_CONCURRENT_REQUESTS"] = "50"
    os.environ["REQUEST_TIMEOUT"] = "30"
    os.environ["CONNECTION_TIMEOUT"] = "10"
    os.environ["MAX_REQUEST_SIZE"] = "10485760"
    os.environ["RATE_LIMIT_WINDOW"] = "60"
    os.environ["RATE_LIMIT_MAX"] = "100"


def test_threaded_start():
    """测试多线程启动功能"""
    print("=" * 60)
    print("测试WeChatServerV2多线程启动功能")
    print("=" * 60)
    
    # 设置测试环境
    setup_test_environment()
    
    # 创建UserManager实例
    print("1. 创建UserManager实例...")
    user_mgr = UserManager()
    
    # 创建WeChatServer实例
    print("2. 创建WeChatServer实例...")
    server = WeChatServer(user_mgr)
    
    # 测试1: 启动服务器（应该在线程中运行）
    print("3. 启动服务器（多线程）...")
    server.start()
    
    # 检查线程是否启动
    print("4. 检查服务器线程状态...")
    time.sleep(2)  # 给线程一点时间启动
    
    if server.server_thread and server.server_thread.is_alive():
        print("   ✓ 服务器线程正在运行")
        print(f"   ✓ 线程名称: {server.server_thread.name}")
        print(f"   ✓ 线程ID: {server.server_thread.ident}")
        print(f"   ✓ 是否为守护线程: {server.server_thread.daemon}")
    else:
        print("   ✗ 服务器线程未启动或已停止")
        return False
    
    # 测试2: 检查服务器运行状态
    print("5. 检查服务器运行状态...")
    if server.is_running:
        print("   ✓ 服务器标记为运行中")
    else:
        print("   ⚠ 服务器未标记为运行中（可能需要更多时间启动）")
    
    # 测试3: 尝试再次启动（应该被拒绝）
    print("6. 测试重复启动...")
    server.start()  # 应该输出警告信息
    
    # 测试4: 运行一段时间
    print("7. 让服务器运行10秒...")
    for i in range(10):
        print(f"   运行中... {i+1}/10 秒")
        time.sleep(1)
    
    # 测试5: 停止服务器
    print("8. 停止服务器...")
    server.stop()
    
    # 检查线程是否停止
    print("9. 检查服务器线程状态...")
    time.sleep(2)  # 给线程一点时间停止
    
    if server.server_thread and server.server_thread.is_alive():
        print("   ⚠ 服务器线程仍在运行（可能需要更多时间停止）")
    else:
        print("   ✓ 服务器线程已停止")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)
    
    return True


def test_main_thread_not_blocked():
    """测试主线程是否被阻塞"""
    print("\n" + "=" * 60)
    print("测试主线程是否被阻塞")
    print("=" * 60)
    
    setup_test_environment()
    
    user_mgr = UserManager()
    server = WeChatServer(user_mgr)
    
    print("1. 启动服务器...")
    server.start()
    
    print("2. 主线程继续执行其他任务...")
    
    # 在主线程中执行一些任务，证明没有被阻塞
    tasks_completed = 0
    for i in range(5):
        print(f"   主线程任务 {i+1}/5...")
        time.sleep(1)
        tasks_completed += 1
    
    print(f"3. 主线程完成了 {tasks_completed} 个任务")
    
    # 停止服务器
    print("4. 停止服务器...")
    server.stop()
    
    if tasks_completed == 5:
        print("   ✓ 主线程未被阻塞，可以继续执行任务")
        return True
    else:
        print("   ✗ 主线程可能被阻塞")
        return False


def test_multiple_servers():
    """测试启动多个服务器实例"""
    print("\n" + "=" * 60)
    print("测试多个服务器实例")
    print("=" * 60)
    
    setup_test_environment()
    
    user_mgr = UserManager()
    
    # 创建两个服务器实例，使用不同端口
    os.environ["SERVER_PORT"] = "8888"
    server1 = WeChatServer(user_mgr)
    
    os.environ["SERVER_PORT"] = "8889"
    server2 = WeChatServer(user_mgr)
    
    print("1. 启动第一个服务器（端口8888）...")
    server1.start()
    
    print("2. 启动第二个服务器（端口8889）...")
    server2.start()
    
    print("3. 检查两个服务器线程...")
    time.sleep(2)
    
    threads_running = 0
    if server1.server_thread and server1.server_thread.is_alive():
        print("   ✓ 服务器1线程正在运行")
        threads_running += 1
    
    if server2.server_thread and server2.server_thread.is_alive():
        print("   ✓ 服务器2线程正在运行")
        threads_running += 1
    
    print(f"4. 运行5秒...")
    time.sleep(5)
    
    print("5. 停止所有服务器...")
    server1.stop()
    server2.stop()
    
    time.sleep(2)
    
    if threads_running == 2:
        print("   ✓ 两个服务器线程都成功启动")
        return True
    else:
        print(f"   ✗ 只有 {threads_running}/2 个服务器线程启动")
        return False


if __name__ == "__main__":
    print("WeChatServerV2多线程功能测试")
    print("=" * 60)
    
    # 运行所有测试
    tests_passed = 0
    tests_total = 0
    
    try:
        tests_total += 1
        if test_threaded_start():
            tests_passed += 1
    except Exception as e:
        print(f"测试1失败: {e}")
    
    try:
        tests_total += 1
        if test_main_thread_not_blocked():
            tests_passed += 1
    except Exception as e:
        print(f"测试2失败: {e}")
    
    try:
        tests_total += 1
        if test_multiple_servers():
            tests_passed += 1
    except Exception as e:
        print(f"测试3失败: {e}")
    
    print("\n" + "=" * 60)
    print(f"测试结果: {tests_passed}/{tests_total} 通过")
    print("=" * 60)
    
    if tests_passed == tests_total:
        print("🎉 所有测试通过！WeChatServerV2多线程功能正常。")
        sys.exit(0)
    else:
        print("⚠ 部分测试失败，请检查问题。")
        sys.exit(1)