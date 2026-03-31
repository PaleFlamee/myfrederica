#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高性能企业微信回调服务器
使用aiohttp实现异步高并发，支持公网环境
"""

import os
import asyncio
import logging
import time
import threading
from typing import Dict, Optional, Set, Tuple
from urllib.parse import parse_qs, urlparse, unquote
import json
import requests
import base64
from Crypto.Cipher import AES

import aiohttp
from aiohttp import web
from wechatpy.enterprise.crypto import WeChatCrypto
from wechatpy.enterprise import parse_message
from wechatpy.enterprise.replies import TextReply

from .Message import Message, MultimodalContent
from .Users import UserManager
from .WXBizJsonMsgCrypt import WXBizJsonMsgCrypt

# 使用项目现有的日志系统
logger = logging.getLogger(__name__)

from .Utils import get_config_instance
config = get_config_instance()

class WeChatBotServer:
    def __init__(self, user_mgr_instance: UserManager):
        global config
        self.home_directory = config.home_directory
        self.token = config.wechat_work_callback_token
        self.encoding_aes_key = config.wechat_work_encoding_aes_key
        self.user_mgr = user_mgr_instance
        self.crypto = WXBizJsonMsgCrypt(self.token, self.encoding_aes_key, "")
        # receiveid 必须是空字符串

    async def _download_decrypt_file_and_send_announcement(self, file_url:str, user_id:str):
        """
        下载并解密加密文件
            
        返回:
            tuple: (status: bool, data: bytes/str) 
                status为True时data是解密后的文件数据，
                status为False时data是错误信息
        """
        try:
            # 1. 下载加密文件
            logger.info("开始下载加密文件: %s", file_url)
            # response = requests.get(file_url, timeout=15)
            # response.raise_for_status()
            # encrypted_data = response.content
            async with aiohttp.ClientSession() as session:
                async with session.get(file_url, timeout=aiohttp.ClientTimeout(total=120)) as response:
                    if response.status != 200:
                        logger.error(f"下载媒体文件失败: HTTP {response.status}")
                        return None
                    encrypted_data = await response.read()
                    # test
                    # logger.error(response.headers)
                    # logger.error(encrypted_data)
                    # /test
                    logger.info("文件下载成功，大小: %d 字节", len(encrypted_data))

            # 2. 准备AES密钥和IV
            if not self.encoding_aes_key:
                raise ValueError("AES密钥不能为空")
                
            # Base64解码密钥 (自动处理填充)
            aes_key = base64.b64decode(self.encoding_aes_key + "=" * (-len(self.encoding_aes_key) % 4))
            if len(aes_key) != 32:
                raise ValueError("无效的AES密钥长度: 应为32字节")
                
            iv = aes_key[:16]  # 初始向量为密钥前16字节
            
            # 3. 解密文件数据
            cipher = AES.new(aes_key, AES.MODE_CBC, iv)
            decrypted_data = cipher.decrypt(encrypted_data)
            
            # 4. 去除PKCS#7填充 (Python 3兼容写法)
            pad_len = decrypted_data[-1]  # 直接获取最后一个字节的整数值
            if pad_len > 32:  # AES-256块大小为32字节
                raise ValueError("无效的填充长度 (大于32字节)")
                
            decrypted_data = decrypted_data[:-pad_len]
            logger.info("文件解密成功，解密后大小: %d 字节", len(decrypted_data))

            # 保存文件
            content_disposition = response.headers.get('Content-Disposition', '')
            filename = None
            if 'filename=' in content_disposition:
                raw_name = content_disposition.split('filename=')[-1].strip()
                filename = unquote(raw_name)

            if not filename:
                url_id = urlparse(file_url).path.split('/')[-1][:16]
                filename = f"{int(time.time())}_{url_id}"

            save_path = os.path.join(config.home_directory, user_id, "files", filename)

            with open(save_path, 'wb') as f:
                f.write(decrypted_data)
            
            logger.info(f"文件下载成功: {save_path}, 大小: {len(decrypted_data)} 字节")

            self.user_mgr.general_handle_new_message(
                user_id=user_id,
                incoming_message_queue=[
                    Message(
                        content=f"[System Message] Received file, saved to ./{user_id}/files/{filename}",
                        role="user"
                    )
                ]
            )
            
            return True, decrypted_data
            
        except ValueError as e:
            error_msg = f"参数错误 : {str(e)}"
            logger.error(error_msg)
            return False, error_msg
            
        except Exception as e:
            error_msg = f"文件处理异常 : {str(e)}"
            logger.error(error_msg)
            return False, error_msg


    async def handle_get(self, request: web.Request):
        """处理GET请求（企业微信服务器验证）"""
        client_ip = request.remote
        try:
            # 解析查询参数
            query_params = parse_qs(request.query_string)
            
            # 提取参数
            msg_signature = query_params.get('msg_signature', [''])[0]
            timestamp = query_params.get('timestamp', [''])[0]
            nonce = query_params.get('nonce', [''])[0]
            echostr = query_params.get('echostr', [''])[0]
            
            if not all([msg_signature, timestamp, nonce, echostr]):
                logger.error(f"WeChatBotServer:GET请求缺少必要参数，来自 {client_ip}")
                return web.Response(status=400, text="Missing required parameters")
            
            # 验证签名并解密echostr
            try:
                ret, echostr_plain = self.crypto.VerifyURL(msg_signature, timestamp, nonce, echostr)
                if ret != 0:
                    return web.Response(status=400, text="Signature verification failed")
                
                # 返回解密后的echostr
                return web.Response(
                    text=echostr_plain,
                    content_type='text/plain',
                    charset='utf-8'
                )
                
            except Exception as e:
                logger.error(f"WeChatBotServer:GET验证失败: {e}，来自 {client_ip}")
                return web.Response(status=400, text="Signature verification failed")
                
        except Exception as e:
            logger.error(f"WeChatBotServer:处理GET请求时出错: {e}，来自 {client_ip}")
            return web.Response(status=500, text=f"Internal Server Error: {str(e)}")
    async def handle_post(self, request: web.Request):
        """处理POST请求（接收企业微信消息）"""
        client_ip = request.remote
        try:
            
            # 解析查询参数
            query_params = parse_qs(request.query_string)
            
            # 提取参数
            msg_signature = query_params.get('msg_signature', [''])[0]
            timestamp = query_params.get('timestamp', [''])[0]
            nonce = query_params.get('nonce', [''])[0]
            
            if not all([msg_signature, timestamp, nonce]):
                logger.error(f"POST请求缺少必要参数，来自 {client_ip}")
                return web.Response(status=400, text="Missing required parameters")
            
            # 读取请求体
            request_body = await request.text()
            try:
                ret, msg = self.crypto.DecryptMsg(request_body, msg_signature, timestamp, nonce)
                
                if not request_body:
                    logger.error(f"POST请求体为空，来自 {client_ip}")
                    return web.Response(status=400, text="Empty request body")
                
                data = json.loads(msg)

                if data["msgtype"] == "file":
                    user_id = data["from"]["userid"]
                    file_url = data["file"]["url"]
                    asyncio.create_task(self._download_decrypt_file_and_send_announcement(file_url, user_id))

                return web.Response(text="")

            except Exception as e:
                logger.error(f"解密或处理消息失败: {e}，来自 {client_ip}")
                return web.Response(status=400, text="Message processing failed")
                
        except asyncio.TimeoutError:
            logger.error(f"请求超时，来自 {client_ip}")
            return web.Response(status=408, text="Request Timeout")
        except Exception as e:
            logger.error(f"处理POST请求时出错: {e}，来自 {client_ip}")
            return web.Response(status=500, text=f"Internal Server Error: {str(e)}")


class WeChatServer:
    """
    高性能企业微信回调服务器
    单class设计，支持高并发，应对公网环境
    """
    
    def __init__(self, user_mgr_instance: UserManager, bot_server: WeChatBotServer = None):
        """初始化服务器"""
        # 从环境变量读取配置
        global config
        self.corpid = config.wechat_work_corpid
        self.token = config.wechat_work_callback_token
        self.encoding_aes_key = config.wechat_work_encoding_aes_key
        
        # 服务器配置
        self.host = config.server_host
        self.port = config.server_port
        
        # 性能和安全配置
        self.max_connections = config.server_max_connections
        self.max_concurrent_requests = config.server_concurrent_requests
        self.connection_timeout = config.server_connection_timeout
        self.request_timeout = config.server_requset_timeout
        self.max_request_size = config.server_max_request_size

        # 频率限制配置
        self.rate_limit_window = config.server_rate_limit_window
        self.rate_limit_max = config.server_rate_limit_max_requests

        # 初始化加密实例
        self.crypto = WeChatCrypto(self.token, self.encoding_aes_key, self.corpid)
        
        # 运行时状态
        self.app = None
        self.runner = None
        self.site = None
        self.is_running = False
        self.server_thread = None  # 服务器线程
        
        # 连接跟踪和频率限制
        self.active_connections: Set[str] = set()
        self.request_counts: Dict[str, list] = {}

        # 用户管理实例
        self.user_mgr = user_mgr_instance
        
        self.bot_server = bot_server
        
        # 验证必要配置
        self._validate_config()
        
    
    def _validate_config(self):
        """验证配置"""
        required_vars = [
            "WECHAT_WORK_CORPID",
            "WECHAT_WORK_CALLBACK_TOKEN", 
            "WECHAT_WORK_ENCODING_AES_KEY"
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            logger.error(f"缺少必要环境变量: {missing_vars}")
            raise ValueError(f"缺少必要环境变量: {missing_vars}")
    
    def _check_rate_limit(self, client_ip: str) -> bool:
        """检查频率限制"""
        now = time.time()
        
        # 清理过期记录
        if client_ip in self.request_counts:
            self.request_counts[client_ip] = [
                timestamp for timestamp in self.request_counts[client_ip]
                if now - timestamp < self.rate_limit_window
            ]
        
        # 检查是否超过限制
        if client_ip in self.request_counts:
            if len(self.request_counts[client_ip]) >= self.rate_limit_max:
                logger.warning(f"频率限制: IP {client_ip} 超过限制")
                return False
        
        # 记录当前请求
        if client_ip not in self.request_counts:
            self.request_counts[client_ip] = []
        self.request_counts[client_ip].append(now)
        
        return True
    
    def _cleanup_rate_limit(self):
        """清理频率限制数据"""
        now = time.time()
        for ip in list(self.request_counts.keys()):
            self.request_counts[ip] = [
                timestamp for timestamp in self.request_counts[ip]
                if now - timestamp < self.rate_limit_window * 2
            ]
            if not self.request_counts[ip]:
                del self.request_counts[ip]
    
    async def _download_media_file(self, media_id: str, save_path: str) -> Optional[str]:
        try:
            # 获取 access_token
            from .WeChatClient import get_wechat_client
            client = get_wechat_client()
            access_token = client._get_access_token()
            
            if not access_token:
                logger.error(f"下载媒体文件失败: 无法获取 access_token")
                return None
            
            # 构建下载URL
            url = f"https://qyapi.weixin.qq.com/cgi-bin/media/get?access_token={access_token}&media_id={media_id}"
            
            # 使用 aiohttp 下载文件
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    if response.status != 200:
                        logger.error(f"下载媒体文件失败: HTTP {response.status}")
                        return None
                    
                    # 检查是否返回了错误JSON
                    content_type = response.headers.get('Content-Type', '')
                    if 'application/json' in content_type or 'text/plain' in content_type:
                        error_data = await response.text()
                        logger.error(f"下载媒体文件失败: {error_data}")
                        return None
                    
                    # 从 Content-Type 获取文件扩展名
                    ext = 'jpg'  # 默认扩展名
                    if 'image/png' in content_type:
                        ext = 'png'
                    elif 'image/gif' in content_type:
                        ext = 'gif'
                    elif 'image/webp' in content_type:
                        ext = 'webp'
                    elif 'image/jpeg' in content_type or 'image/jpg' in content_type:
                        ext = 'jpg'
                    final_path = f"{save_path}.{ext}"
                    # 保存文件
                    content = await response.read()
                    with open(final_path, 'wb') as f:
                        f.write(content)
                    
                    logger.info(f"媒体文件下载成功: {final_path}, 大小: {len(content)} 字节")
                    return final_path
                    
        except asyncio.TimeoutError:
            logger.error(f"下载媒体文件超时: media_id={media_id}")
            return None
        except Exception as e:
            logger.error(f"下载媒体文件时出错: {e}")
            return None

    async def _download_file(self, media_id: str, save_path: str) -> Optional[str]:
        try:
            # 获取 access_token
            from .WeChatClient import get_wechat_client
            client = get_wechat_client()
            access_token = client._get_access_token()
            
            if not access_token:
                logger.error(f"下载普通文件失败: 无法获取 access_token")
                return None
            
            # 构建下载URL
            url = f"https://qyapi.weixin.qq.com/cgi-bin/media/get?access_token={access_token}&media_id={media_id}"
            
            # 使用 aiohttp 下载文件
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    if response.status != 200:
                        logger.error(f"下载普通文件失败: HTTP {response.status}")
                        return None
                    
                    # 检查是否返回了错误JSON
                    content_type = response.headers.get('Content-Type', '')
                    if 'application/json' in content_type or 'text/plain' in content_type:
                        error_data = await response.text()
                        logger.error(f"下载普通文件失败: {error_data}")
                        return None
                    
                    # 保存文件
                    content = await response.read()
                    with open(save_path, 'wb') as f:
                        f.write(content)
                    
                    logger.info(f"媒体文件下载成功: {save_path}, 大小: {len(content)} 字节")
                    return "success"
                    
        except asyncio.TimeoutError:
            logger.error(f"下载媒体文件超时: media_id={media_id}")
            return None
        except Exception as e:
            logger.error(f"下载媒体文件时出错: {e}")
            return None

    async def _handle_get(self, request: web.Request) -> web.Response:
        """处理GET请求（企业微信服务器验证）"""
        client_ip = request.remote
        
        # 检查频率限制
        if not self._check_rate_limit(client_ip):
            return web.Response(status=429, text="Too Many Requests")
        
        try:
            # 解析查询参数
            query_params = parse_qs(request.query_string)
            
            # 提取参数
            msg_signature = query_params.get('msg_signature', [''])[0]
            timestamp = query_params.get('timestamp', [''])[0]
            nonce = query_params.get('nonce', [''])[0]
            echostr = query_params.get('echostr', [''])[0]
            
            if not all([msg_signature, timestamp, nonce, echostr]):
                logger.error(f"GET请求缺少必要参数，来自 {client_ip}")
                return web.Response(status=400, text="Missing required parameters")
            
            # 验证签名并解密echostr
            try:
                decrypted_echostr = self.crypto.check_signature(
                    msg_signature,
                    timestamp,
                    nonce,
                    echostr
                )
                
                # 返回解密后的echostr
                return web.Response(
                    text=decrypted_echostr,
                    content_type='text/plain',
                    charset='utf-8'
                )
                
            except Exception as e:
                logger.error(f"GET验证失败: {e}，来自 {client_ip}")
                return web.Response(status=400, text="Signature verification failed")
                
        except Exception as e:
            logger.error(f"处理GET请求时出错: {e}，来自 {client_ip}")
            return web.Response(status=500, text=f"Internal Server Error: {str(e)}")
    
    async def _handle_post(self, request: web.Request) -> web.Response:
        """处理POST请求（接收企业微信消息）"""
        client_ip = request.remote
        
        # 检查频率限制
        if not self._check_rate_limit(client_ip):
            return web.Response(status=429, text="Too Many Requests")
        
        try:
            # 检查请求体大小
            content_length = request.content_length
            if content_length and content_length > self.max_request_size:
                logger.error(f"请求体过大: {content_length} > {self.max_request_size}，来自 {client_ip}")
                return web.Response(status=413, text="Request entity too large")
            
            # 解析查询参数
            query_params = parse_qs(request.query_string)
            
            # 提取参数
            msg_signature = query_params.get('msg_signature', [''])[0]
            timestamp = query_params.get('timestamp', [''])[0]
            nonce = query_params.get('nonce', [''])[0]
            
            if not all([msg_signature, timestamp, nonce]):
                logger.error(f"POST请求缺少必要参数，来自 {client_ip}")
                return web.Response(status=400, text="Missing required parameters")
            
            # 读取请求体
            request_body = await request.text()
            
            if not request_body:
                logger.error(f"POST请求体为空，来自 {client_ip}")
                return web.Response(status=400, text="Empty request body")
            
            # 解密消息
            try:
                decrypted_xml = self.crypto.decrypt_message(
                    request_body,
                    msg_signature,
                    timestamp,
                    nonce
                )
                
                # 解析消息
                message = parse_message(decrypted_xml)
                
                # 处理消息
                response_xml = await self._handle_message(message, nonce, timestamp)
                
                # 发送响应
                return web.Response(
                    text=response_xml,
                    content_type='text/xml',
                    charset='utf-8'
                )
                
            except Exception as e:
                logger.error(f"解密或处理消息失败: {e}，来自 {client_ip}")
                return web.Response(status=400, text="Message processing failed")
                
        except asyncio.TimeoutError:
            logger.error(f"请求超时，来自 {client_ip}")
            return web.Response(status=408, text="Request Timeout")
        except Exception as e:
            logger.error(f"处理POST请求时出错: {e}，来自 {client_ip}")
            return web.Response(status=500, text=f"Internal Server Error: {str(e)}")
    
    async def _handle_message(self, message, nonce: str, timestamp: str) -> str:
        """处理消息并返回响应XML"""
        try:
            user_id = message.source
            
            # 处理文本消息
            if message.type == 'text':
                content = message.content
                
                logger.info(f"收到文本消息来自 {user_id}: {content[:50]}...")
                
                # 如果UserManager可用，将消息添加到用户队列
                try:
                    # 添加消息到用户队列
                    self.user_mgr.general_handle_new_message(
                        user_id=user_id,
                        incoming_message_queue=[
                            Message(content=content, role="user")
                        ]
                    )
                    logger.info(f"消息已添加到用户 {user_id} 的队列")
                except Exception as e:
                    logger.error(f"添加消息到UserManager失败: {e}")
                
                # 企业微信要求：必须立即返回success，实际回复通过异步方式发送
                reply = TextReply(
                    content="",  # 空内容，表示已接收
                    message=message
                )
            elif message.type == "image":
                logger.info(f"Recv image msg, url: {message.image}, id: {message.media_id}")
                media_id = message.media_id
                media_id_short = media_id[:8] if len(media_id) >= 8 else media_id
                filename = f"{user_id}_{timestamp}_{media_id_short}"
                
                save_dir = os.path.join(config.home_directory, user_id, "images")
                os.makedirs(save_dir, exist_ok=True)
                save_path = os.path.join(save_dir, filename)
                
                asyncio.create_task(self._download_media_file(media_id, save_path))
    
                try:
                    self.user_mgr.general_handle_new_message(
                        user_id=user_id,
                        incoming_message_queue=[
                            Message(
                                content=[
                                    MultimodalContent(type="image_url", image_url=MultimodalContent.Url(url=message.image)),
                                    MultimodalContent(type="text", text=f"[System Message] Received image, saved to ./{user_id}/images/{filename} \
                                                      (Extension depends on actual image type.)\n\
                                                      Rename it to a more descriptive name if needed.")
                                ],
                                role="user"
                            )
                        ]
                    )
                    
                except Exception as e:
                    logger.error(f"Error when adding img msg to {user_id}: {e}")
                reply = TextReply(
                    content="",
                    message=message
                )
            elif message.type == 'file':
                media_id = message.media_id
                original_name = getattr(message, 'file_name', None) or f"{media_id[:8]}.bin"
                filename = f"{timestamp}_{original_name}"  # 加时间戳避免同名文件覆盖
                
                save_dir = os.path.join(config.home_directory, user_id, "files")
                os.makedirs(save_dir, exist_ok=True)
                save_path = os.path.join(save_dir, filename)
                
                asyncio.create_task(self._download_file(media_id, save_path))
                
                try:
                    self.user_mgr.general_handle_new_message(
                        user_id=user_id,
                        incoming_message_queue=[
                            Message(
                                content=f"[System Message] Received file, saved to ./{user_id}/files/{filename}",
                                role="user"
                            )
                        ]
                    )
                except Exception as e:
                    logger.error(f"Error when adding file msg to {user_id}: {e}")
                reply = TextReply(
                    content="",
                    message=message
                )
            elif message.type == 'event':
                # 处理事件消息
                event_type = getattr(message, 'event', 'unknown')
                logger.info(f"收到事件消息: 事件类型={event_type}, 发送者={user_id}")
                
                # 返回success表示已接收
                reply = TextReply(
                    content="",
                    message=message
                )
                
            else:
                # 其他类型的消息
                logger.info(f"收到非文本消息，类型: {message.type}, 发送者: {user_id}")
                
                # 返回success表示已接收
                reply = TextReply(
                    content="",
                    message=message
                )
            
            # 加密回复
            encrypted_reply = self.crypto.encrypt_message(
                reply.render(),
                nonce,
                timestamp
            )
            
            return encrypted_reply
            
        except Exception as e:
            logger.error(f"处理消息时出错: {e}")
            
            # 出错时也返回success，避免企业微信重试
            reply = TextReply(
                content="",
                message=message
            )
            
            encrypted_reply = self.crypto.encrypt_message(
                reply.render(),
                nonce,
                timestamp
            )
            
            return encrypted_reply
    
    async def _cleanup_task(self):
        """清理任务，定期清理频率限制数据"""
        while self.is_running:
            await asyncio.sleep(60)  # 每分钟清理一次
            self._cleanup_rate_limit()
    
    async def _start_server(self):
        """启动服务器内部实现"""
        # 解析主机地址显示信息
        if self.host == '::':
            display_host = ':: (所有IPv6地址，同时支持IPv4)'
            server_type = "双栈服务器 (IPv4 + IPv6)"
        elif self.host == '0.0.0.0':
            display_host = '0.0.0.0 (所有IPv4地址)'
            server_type = "标准服务器 (IPv4)"
        elif ':' in self.host:
            display_host = f'{self.host} (IPv6地址)'
            server_type = "IPv6服务器"
        else:
            display_host = f'{self.host} (IPv4地址)'
            server_type = "IPv4服务器"
        
        # 创建aiohttp应用
        self.app = web.Application(
            client_max_size=self.max_request_size
        )
        
        # 设置超时配置（通过中间件）
        @web.middleware
        async def timeout_middleware(request, handler):
            try:
                return await asyncio.wait_for(
                    handler(request),
                    timeout=self.request_timeout
                )
            except asyncio.TimeoutError:
                logger.error(f"请求超时: {request.remote}")
                return web.Response(status=408, text="Request Timeout")
        
        self.app.middlewares.append(timeout_middleware)
        
        # 添加路由
        self.app.router.add_get('/callback', self._handle_get)
        self.app.router.add_post('/callback', self._handle_post)
        if self.bot_server:
            self.app.router.add_get('/bot_callback', self.bot_server.handle_get)
            self.app.router.add_post('/bot_callback', self.bot_server.handle_post)
                
        # 添加健康检查
        self.app.router.add_get('/health', lambda request: web.Response(text='OK'))
        
        # 创建runner
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        
        # 创建site
        self.site = web.TCPSite(
            self.runner,
            self.host,
            self.port,
            backlog=self.max_connections
        )
        
        # 启动清理任务
        asyncio.create_task(self._cleanup_task())
        
        # 启动服务器
        await self.site.start()
        
        logger.info(f"""
