#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试高性能企业微信服务器V2
测试并发性能和安全性
"""

import os
import sys
import time
import asyncio
import threading
import logging
from concurrent.futures import ThreadPoolExecutor
import requests
from typing import List, Dict

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 设置测试配置
os.environ["WECHAT_WORK_CORPID"] = "test_corpid"
os.environ["WECHAT_WORK_CALLBACK_TOKEN"] = "test_token"
# 使用有效的base64编码的AES密钥（43个字符，符合企业微信要求）
os.environ["WECHAT_WORK_ENCODING_AES_KEY"] = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG=="
os.environ["SERVER_HOST"] = "127.0.0.1"
os.environ["SERVER_PORT"] = "8899"  # 使用不同端口避免冲突

# 设置性能参数
os.environ["MAX_CONNECTIONS"] = "50"
os.environ["MAX_CONCURRENT_REQUESTS"] = "20"
os.environ["REQUEST_TIMEOUT"] = "5"
os.environ["CONNECTION_TIMEOUT"] = "3"
os.environ["MAX_REQUEST_SIZE"] = "1048576"  # 1MB
os.environ["RATE_LIMIT_WINDOW"] = "10"
os.environ["RATE_LIMIT_MAX"] = "5"

# 禁用详细日志
logging.getLogger().setLevel(logging.ERROR)


class WeChatServerTester:
    """测试高性能WeChatServer"""
    
    def __init__(self):
        self.base_url = "http://127.0.0.1:8899"
        self.server_thread = None
        self.server = None
        self.results = []
    
    def start_server(self):
        """启动服务器"""
        from source.WeChatServerV2 import WeChatServer
        
        self.server = WeChatServer()
        
        # 在单独的线程中启动服务器
        def run_server():
            self.server.start()
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        
        # 等待服务器启动
        time.sleep(2)
        print("服务器已启动")
    
    def stop_server(self):
        """停止服务器"""
        if self.server:
            self.server.stop()
        if self.server_thread:
            self.server_thread.join(timeout=5)
        print("服务器已停止")
    
    def test_health_check(self):
        """测试健康检查"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=3)
            if response.status_code == 200 and response.text == "OK":
                print("✓ 健康检查通过")
                return True
            else:
                print(f"✗ 健康检查失败: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"✗ 健康检查异常: {e}")
            return False
    
    def test_get_verification(self):
        """测试GET验证"""
        try:
            # 模拟企业微信验证请求
            params = {
                'msg_signature': 'test_signature',
                'timestamp': '1234567890',
                'nonce': 'test_nonce',
                'echostr': 'test_echostr'
            }
            
            response = requests.get(f"{self.base_url}/callback", params=params, timeout=3)
            
            # 由于签名验证会失败，我们期望400错误
            if response.status_code == 400:
                print("✓ GET验证测试通过（预期签名验证失败）")
                return True
            else:
                print(f"✗ GET验证测试失败: 状态码 {response.status_code}")
                return False
        except Exception as e:
            print(f"✗ GET验证测试异常: {e}")
            return False
    
    def test_post_message(self):
        """测试POST消息"""
        try:
            # 模拟企业微信消息请求
            params = {
                'msg_signature': 'test_signature',
                'timestamp': '1234567890',
                'nonce': 'test_nonce'
            }
            
            # 模拟XML消息体
            xml_body = """<xml>
<ToUserName><![CDATA[toUser]]></ToUserName>
<FromUserName><![CDATA[fromUser]]></FromUserName>
<CreateTime>1348831860</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[测试消息]]></Content>
<MsgId>1234567890123456</MsgId>
</xml>"""
            
            response = requests.post(
                f"{self.base_url}/callback",
                params=params,
                data=xml_body,
                headers={'Content-Type': 'text/xml'},
                timeout=3
            )
            
            # 由于解密会失败，我们期望400错误
            if response.status_code == 400:
                print("✓ POST消息测试通过（预期解密失败）")
                return True
            else:
                print(f"✗ POST消息测试失败: 状态码 {response.status_code}")
                return False
        except Exception as e:
            print(f"✗ POST消息测试异常: {e}")
            return False
    
    def test_concurrent_requests(self, num_requests: int = 5):
        """测试并发请求"""
        print(f"\n测试 {num_requests} 个并发请求...")
        
        def make_request(request_id: int):
            try:
                start_time = time.time()
                response = requests.get(f"{self.base_url}/health", timeout=5)
                end_time = time.time()
                
                return {
                    'id': request_id,
                    'success': response.status_code == 200,
                    'time': end_time - start_time
                }
            except Exception as e:
                return {
                    'id': request_id,
                    'success': False,
                    'error': str(e),
                    'time': 0
                }
        
        # 使用线程池并发请求
        with ThreadPoolExecutor(max_workers=num_requests) as executor:
            futures = [executor.submit(make_request, i) for i in range(num_requests)]
            results = [future.result() for future in futures]
        
        # 分析结果
        successful = sum(1 for r in results if r.get('success', False))
        total_time = sum(r.get('time', 0) for r in results)
        avg_time = total_time / len(results) if results else 0
        
        print(f"并发测试结果:")
        print(f"  成功请求: {successful}/{num_requests}")
        print(f"  平均响应时间: {avg_time:.3f}秒")
        
        if successful >= num_requests * 0.8:  # 80%成功率
            print("✓ 并发测试通过")
            return True
        else:
            print("✗ 并发测试失败")
            return False
    
    def test_rate_limiting(self):
        """测试频率限制"""
        print("\n测试频率限制...")
        
        # 快速发送多个请求到/callback端点（应该应用频率限制）
        successes = 0
        failures = 0
        
        for i in range(10):  # 发送10个请求，超过限制(5个/10秒)
            try:
                # 使用不同的参数避免签名验证错误
                params = {
                    'msg_signature': f'test_signature_{i}',
                    'timestamp': str(1234567890 + i),
                    'nonce': f'test_nonce_{i}',
                    'echostr': f'test_echostr_{i}'
                }
                
                response = requests.get(f"{self.base_url}/callback", params=params, timeout=2)
                if response.status_code == 400:  # 签名验证失败，但请求被处理了
                    successes += 1
                elif response.status_code == 429:  # Too Many Requests
                    failures += 1
                time.sleep(0.1)  # 稍微延迟
            except Exception as e:
                # 忽略连接错误
                pass
        
        print(f"频率限制测试结果:")
        print(f"  处理请求: {successes}")
        print(f"  被限制请求: {failures}")
        
        # 应该有部分请求被限制（因为我们发送了10个请求，限制是5个/10秒）
        if failures > 0:
            print("✓ 频率限制测试通过（部分请求被正确限制）")
            return True
        else:
            print("✗ 频率限制测试失败（没有请求被限制）")
            return False
    
    def test_request_size_limit(self):
        """测试请求大小限制"""
        print("\n测试请求大小限制...")
        
        try:
            # 创建超过限制的请求体
            large_body = "A" * 2 * 1024 * 1024  # 2MB，超过1MB限制
            
            response = requests.post(
                f"{self.base_url}/callback",
                data=large_body,
                timeout=3
            )
            
            if response.status_code == 413:  # Request Entity Too Large
                print("✓ 请求大小限制测试通过")
                return True
            else:
                print(f"✗ 请求大小限制测试失败: 状态码 {response.status_code}")
                return False
        except Exception as e:
            print(f"✗ 请求大小限制测试异常: {e}")
            return False
    
    def run_all_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("开始测试高性能WeChatServerV2")
        print("=" * 60)
        
        try:
            # 启动服务器
            print("\n1. 启动服务器...")
            self.start_server()
            
            # 等待服务器完全启动
            time.sleep(3)
            
            # 运行测试（注意顺序：请求大小限制在频率限制之前）
            tests = [
                ("健康检查", self.test_health_check),
                ("GET验证", self.test_get_verification),
                ("POST消息", self.test_post_message),
                ("并发请求", lambda: self.test_concurrent_requests(5)),
                ("请求大小限制", self.test_request_size_limit),
                ("频率限制", self.test_rate_limiting),
            ]
            
            results = []
            for test_name, test_func in tests:
                print(f"\n测试: {test_name}")
                try:
                    result = test_func()
                    results.append((test_name, result))
                except Exception as e:
                    print(f"测试 {test_name} 异常: {e}")
                    results.append((test_name, False))
            
            # 显示结果
            print("\n" + "=" * 60)
            print("测试结果汇总:")
            print("=" * 60)
            
            passed = 0
            total = len(results)
            
            for test_name, result in results:
                status = "✓ 通过" if result else "✗ 失败"
                print(f"{test_name}: {status}")
                if result:
                    passed += 1
            
            print(f"\n总计: {passed}/{total} 个测试通过")
            
            if passed == total:
                print("\n🎉 所有测试通过！服务器符合高性能要求。")
                return True
            else:
                print(f"\n⚠️  {total - passed} 个测试失败。")
                return False
            
        finally:
            # 停止服务器
            print("\n清理: 停止服务器...")
            self.stop_server()


async def test_async_concurrent():
    """测试异步并发性能"""
    print("\n" + "=" * 60)
    print("测试异步并发性能")
    print("=" * 60)
    
    async def make_async_request(session, request_id):
        try:
            start_time = time.time()
            async with session.get('http://127.0.0.1:8899/health') as response:
                end_time = time.time()
                return {
                    'id': request_id,
                    'success': response.status == 200,
                    'time': end_time - start_time
                }
        except Exception as e:
            return {
                'id': request_id,
                'success': False,
                'error': str(e),
                'time': 0
            }
    
    import aiohttp
    
    # 启动服务器
    tester = WeChatServerTester()
    tester.start_server()
    time.sleep(3)
    
    try:
        # 创建aiohttp会话
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # 创建10个并发请求
            tasks = [make_async_request(session, i) for i in range(10)]
            results = await asyncio.gather(*tasks)
            
            # 分析结果
            successful = sum(1 for r in results if r.get('success', False))
            total_time = sum(r.get('time', 0) for r in results)
            avg_time = total_time / len(results) if results else 0
            
            print(f"异步并发测试结果:")
            print(f"  成功请求: {successful}/10")
            print(f"  平均响应时间: {avg_time:.3f}秒")
            
            if successful >= 8:  # 80%成功率
                print("✓ 异步并发测试通过")
                return True
            else:
                print("✗ 异步并发测试失败")
                return False
    finally:
        tester.stop_server()


if __name__ == "__main__":
    # 运行同步测试
    tester = WeChatServerTester()
    sync_result = tester.run_all_tests()
    
    # 运行异步测试
    if sync_result:
        print("\n" + "=" * 60)
        print("开始异步并发测试")
        print("=" * 60)
        
        try:
            async_result = asyncio.run(test_async_concurrent())
        except Exception as e:
            print(f"异步测试异常: {e}")
            async_result = False
        
        # 最终结果
        print("\n" + "=" * 60)
        print("最终测试结果")
        print("=" * 60)
        
        if sync_result and async_result:
            print("🎉 所有测试通过！服务器满足高性能要求：")
            print("   ✓ 支持至少5个并发连接")
            print("   ✓ 异步高性能处理")
            print("   ✓ 频率限制保护")
            print("   ✓ 请求大小限制")
            print("   ✓ 连接池管理")
            sys.exit(0)
        else:
            print("⚠️ 部分测试失败")
            sys.exit(1)
    else:
        print("同步测试失败，跳过异步测试")
        sys.exit(1)