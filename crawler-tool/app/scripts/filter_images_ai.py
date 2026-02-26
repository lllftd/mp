#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片质量AI筛选脚本
使用视觉大模型 (VLM) 智能判断图片是否适合作为餐厅展示图。
可以过滤掉：二维码、模糊图、无关截图、表情包、纯文字图、非餐厅/食物相关的图片。
"""

import os
import sys
import json
import time
import base64
import logging
import argparse
import requests
from io import BytesIO
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from base.database import db
from base.config import Config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('image_audit.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ==================== 视觉模型配置 ====================

class VisionAuditor:
    def __init__(self, api_base: str, api_key: str, model: str):
        self.api_base = api_base.rstrip('/')
        self.api_key = api_key
        self.model = model
        
    def _encode_image(self, image_content: bytes) -> str:
        """将图片内容转换为Base64字符串"""
        return base64.b64encode(image_content).decode('utf-8')

    def check_image(self, image_url: str, content: bytes = None) -> Tuple[bool, str, str]:
        """
        使用AI检查图片
        Returns: (is_valid, reason, category)
        """
        try:
            # 如果未提供二进制内容，则下载
            if not content:
                try:
                    resp = requests.get(image_url, timeout=10)
                    if resp.status_code != 200:
                        return False, f"下载失败 HTTP {resp.status_code}", "download_error"
                    content = resp.content
                except Exception as e:
                    return False, f"下载异常: {e}", "download_error"

            # 转换为Base64
            base64_image = self._encode_image(content)
            
            # 构建Prompt
            # 注意：不同的模型可能对Prompt的敏感度不同，这里使用通用的结构
            prompt = """请作为一名专业的餐厅内容审核员，分析这张图片是否适合展示在"餐厅推荐/美食探店"的帖子中。

判断标准：
1. [合适]：
   - 诱人的美食特写
   - 清晰的餐厅环境/内饰
   - 餐厅外观/门头
   - 菜单(清晰可见)
   - 正在享用美食的人物(非自拍)
2. [不合适]：
   - 二维码/条形码
   - 截图(聊天记录/地图/大段文字)
   - 模糊不清/极低画质
   - 纯表情包/梗图
   - 与餐厅完全无关的自拍/人像
   - 不雅或令人不适的内容
   - 比例严重失调（如被拉伸、压扁）
   - 塑料感过强/过度美颜/AI生成的假图
   - 看起来非常不自然或令人倒胃口的食物图

