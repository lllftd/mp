#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
随机化评论区用户名脚本
使用AI生成真实自然的用户名，创建新用户，并将评论随机分配给这些用户。
"""

import os
import sys
import logging
import argparse
import random
import uuid
import time
from typing import List

# 修复 Windows 控制台乱码
if os.name == 'nt':
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from base.database import db
from app.services.ai_service import get_ai_paraphraser
from sqlalchemy import text

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_fake_users(count: int, batch_size: int = 50) -> List[int]:
    """
    生成指定数量的虚假用户并插入数据库
    
    Args:
        count: 需要生成的数量
        batch_size: 每批生成的数量
        
    Returns:
        新创建的用户ID列表
    """
    ai = get_ai_paraphraser()
    new_user_ids = []
    
    logger.info(f"开始生成 {count} 个新用户...")
    
    generated_count = 0
    while generated_count < count:
        current_batch = min(batch_size, count - generated_count)
        logger.info(f"正在生成批次: {generated_count + 1}-{generated_count + current_batch} / {count}")
        
        try:
            # 1. AI生成用户名
            usernames = ai.generate_usernames(count=current_batch)
            if not usernames:
                logger.warning("AI未返回用户名，重试...")
                time.sleep(2)
                continue
                
            # 2. 插入数据库
            current_ids = []
            with db.engine.connect() as conn:
                for name in usernames:
                    # 生成唯一的 open_id
                    fake_open_id = f"fake_user_{uuid.uuid4().hex[:16]}"
                    
                    # 随机生成一些简单的头像或留空 (这里留空)
                    avatar = ""
                    
                    sql = """
                        INSERT INTO client_user (open_id, nick_name, avatar, status, get_msg)
                        VALUES (:open_id, :nick_name, :avatar, '1', '1')
                    """
                    conn.execute(text(sql), {
                        'open_id': fake_open_id,
                        'nick_name': name,
                        'avatar': avatar
                    })
                    
                    # 获取刚插入的ID
                    result = conn.execute(text("SELECT LAST_INSERT_ID()"))
                    user_id = result.scalar()
                    current_ids.append(user_id)
                
                conn.commit()
            
            new_user_ids.extend(current_ids)
            generated_count += len(current_ids)
            logger.info(f"✅ 成功创建 {len(current_ids)} 个用户")
            
            # 避免请求过快
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"生成用户失败: {e}")
            time.sleep(5)
            
    return new_user_ids


def randomize_comments(user_ids: List[int], limit: int = None, dry_run: bool = False):
    """
    将评论随机分配给指定的用户列表
    """
    if not user_ids:
        logger.error("没有可用的用户ID")
        return

    logger.info(f"开始随机分配评论给 {len(user_ids)} 个用户...")
    
    # 获取所有评论ID
    sql = "SELECT id FROM tweets_evaluate"
    if limit:
        sql += f" LIMIT {limit}"
        
    df = db.execute_query(sql)
    if df.empty:
        logger.warning("没有找到评论")
        return
        
    comment_ids = df['id'].tolist()
    logger.info(f"找到 {len(comment_ids)} 条评论需要处理")
    
    if dry_run:
        logger.info("[试运行] 不执行实际更新")
        return

    # 准备批量更新数据
    updates = []
    for cid in comment_ids:
        # 随机选择一个用户
        uid = random.choice(user_ids)
        updates.append({'uid': uid, 'cid': cid})
    
    # 分批执行更新 (每批1000条)
    batch_size = 1000
    total_updated = 0
    
    logger.info(f"开始批量更新，共 {len(updates)} 条...")
    
    try:
        with db.engine.connect() as conn:
            for i in range(0, len(updates), batch_size):
                batch = updates[i:i+batch_size]
                
                # 使用 executemany 批量执行
                conn.execute(
                    text("UPDATE tweets_evaluate SET client_user_id = :uid WHERE id = :cid"),
                    batch
                )
                conn.commit()
                
                total_updated += len(batch)
                if total_updated % 5000 == 0:
                    logger.info(f"已更新 {total_updated}/{len(updates)} 条评论")
                    
    except Exception as e:
        logger.error(f"批量更新失败: {e}", exc_info=True)
            
    logger.info(f"🎉 所有评论随机化完成！共更新 {total_updated} 条")


def main():
    parser = argparse.ArgumentParser(description='随机化评论区用户名')
    parser.add_argument('--count', type=int, default=100, help='生成的新用户数量 (默认: 100)')
    parser.add_argument('--limit', type=int, help='限制处理的评论数量 (默认: 所有)')
    parser.add_argument('--dry-run', action='store_true', help='试运行模式，不修改数据库')
    
    args = parser.parse_args()
    
    try:
        # 1. 生成新用户
        user_ids = generate_fake_users(args.count)
        
        if not user_ids:
            logger.error("未能生成任何新用户，退出")
            return
            
        # 2. 随机分配评论
        randomize_comments(user_ids, limit=args.limit, dry_run=args.dry_run)
        
    except KeyboardInterrupt:
        logger.info("用户中断操作")
    except Exception as e:
        logger.error(f"程序异常: {e}", exc_info=True)

if __name__ == '__main__':
    main()