========================================
    企业微信回调服务器启动
========================================

服务器配置：
服务器类型: {server_type}
监听地址: {display_host}
监听端口: {self.port}

性能配置：
最大连接数: {self.max_connections}
最大并发请求: {self.max_concurrent_requests}
请求超时: {self.request_timeout}秒
连接超时: {self.connection_timeout}秒

回调URL配置：
企业微信回调URL: http://你的域名或IP:{self.port}/callback
Token: {self.token[:10]}...
EncodingAESKey: {self.encoding_aes_key[:10]}...

按 Ctrl+C 停止服务器
""")
        
        self.is_running = True
        
        # 保持服务器运行
        while self.is_running:
            await asyncio.sleep(1)
    
    def _run_server_blocking(self):
        """阻塞式运行服务器（线程目标函数）"""
        try:
            # 运行异步服务器
            asyncio.run(self._start_server())
            
        except KeyboardInterrupt:
            logger.info("\n收到停止信号，正在关闭服务器...")
            self.stop()
        except Exception as e:
            logger.error(f"服务器运行出错: {e}")
            self.stop()
    
    def start(self):
        """启动服务器（在独立线程中运行，非阻塞）"""
        if self.is_running:
            logger.info("服务器已经在运行中")
            return
        
        if self.server_thread and self.server_thread.is_alive():
            logger.warning("服务器线程已经在运行")
            return
        
        # 创建并启动服务器线程
        self.server_thread = threading.Thread(
            target=self._run_server_blocking,
            name="WeChatServer-Thread",
            daemon=True  # 设置为守护线程，主程序退出时自动结束
        )
        self.server_thread.start()
        
        logger.info("服务器线程已启动（守护线程）")
    
    async def _stop_server(self):
        """停止服务器内部实现"""
        if self.site:
            await self.site.stop()
        
        if self.runner:
            await self.runner.cleanup()
        
        self.is_running = False
        logger.info("服务器已关闭")
    
    def stop(self):
        """停止服务器"""
        if not self.is_running:
            return
        
        # 运行异步停止
        asyncio.run(self._stop_server())
        
        # 等待线程结束（可选）
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=5)
            if self.server_thread.is_alive():
                logger.warning("服务器线程未在5秒内结束")
            else:
                logger.info("服务器线程已正常结束")


# def run_wechat_server():
#     """运行企业微信服务器"""
#     server = WeChatServer()
#     server.start()


if __name__ == "__main__":
    # 测试服务器
    print("测试高性能企业微信服务器...")
    
    # 设置测试配置
    os.environ["WECHAT_WORK_CORPID"] = "test_corpid"
    os.environ["WECHAT_WORK_CALLBACK_TOKEN"] = "test_token"
    os.environ["WECHAT_WORK_ENCODING_AES_KEY"] = "test_aes_key"
    
    # 使用本地地址和测试端口
    os.environ["SERVER_HOST"] = "127.0.0.1"
    os.environ["SERVER_PORT"] = "8888"
    
    # 设置性能参数
    os.environ["MAX_CONNECTIONS"] = "100"
    os.environ["MAX_CONCURRENT_REQUESTS"] = "50"
    os.environ["REQUEST_TIMEOUT"] = "30"
    os.environ["CONNECTION_TIMEOUT"] = "10"
    os.environ["MAX_REQUEST_SIZE"] = "10485760"
    os.environ["RATE_LIMIT_WINDOW"] = "60"
    os.environ["RATE_LIMIT_MAX"] = "100"
    
    # 注意：测试代码需要UserManager实例，但这里只是演示
    # 在实际使用中，应该从main.py传递UserManager实例
    print("注意：测试代码需要UserManager实例，跳过实际启动")
    print("要测试服务器，请运行main.py")
    
    # 如果要实际测试，可以取消下面的注释并导入UserManager
    # from .Users import UserManager
    # user_mgr = UserManager()
    # server = WeChatServer(user_mgr)
    # server.start()
