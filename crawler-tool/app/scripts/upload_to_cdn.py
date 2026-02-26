#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片CDN迁移脚本
将数据库中存储的外部图片URL下载并上传到指定的CDN（如阿里云OSS），
然后更新数据库中的URL。
"""

import os
import sys
import json
import time
import logging
import requests
import hashlib
import mimetypes
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Tuple

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from base.database import db

# ==================== 配置区域 ====================

# CDN配置 (请在此处填写您的配置)
CDN_CONFIG = {
    # 类型: 'aliyun' (阿里云OSS) 或 's3' (AWS S3及兼容存储)
    'type': 'aliyun',
    
    # 您的CDN域名 (用于替换数据库中的URL)
    'cdn_domain': 'https://your-bucket.oss-cn-shanghai.aliyuncs.com',
    
    # 阿里云 OSS 配置
    'aliyun': {
        'access_key_id': 'YOUR_ACCESS_KEY_ID',
        'access_key_secret': 'YOUR_ACCESS_KEY_SECRET',
        'endpoint': 'http://oss-cn-shanghai.aliyuncs.com',
        'bucket_name': 'YOUR_BUCKET_NAME',
    },
    
    # AWS S3 配置 (如果使用S3)
    's3': {
        'aws_access_key_id': 'YOUR_ACCESS_KEY',
        'aws_secret_access_key': 'YOUR_SECRET_KEY',
        'region_name': 'us-east-1',
        'bucket_name': 'YOUR_BUCKET_NAME',
    },
    
    # 图片存储路径前缀
    'path_prefix': 'images/restaurants/',
}

# 脚本运行配置
RUN_CONFIG = {
    'batch_size': 100,        # 每次从数据库读取的记录数
    'max_workers': 10,        # 并发上传线程数
    'timeout': 15,            # 下载超时时间(秒)
    'retry_count': 3,         # 下载重试次数
    'dry_run': False,         # True=仅模拟不上传不更新数据库
}

# ==================== 日志配置 ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('cdn_upload.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ==================== CDN上传类 ====================

class CDNUploader:
    def __init__(self, config):
        self.config = config
        self.type = config.get('type', 'aliyun')
        self.cdn_domain = config.get('cdn_domain', '').rstrip('/')
        self.bucket = None
        self._init_client()

    def _init_client(self):
        """初始化存储客户端"""
        try:
            if self.type == 'aliyun':
                import oss2
                cfg = self.config['aliyun']
                auth = oss2.Auth(cfg['access_key_id'], cfg['access_key_secret'])
                self.bucket = oss2.Bucket(auth, cfg['endpoint'], cfg['bucket_name'])
                logger.info("阿里云OSS客户端初始化成功")
                
            elif self.type == 's3':
                import boto3
                cfg = self.config['s3']
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=cfg['aws_access_key_id'],
                    aws_secret_access_key=cfg['aws_secret_access_key'],
                    region_name=cfg['region_name']
                )
                self.bucket_name = cfg['bucket_name']
                logger.info("AWS S3客户端初始化成功")
            else:
                logger.error(f"不支持的CDN类型: {self.type}")
        except ImportError as e:
            logger.error(f"缺少必要的库: {e}. 请运行: pip install oss2 boto3")
            sys.exit(1)
        except Exception as e:
            logger.error(f"客户端初始化失败: {e}")
            sys.exit(1)

    def upload_data(self, data: bytes, filename: str, content_type: str = None) -> Optional[str]:
        """上传二进制数据到CDN"""
        key = f"{self.config['path_prefix'].rstrip('/')}/{filename}"
        
        try:
            if RUN_CONFIG['dry_run']:
                logger.info(f"[Dry Run] Uploading {len(data)} bytes to {key}")
                return f"{self.cdn_domain}/{key}"

            if self.type == 'aliyun':
                headers = {'Content-Type': content_type} if content_type else {}
                self.bucket.put_object(key, data, headers=headers)
            
            elif self.type == 's3':
                extra_args = {'ContentType': content_type} if content_type else {}
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=data,
                    ExtraArgs=extra_args
                )
            
            return f"{self.cdn_domain}/{key}"
            
        except Exception as e:
            logger.error(f"上传失败 {key}: {e}")
            return None

    def exists(self, url: str) -> bool:
        """检查URL是否属于当前CDN"""
        return self.cdn_domain in url

# ==================== 核心逻辑 ====================

def calculate_md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()

def download_image(url: str) -> Tuple[Optional[bytes], Optional[str]]:
    """下载图片，返回二进制数据和Content-Type"""
    for i in range(RUN_CONFIG['retry_count']):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            resp = requests.get(url, headers=headers, timeout=RUN_CONFIG['timeout'])
            if resp.status_code == 200:
                return resp.content, resp.headers.get('Content-Type')
        except Exception as e:
            if i == RUN_CONFIG['retry_count'] - 1:
                logger.warning(f"下载失败 {url}: {e}")
            time.sleep(1)
    return None, None

def process_single_image(url: str, uploader: CDNUploader) -> str:
    """处理单张图片：检查->下载->上传"""
    # 1. 如果已经是CDN链接，直接返回
    if uploader.exists(url):
        return url
        
    # 2. 如果是无效链接，保持原样（或者返回None以删除）
    if not url or not url.startswith('http'):
        return url

    # 3. 下载图片
    data, content_type = download_image(url)
    if not data:
        return url # 下载失败保持原样
        
    # 4. 生成新文件名 (MD5 + 扩展名)
    ext = mimetypes.guess_extension(content_type) or '.jpg'
    if ext == '.jpe': ext = '.jpg'
    filename = f"{calculate_md5(data)}{ext}"
    
    # 5. 上传
    new_url = uploader.upload_data(data, filename, content_type)
    
    if new_url:
        logger.info(f"迁移成功: ...{url[-20:]} -> ...{new_url[-20:]}")
        return new_url
    else:
        return url

def process_batch(rows, uploader: CDNUploader):
    """批量处理数据库记录"""
    updates = []
    
    for row in rows:
        tweet_id = row['id']
        img_json = row['tweets_img']
        
        if not img_json:
            continue
            
        try:
            # 解析图片列表
            if isinstance(img_json, str):
                images = json.loads(img_json)
            else:
                images = img_json
                
            if not isinstance(images, list):
                continue
                
            # 并发处理该条记录的所有图片
            new_images = []
            has_changes = False
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_url = {executor.submit(process_single_image, url, uploader): url for url in images}
                
                # 保持原有顺序
                results = {}
                for future in as_completed(future_to_url):
                    orig_url = future_to_url[future]
                    try:
                        new_url = future.result()
                        results[orig_url] = new_url
                        if new_url != orig_url:
                            has_changes = True
                    except Exception as e:
                        logger.error(f"处理图片出错: {e}")
                        results[orig_url] = orig_url
                
                # 按原顺序重组
                new_images = [results.get(url, url) for url in images]

            # 如果有变化，准备更新
            if has_changes:
                new_json = json.dumps(new_images, ensure_ascii=False)
                updates.append({
                    'id': tweet_id,
                    'tweets_img': new_json
                })
                
        except Exception as e:
            logger.error(f"处理记录 ID={tweet_id} 失败: {e}")

    # 批量更新数据库
    if updates and not RUN_CONFIG['dry_run']:
        update_db(updates)

def update_db(updates: List[Dict]):
    """更新数据库"""
    if not updates:
        return
        
    try:
        from sqlalchemy import text
        # 使用单个事务批量更新
        with db.engine.connect() as conn:
            for item in updates:
                sql = text("UPDATE tweets SET tweets_img = :tweets_img WHERE id = :id")
                conn.execute(sql, item)
            conn.commit()
        logger.info(f"✅ 成功更新数据库 {len(updates)} 条记录")
    except Exception as e:
        logger.error(f"❌ 数据库更新失败: {e}")

def main():
    logger.info("开始执行图片迁移脚本...")
    
    # 初始化上传器
    uploader = CDNUploader(CDN_CONFIG)
    
    # 获取总记录数
    count_sql = "SELECT COUNT(*) as cnt FROM tweets WHERE tweets_img IS NOT NULL AND tweets_img != '[]' AND tweets_img != ''"
    df_cnt = db.execute_query(count_sql)
    total_records = df_cnt.iloc[0]['cnt']
    logger.info(f"发现 {total_records} 条包含图片的记录")
    
    offset = 0
    processed = 0
    
    while True:
        # 分页查询
        sql = f"""
            SELECT id, tweets_img 
            FROM tweets 
            WHERE tweets_img IS NOT NULL AND tweets_img != '[]' AND tweets_img != ''
            LIMIT {RUN_CONFIG['batch_size']} OFFSET {offset}
        """
        
        df = db.execute_query(sql)
        if df.empty:
            break
            
        batch_rows = df.to_dict('records')
        logger.info(f"正在处理批次: {offset} - {offset + len(batch_rows)} / {total_records}")
        
        process_batch(batch_rows, uploader)
        
        offset += len(batch_rows)
        processed += len(batch_rows)
        
        # 防止过快
        time.sleep(1)

    logger.info("所有处理完成！")

if __name__ == '__main__':
    # 检查依赖
    try:
        import oss2
    except ImportError:
        logger.warning("未检测到 'oss2' 库，如果使用阿里云OSS请安装: pip install oss2")
    
    try:
        import boto3
    except ImportError:
        logger.warning("未检测到 'boto3' 库，如果使用S3请安装: pip install boto3")

    main()
