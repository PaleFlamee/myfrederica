#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试企业微信echo验证修复
"""

import os
import sys
import time
import subprocess
from unittest.mock import Mock

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from source.Users import UserManager
from source.WeChatServerV2 import WeChatServer


def test_echo_validation():
    """测试echo验证"""
    print("测试企业微信echo验证修复")
    print("=" * 60)
    
    # 创建模拟的UserManager
    user_mgr = Mock(spec=UserManager)
    user_mgr.new_message = Mock()
    
    # 启动服务器
    print("启动WeChatServerV2服务器...")
    server = WeChatServer(user_mgr)
    server.start()
    
    # 等待服务器启动
    time.sleep(3)
    
    if not server.is_running:
        print("✗ 服务器启动失败")
        return
    
    print("✓ 服务器启动成功")
    
    # 测试echo验证
    print("\n测试echo验证（模拟企业微信回调）...")
    
    # 模拟企业微信的验证请求参数
    # 这些参数需要根据实际的token、AESKey等生成
    # 这里我们使用一个简单的测试
    
    test_urls = [
        {
            "name": "IPv6 echo验证",
            "url": "http://[::1]:8888/callback?msg_signature=test&timestamp=1234567890&nonce=123456&echostr=test123"
        },
        {
            "name": "缺少参数测试",
            "url": "http://[::1]:8888/callback"
        }
    ]
    
    for test in test_urls:
        print(f"\n{test['name']}:")
        print(f"URL: {test['url']}")
        
        try:
            cmd = ['curl', '-s', '-v', test['url'], '--max-time', '5']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            print(f"状态码: 通过响应头分析")
            
            # 分析响应
            if "HTTP/1.1 400" in result.stderr:
                if "Missing required parameters" in result.stdout:
                    print("✓ 收到预期的'Missing required parameters'响应")
                elif "Signature verification failed" in result.stdout:
                    print("✓ 收到签名验证失败响应（参数格式不正确但服务器处理了）")
                else:
                    print(f"响应: {result.stdout[:200]}")
            elif "HTTP/1.1 200" in result.stderr:
                print("✓ 收到200 OK响应")
                print(f"响应内容: {result.stdout[:100]}...")
            else:
                print(f"响应头: {result.stderr[:300]}...")
                
        except Exception as e:
            print(f"✗ 请求失败: {e}")
    
    # 测试健康检查
    print("\n测试健康检查:")
    try:
        cmd = ['curl', '-s', 'http://[::1]:8888/health']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if result.stdout.strip() == "OK":
            print("✓ 健康检查通过")
        else:
            print(f"✗ 健康检查失败: {result.stdout}")
    except Exception as e:
        print(f"✗ 健康检查失败: {e}")
    
    # 停止服务器
    print("\n停止服务器...")
    server.stop()
    
    print("\n测试完成")


def check_aiohttp_version():
    """检查aiohttp版本"""
    print("\n检查aiohttp版本:")
    try:
        import aiohttp
        print(f"aiohttp版本: {aiohttp.__version__}")
        
        # 检查web.Response的参数
        import inspect
        sig = inspect.signature(aiohttp.web.Response.__init__)
        params = list(sig.parameters.keys())
        
        print("web.Response参数:")
        for param in params:
            print(f"  - {param}")
            
        # 检查是否有charset参数
        if 'charset' in params:
            print("✓ web.Response支持charset参数")
        else:
            print("✗ web.Response不支持charset参数")
            
    except Exception as e:
        print(f"检查失败: {e}")


if __name__ == "__main__":
    print("企业微信echo验证测试")
    print("=" * 60)
    
    # 检查aiohttp版本
    check_aiohttp_version()
    
    # 运行echo验证测试
    test_echo_validation()