请返回JSON格式：
{
    "valid": true/false,
    "category": "美食/环境/菜单/二维码/截图/模糊/比例失调/塑料感/其他",
    "reason": "简短的判断理由"
}"""

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }

            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 300,
                "temperature": 0.1
            }

            # 兼容 Ollama 的 URL 格式 (chat/completions)
            url = f"{self.api_base}/chat/completions"
            
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            
            if response.status_code != 200:
                logger.error(f"API请求失败: {response.status_code} - {response.text[:200]}")
                return True, "API_ERROR", "unknown" # API错误时默认保留，避免误删

            result = response.json()
            content_str = result['choices'][0]['message']['content']
            
            # 解析JSON
            # 有些模型可能返回 ```json ... ``` 格式
            content_str = content_str.replace('```json', '').replace('```', '').strip()
            
            try:
                data = json.loads(content_str)
                return data.get('valid', False), data.get('reason', '无理由'), data.get('category', 'unknown')
            except json.JSONDecodeError:
                # 如果模型没有返回JSON，尝试简单的文本判断
                lower_content = content_str.lower()
                if "true" in lower_content or "合适" in lower_content or "valid" in lower_content:
                    return True, content_str[:50], "parsed_text"
                return False, content_str[:50], "parsed_text_invalid"

        except Exception as e:
            logger.error(f"处理图片出错: {e}")
            return True, f"EXCEPTION: {e}", "error" # 出错默认保留

# ==================== 主逻辑 ====================

def process_audit(
    auditor: VisionAuditor,
    limit: int = 100,
    offset: int = 0,
    dry_run: bool = False,
    batch_size: int = 10,
    start_time: str = None
):
    """
    批量审核图片
    """
    # 构建查询
    sql = "SELECT id, tweets_title, tweets_img FROM tweets WHERE tweets_img IS NOT NULL AND tweets_img != '' AND tweets_img != '[]'"
    params = {}
    
    if start_time:
        sql += " AND create_time >= :start_time"
        params['start_time'] = start_time
        
    sql += " ORDER BY id DESC" # 从最新的开始查
    
    if limit:
        sql += f" LIMIT {limit} OFFSET {offset}"
        
    logger.info("正在查询数据库...")
    df = db.execute_query(sql, params)
    
    if df.empty:
        logger.info("没有找到需要处理的记录")
        return

    logger.info(f"找到 {len(df)} 条记录，开始AI审核...")
    
    total_images_checked = 0
    total_images_removed = 0
    records_updated = 0
    
    for idx, row in df.iterrows():
        tweet_id = row['id']
        title = row['tweets_title']
        img_json = row['tweets_img']
        
        try:
            if isinstance(img_json, str):
                images = json.loads(img_json)
            else:
                images = img_json
                
            if not images or not isinstance(images, list):
                continue
                
            valid_images = []
            has_changes = False
            
            logger.info(f"\n[{idx+1}/{len(df)}] 审核餐厅: {title} (ID: {tweet_id}) - {len(images)} 张图片")
            
            # 这里的并发是针对单条记录内的多张图片，还是单线程处理比较稳妥，避免API限流
            # 如果图片很多，可以使用线程池
            for img_url in images:
                total_images_checked += 1
                
                # 简单过滤：非HTTP链接直接跳过
                if not img_url.startswith('http'):
                    continue
                    
                # 调用AI审核
                is_valid, reason, category = auditor.check_image(img_url)
                
                if is_valid:
                    valid_images.append(img_url)
                    logger.info(f"  ✅ [通过] {category}: {reason[:30]}...")
                else:
                    has_changes = True
                    total_images_removed += 1
                    logger.warning(f"  ❌ [删除] {category}: {reason[:50]}...")
            
            # 如果所有图片都被删了，至少保留一张（或者标记记录）
            # 这里策略是：如果还有有效图片，就更新；如果没有了，暂时保留原样或清空
            # 建议：如果只剩0张，可能需要人工介入，或者保留第一张原图
            
            if has_changes:
                if not valid_images:
                    logger.warning("  ⚠️ 该餐厅所有图片均被判定为不合格，将清空图片列表。")
                
                if not dry_run:
                    new_json = json.dumps(valid_images, ensure_ascii=False)
                    db.execute_update(
                        "UPDATE tweets SET tweets_img = :img WHERE id = :id",
                        {'img': new_json, 'id': tweet_id}
                    )
                    records_updated += 1
                    logger.info(f"  💾 数据库已更新: {len(images)} -> {len(valid_images)} 张")
                else:
                    logger.info(f"  [试运行] 应该更新: {len(images)} -> {len(valid_images)} 张")
            else:
                logger.info("  ✨ 所有图片均合格，无需更新")
                
        except Exception as e:
            logger.error(f"处理记录 {tweet_id} 失败: {e}")
            continue

    logger.info("="*50)
    logger.info(f"审核完成 Summary:")
    logger.info(f"检查图片总数: {total_images_checked}")
    logger.info(f"移除图片总数: {total_images_removed}")
    logger.info(f"更新记录条数: {records_updated}")


def main():
    parser = argparse.ArgumentParser(description='使用AI视觉模型筛选高质量图片')
    
    # 默认使用 Ollama 本地服务
    parser.add_argument('--api-base', type=str, default='http://localhost:11434/v1', help='API基础地址 (默认: Ollama本地)')
    parser.add_argument('--api-key', type=str, default='ollama', help='API Key (Ollama随意，OpenAI/DeepSeek需填)')
    parser.add_argument('--model', type=str, default='llava', help='使用的视觉模型名称 (如 llava, moondream, gpt-4o)')
    
    parser.add_argument('--limit', type=int, default=10, help='处理记录数量限制')
    parser.add_argument('--offset', type=int, default=0, help='起始偏移量')
    parser.add_argument('--dry-run', action='store_true', help='试运行模式 (不修改数据库)')
    parser.add_argument('--start-time', type=str, help='只处理此时间之后的记录 (YYYY-MM-DD HH:MM:SS)')
    
    args = parser.parse_args()
    
    # 检查 DeepSeek 误用情况
    if 'deepseek' in args.api_base or 'deepseek' in args.model:
        logger.warning("⚠️  注意: DeepSeek (chat) 模型通常不支持图片输入。")
        logger.warning("   如果你的 DeepSeek API 支持 Vision，请忽略此警告。")
        # 暂停一下让用户看到
        time.sleep(2)

    # 自动识别通义千问配置
    if 'dashscope' in args.api_base or args.model.startswith('qwen'):
        logger.info("检测到通义千问配置，自动调整API参数...")
        # 如果是通义千问，默认使用兼容OpenAI的endpoint
        if args.api_base == 'http://localhost:11434/v1': # 如果是默认值，则替换
            args.api_base = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        if args.model == 'llava': # 如果是默认值，则替换为qwen-vl
            args.model = "qwen-vl-plus"

    auditor = VisionAuditor(
        api_base=args.api_base,
        api_key=args.api_key,
        model=args.model
    )
    
    try:
        process_audit(
            auditor, 
            limit=args.limit, 
            offset=args.offset, 
            dry_run=args.dry_run,
            start_time=args.start_time
        )
    except KeyboardInterrupt:
        logger.info("用户停止操作")
    except Exception as e:
        logger.error(f"发生未捕获异常: {e}", exc_info=True)

if __name__ == '__main__':
    main()
