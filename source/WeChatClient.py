#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
企业微信客户端模块
用于发送消息给企业微信用户
"""

import time
import requests
import os
import mimetypes
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path


import logging
logger = logging.getLogger(__name__)

from .Utils import get_config_instance
config = get_config_instance()


class WeChatClient:
    """企业微信客户端（简化版）"""
    
    def __init__(self):
        """初始化企业微信客户端"""
        self.logger = logger
        
        # 获取企业微信配置
        global config
        self.corpid = config.wechat_work_corpid
        self.corpsecret = config.wechat_work_corpsecret
        self.agentid = config.wechat_work_agentid
        
        # access_token缓存
        self.access_token: Optional[str] = None
        self.token_expire_time: Optional[datetime] = None
        
        # API基础URL
        self.base_url = "https://qyapi.weixin.qq.com/cgi-bin"
        
        self.logger.info(f"wechatclient::start")
    
    def _detect_media_type(self, file_path: str) -> Optional[str]:
        """
        根据文件扩展名检测媒体类型
        
        Args:
            file_path: 文件路径
            
        Returns:
            媒体类型 (image/voice/video/file) 或 None
        """
        path = Path(file_path)
        ext = path.suffix.lower()
        
        # 图片类型
        image_exts = {'.jpg', '.jpeg', '.png', '.bmp', '.gif'}
        # 语音类型 (企业微信仅支持AMR格式)
        voice_exts = {'.amr'}
        # 视频类型
        video_exts = {'.mp4', '.avi', '.mov', '.wmv', '.flv'}
        
        if ext in image_exts:
            return 'image'
        elif ext in voice_exts:
            return 'voice'
        elif ext in video_exts:
            return 'video'
        else:
            # 其他文件都作为普通文件处理
            return 'file'
    
    def _validate_file_size(self, file_path: str, media_type: str) -> Tuple[bool, str]:
        """
        验证文件大小是否符合企业微信限制
        
        Args:
            file_path: 文件路径
            media_type: 媒体类型
            
        Returns:
            (是否有效, 错误信息)
        """
        try:
            file_size = os.path.getsize(file_path)
            
            # 企业微信文件大小限制（字节）
            limits = {
                'image': 10 * 1024 * 1024,  # 10MB
                'voice': 2 * 1024 * 1024,   # 2MB
                'video': 10 * 1024 * 1024,  # 10MB
                'file': 20 * 1024 * 1024    # 20MB
            }
            
            if media_type not in limits:
                return False, f"不支持的媒体类型: {media_type}"
            
            limit = limits[media_type]
            
            if file_size > limit:
                size_mb = file_size / (1024 * 1024)
                limit_mb = limit / (1024 * 1024)
                return False, f"文件大小({size_mb:.2f}MB)超过{media_type}类型限制({limit_mb}MB)"
            
            # 所有文件必须大于5字节
            if file_size <= 5:
                return False, "文件大小必须大于5字节"
            
            return True, ""
            
        except Exception as e:
            return False, f"检查文件大小时出错: {e}"
    
    def _get_access_token(self) -> Optional[str]:
        """获取access_token（带简单缓存）"""
        try:
            # 检查token是否有效（简单缓存：如果存在且未过期5分钟，则使用）
            if self.access_token and self.token_expire_time:
                if datetime.now() < self.token_expire_time - timedelta(minutes=5):
                    self.logger.debug("使用缓存的access_token")
                    return self.access_token
            
            # 获取新的access_token
            self.logger.debug("获取新的access_token...")
            url = f"{self.base_url}/gettoken"
            params = {
                "corpid": self.corpid,
                "corpsecret": self.corpsecret
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("errcode") != 0:
                self.logger.error(f"获取access_token失败: {result}")
                return None
            
            self.access_token = result["access_token"]
            # 设置过期时间（企业微信token有效期为7200秒，我们设置为7000秒）
            self.token_expire_time = datetime.now() + timedelta(seconds=7000)
            
            self.logger.info("成功获取access_token")
            return self.access_token
            
        except Exception as e:
            self.logger.error(f"获取access_token时出错: {e}")
            return None
    
    def upload_media(self, file_path: str, media_type: Optional[str] = None) -> Optional[str]:
        """
        通用 上传文件到企业微信服务器，支持各种文件类型
        
        Args:
            file_path: 本地文件路径
            media_type: 文件类型（image/voice/video/file），如果为None则自动检测
            
        Returns:
            media_id 或 None（上传失败）
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                self.logger.error(f"文件不存在: {file_path}")
                return None
            
            # 自动检测媒体类型
            if media_type is None:
                media_type = self._detect_media_type(file_path)
                self.logger.debug(f"自动检测到媒体类型: {media_type}")
            
            if media_type not in ['image', 'voice', 'video', 'file']:
                self.logger.error(f"不支持的媒体类型: {media_type}")
                return None
            
            # 验证文件大小
            is_valid, error_msg = self._validate_file_size(file_path, media_type)
            if not is_valid:
                self.logger.error(f"文件大小验证失败: {error_msg}")
                return None
            
            # 获取access_token
            access_token = self._get_access_token()
            if not access_token:
                self.logger.error("无法获取access_token，文件上传失败")
                return None
            
            # 准备上传
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            
            # 获取文件MIME类型
            mime_type, _ = mimetypes.guess_type(file_path)
            if not mime_type:
                mime_type = 'application/octet-stream'
            
            self.logger.info(f"开始上传文件: {file_name} ({file_size}字节), 类型: {media_type}")
            
            # 构建上传URL
            url = f"{self.base_url}/media/upload"
            params = {
                "access_token": access_token,
                "type": media_type
            }
            
            # 使用multipart/form-data上传文件
            with open(file_path, 'rb') as f:
                files = {
                    'media': (file_name, f, mime_type)
                }
                
                # 添加额外的文件信息（根据企业微信API要求）
                # 注意：requests会自动处理multipart/form-data
                response = requests.post(
                    url,
                    params=params,
                    files=files,
                    timeout=30  # 文件上传可能需要更长时间
                )
            
            response.raise_for_status()
            result = response.json()
            
            if result.get("errcode") == 0:
                media_id = result.get("media_id")
                created_at = result.get("created_at")
                self.logger.info(f"文件上传成功: media_id={media_id}, created_at={created_at}")
                return media_id
            else:
                self.logger.error(f"文件上传失败: {result}")
                return None
                
        except Exception as e:
            self.logger.error(f"上传文件时出错: {e}")
            return None
    
    def send_file(self, user_id: str, file_path: str, media_type: Optional[str] = None) -> bool:
        """
        发送文件给指定用户
        
        Args:
            user_id: 接收用户ID
            file_path: 本地文件路径
            media_type: 文件类型，如果为None则自动检测
            
        Returns:
            是否发送成功
        """
        try:
            # 先上传文件获取media_id
            self.logger.info(f"开始上传文件: {file_path}")
            media_id = self.upload_media(file_path, media_type)
            
            if not media_id:
                self.logger.error("文件上传失败，无法发送文件消息")
                return False
            
            # 使用media_id发送文件消息
            self.logger.info(f"文件上传成功，开始发送文件消息给用户 {user_id}")
            return self.send_file_message(user_id, media_id)
            
        except Exception as e:
            self.logger.error(f"发送文件时出错: {e}")
            return False
    
    def send_file_message(self, user_id: str, media_id: str) -> bool:
        """
        使用已有的media_id发送文件消息

        Args:
            user_id: 接收用户ID
            media_id: 通过upload_media获取的媒体ID

        Returns:
            是否发送成功
        """
        try:
            # 获取access_token
            access_token = self._get_access_token()
            if not access_token:
                self.logger.error("无法获取access_token，消息发送失败")
                return False

            # 构建文件消息数据（根据企业微信API文档）
            message_data = {
                "touser": user_id,
                "msgtype": "file",
                "agentid": int(self.agentid),
                "file": {
                    "media_id": media_id
                },
                "safe": 0,  # 非保密消息
                "enable_duplicate_check": 0,  # 不开启重复消息检查
                "duplicate_check_interval": 1800  # 重复消息检查时间间隔
            }

            self.logger.info(f"准备发送文件消息给用户 {user_id}，media_id: {media_id}")

            # 发送消息
            url = f"{self.base_url}/message/send"
            params = {"access_token": access_token}

            response = requests.post(
                url,
                params=params,
                json=message_data,
                timeout=10
            )
            response.raise_for_status()

            result = response.json()

            if result.get("errcode") == 0:
                self.logger.info(f"成功发送文件消息给用户 {user_id}")
                return True
            else:
                self.logger.error(f"发送文件消息失败: {result}")
                return False

        except Exception as e:
            self.logger.error(f"发送文件消息时出错: {e}")
            return False

    def send_image_message(self, user_id: str, media_id: str) -> bool:
        """
        使用已有的media_id发送图片消息

        Args:
            user_id: 接收用户ID
            media_id: 通过upload_media获取的媒体ID

        Returns:
            是否发送成功
        """
        try:
            # 获取access_token
            access_token = self._get_access_token()
            if not access_token:
                self.logger.error("无法获取access_token，消息发送失败")
                return False

            # 构建图片消息数据（根据企业微信API文档）
            message_data = {
                "touser": user_id,
                "msgtype": "image",
                "agentid": int(self.agentid),
                "image": {
                    "media_id": media_id
                },
                "safe": 0,  # 非保密消息
                "enable_duplicate_check": 0,  # 不开启重复消息检查
                "duplicate_check_interval": 1800  # 重复消息检查时间间隔
            }

            self.logger.info(f"准备发送图片消息给用户 {user_id}，media_id: {media_id}")

            # 发送消息
            url = f"{self.base_url}/message/send"
            params = {"access_token": access_token}

            response = requests.post(
                url,
                params=params,
                json=message_data,
                timeout=10
            )
            response.raise_for_status()

            result = response.json()

            if result.get("errcode") == 0:
                self.logger.info(f"成功发送图片消息给用户 {user_id}")
                return True
            else:
                self.logger.error(f"发送图片消息失败: {result}")
                return False

        except Exception as e:
            self.logger.error(f"发送图片消息时出错: {e}")
            return False

    def send_image(self, user_id: str, file_path: str, media_type: Optional[str] = 'image') -> bool:
        """
        发送图片给指定用户

        Args:
            user_id: 接收用户ID
            file_path: 本地文件路径
            media_type: 文件类型，对于图片应为'image'

        Returns:
            是否发送成功
        """
        try:
            # 先上传图片获取media_id
            self.logger.info(f"开始上传图片: {file_path}")
            media_id = self.upload_media(file_path, media_type)

            if not media_id:
                self.logger.error("图片上传失败，无法发送图片消息")
                return False

            # 使用media_id发送图片消息
            self.logger.info(f"图片上传成功，开始发送图片消息给用户 {user_id}")
            return self.send_image_message(user_id, media_id)

        except Exception as e:
            self.logger.error(f"发送图片时出错: {e}")
            return False

    def send_text_message(self, user_id: str, content: str) -> bool:
        """发送文本消息给指定用户"""
        try:
            # 获取access_token
            access_token = self._get_access_token()
            if not access_token:
                self.logger.error("无法获取access_token，消息发送失败")
                return False
            
            # 构建消息数据
            message_data = {
                "touser": user_id,
                "msgtype": "text",
                "agentid": int(self.agentid),
                "text": {
                    "content": content
                },
                "safe": 0,  # 非保密消息
                "enable_id_trans": 0,  # 不开启id转译
                "enable_duplicate_check": 0,  # 不开启重复消息检查
                "duplicate_check_interval": 1800  # 重复消息检查时间间隔
            }
            
            self.logger.info(f"准备发送消息给用户 {user_id}，内容长度: {len(content)}")
            
            # 发送消息
            url = f"{self.base_url}/message/send"
            params = {"access_token": access_token}
            
            response = requests.post(
                url,
                params=params,
                json=message_data,
                timeout=10
            )
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("errcode") == 0:
                self.logger.info(f"成功发送消息给用户 {user_id}")
                return True
            else:
                self.logger.error(f"发送消息失败: {result}")
                return False
                
        except Exception as e:
            self.logger.error(f"发送消息时出错: {e}")
            return False
    
    def send_text_messages(self, user_id: str, segments: list) -> bool:
        """发送多条消息（分段发送）"""
        if not segments:
            self.logger.warning(f"用户 {user_id} 没有消息需要发送")
            return True
        
        self.logger.info(f"开始发送 {len(segments)} 段消息给用户 {user_id}")
        
        success_count = 0
        fail_count = 0
        
        for i, segment in enumerate(segments, 1):
            self.logger.debug(f"发送第 {i}/{len(segments)} 段消息，长度: {len(segment)}")
            
            success = self.send_text_message(user_id, segment)
            
            if success:
                success_count += 1
                # 简单延迟，避免发送过快（虽然不需要考虑频率限制，但保持友好）
                if i < len(segments):
                    time.sleep(0.5)
            else:
                fail_count += 1
                self.logger.error(f"第 {i} 段消息发送失败")
        
        if fail_count == 0:
            self.logger.info(f"所有 {success_count} 段消息发送成功")
            return True
        else:
            self.logger.error(f"消息发送完成，成功: {success_count}, 失败: {fail_count}")
            return fail_count == 0  # 如果全部失败才返回False，部分成功也算成功
    
    def test_connection(self) -> bool:
        """测试连接是否正常"""
        try:
            access_token = self._get_access_token()
            if access_token:
                self.logger.info("企业微信连接测试成功")
                return True
            else:
                self.logger.error("企业微信连接测试失败")
                return False
        except Exception as e:
            self.logger.error(f"企业微信连接测试出错: {e}")
            return False


