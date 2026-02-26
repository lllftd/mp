#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户头像填充脚本
为没有头像的用户自动生成多样化的随机头像。
"""

import os
import sys
import random
import logging
import argparse
import time
from typing import List

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from base.database import db
from sqlalchemy import text

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 头像风格配置 (DiceBear API)
# 文档: https://www.dicebear.com/styles/
AVATAR_STYLES = [
    'adventurer',     # 冒险家风格 (推荐)
    'adventurer-neutral',
    'avataaars',      # 卡通风格
    'big-ears',       # 大耳朵风格
    'big-smile',      # 大笑风格
    'bottts',         # 机器人
    'croodles',       # 涂鸦风格
    'fun-emoji',      # Emoji风格
    'icons',          # 图标风格
    'identicon',      # 几何图形
    'lorelei',        # 唯美风格 (推荐)
    'micah',          # 极简线条 (推荐)
    'miniavs',        # 迷你头像
    'open-peeps',     # 手绘风格 (推荐)
    'personas',       # 扁平化风格
    'pixel-art',      # 像素风
]

# 也可以使用 Unsplash 的随机人像 (更真实，但链接可能会变)
REALISTIC_AVATARS = [
    "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=200&h=200&fit=crop",
    "https://images.unsplash.com/photo-1527980965255-d3b416303d12?w=200&h=200&fit=crop",
    "https://images.unsplash.com/photo-1580489944761-15a19d654956?w=200&h=200&fit=crop",
    "https://images.unsplash.com/photo-1633332755192-727a05c4013d?w=200&h=200&fit=crop",
    "https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=200&h=200&fit=crop",
    "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=200&h=200&fit=crop",
    "https://images.unsplash.com/photo-1628157588553-5eeea00af15c?w=200&h=200&fit=crop",
    "https://images.unsplash.com/photo-1570295999919-56ceb5ecca61?w=200&h=200&fit=crop",
    "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=200&h=200&fit=crop",
    "https://images.unsplash.com/photo-1531123897727-8f129e1688ce?w=200&h=200&fit=crop"
]

def generate_avatar_url(seed: str, style: str = None) -> str:
    """
    生成头像 URL
    """
    if not style:
        style = random.choice(AVATAR_STYLES)
    
    # 随机背景色
    bg_color = random.choice(['b6e3f4', 'c0aede', 'd1d4f9', 'ffd5dc', 'ffdfbf'])
    
    return f"https://api.dicebear.com/7.x/{style}/svg?seed={seed}&backgroundColor={bg_color}"

def fill_avatars(limit: int = 1000, style: str = None, use_realistic: bool = False):
    """
    填充头像
    """
    # 1. 查找没有头像的用户
    sql = """
        SELECT id, nick_name, open_id 
        FROM client_user 
        WHERE (avatar IS NULL OR avatar = '') 
        LIMIT :limit
    """
    
    logger.info("查找无头像用户...")
    df = db.execute_query(sql, {'limit': limit})
    
    if df.empty:
        logger.info("所有用户都有头像，无需处理。")
        return
        
    logger.info(f"找到 {len(df)} 个无头像用户，开始更新...")
    
    updated_count = 0
    
    try:
        with db.engine.connect() as conn:
            for idx, row in df.iterrows():
                user_id = row['id']
                # 使用 open_id 或 nick_name 作为种子，确保同一个用户生成的头像始终一致
                seed = row['open_id'] or row['nick_name'] or f"user_{user_id}"
                
                if use_realistic:
                    # 随机选择真实人像
                    avatar_url = random.choice(REALISTIC_AVATARS)
                else:
                    # 生成卡通/风格化头像
                    avatar_url = generate_avatar_url(seed, style)
                
                # 更新数据库
                update_sql = "UPDATE client_user SET avatar = :avatar WHERE id = :id"
                conn.execute(text(update_sql), {'avatar': avatar_url, 'id': user_id})
                
                updated_count += 1
                if updated_count % 100 == 0:
                    logger.info(f"已更新 {updated_count} 个用户头像")
                    
            conn.commit()
            
    except Exception as e:
        logger.error(f"更新失败: {e}", exc_info=True)
        
    logger.info(f"🎉 完成！共更新 {updated_count} 个用户头像。")

def main():
    parser = argparse.ArgumentParser(description='为用户自动生成头像')
    parser.add_argument('--limit', type=int, default=1000, help='处理用户数量限制')
    parser.add_argument('--style', type=str, choices=AVATAR_STYLES, help='指定头像风格 (默认随机)')
    parser.add_argument('--realistic', action='store_true', help='使用真实人像风格 (Unsplash随机图)')
    
    args = parser.parse_args()
    
    fill_avatars(limit=args.limit, style=args.style, use_realistic=args.realistic)

if __name__ == '__main__':
    main()