# 全局企业微信客户端实例
_wechat_client_instance: Optional[WeChatClient] = None


def get_wechat_client() -> WeChatClient:
    """获取企业微信客户端实例（单例模式）"""
    global _wechat_client_instance
    
    if _wechat_client_instance is None:
        _wechat_client_instance = WeChatClient()
    
    return _wechat_client_instance



if __name__ == "__main__":
    # 测试企业微信客户端
    import os
    
    print("测试企业微信客户端...")
    
    # 设置测试配置
    os.environ["WECHAT_WORK_CORPID"] = "test_corpid"
    os.environ["WECHAT_WORK_CORPSECRET"] = "test_secret"
    os.environ["WECHAT_WORK_AGENTID"] = "test_agentid"
    
    client = get_wechat_client()
    
    # 测试连接
    print("测试连接...")
    connected = client.test_connection()
    print(f"连接测试: {'成功' if connected else '失败'}")
    
    # 测试发送消息（需要真实的secret才能实际发送）
    # print("测试发送消息...")
    # success = client.send_text_message("test_user", "这是一条测试消息")
    # print(f"消息发送: {'成功' if success else '失败'}")
    
    # 测试文件上传功能（示例代码）
    print("\n文件上传功能测试示例:")
    print("1. 上传文件: media_id = client.upload_media('path/to/file.txt', 'file')")
    print("2. 发送文件消息: success = client.send_file_message('user_id', media_id)")
    print("3. 直接发送文件: success = client.send_file('user_id', 'path/to/file.txt')")
    
    print("\n注意：")
    print("- 需要真实的企业微信配置才能实际测试")
    print("- 文件类型支持: image, voice, video, file")
    print("- 文件大小限制:")
    print("  - 图片(image): 10MB")
    print("  - 语音(voice): 2MB (仅支持AMR格式)")
    print("  - 视频(video): 10MB")
    print("  - 普通文件(file): 20MB")
    
    print("\n测试完成")
