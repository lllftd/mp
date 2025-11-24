#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
删除重复帖子脚本
根据标题和餐厅地址识别重复帖子，保留ID最小的，删除其他重复项
"""
import os
import sys
import logging
import argparse
from typing import List, Dict, Tuple

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from base.database import db
from sqlalchemy import text

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def find_duplicate_tweets(dry_run: bool = False) -> Tuple[List[Dict], int]:
    """
    查找重复的帖子
    
    Args:
        dry_run: 是否为试运行模式
        
    Returns:
        (重复帖子列表, 重复组数)
    """
    logger.info("开始查找重复帖子...")
    
    # 使用SQL GROUP BY找出重复的标题和地址组合
    sql = """
        SELECT 
            tweets_title,
            tweets_describe,
            COUNT(*) as count,
            GROUP_CONCAT(id ORDER BY id ASC) as ids
        FROM tweets
        WHERE tweets_title IS NOT NULL 
          AND tweets_title != ''
          AND tweets_describe IS NOT NULL 
          AND tweets_describe != ''
        GROUP BY tweets_title, tweets_describe
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC
    """
    
    logger.info("查询重复帖子...")
    df = db.execute_query(sql)
    
    if df.empty:
        logger.info("没有找到重复的帖子")
        return [], 0
    
    logger.info(f"找到 {len(df)} 组重复帖子")
    
    # 获取所有重复帖子的详细信息
    duplicate_groups = []
    duplicate_tweets = []
    all_duplicate_ids = []
    
    for idx, row in df.iterrows():
        title = str(row['tweets_title']).strip()
        address = str(row['tweets_describe']).strip()
        count = int(row['count'])
        ids_str = str(row['ids'])
        
        # 解析ID列表
        ids = [int(id_str.strip()) for id_str in ids_str.split(',') if id_str.strip()]
        
        # 保留最小的ID，其他都要删除
        keep_id = ids[0]
        delete_ids = ids[1:]
        
        duplicate_groups.append({
            'title': title,
            'address': address,
            'count': count,
            'keep_id': keep_id,
            'delete_ids': delete_ids
        })
        
        all_duplicate_ids.extend(delete_ids)
    
    # 查询要删除的帖子的详细信息
    if all_duplicate_ids:
        ids_str = ','.join([str(tid) for tid in all_duplicate_ids])
        detail_sql = f"""
            SELECT 
                id,
                tweets_title,
                tweets_describe,
                create_time
            FROM tweets
            WHERE id IN ({ids_str})
            ORDER BY id ASC
        """
        detail_df = db.execute_query(detail_sql)
        
        for idx, row in detail_df.iterrows():
            duplicate_tweets.append({
                'id': int(row['id']),
                'title': str(row['tweets_title']).strip(),
                'address': str(row['tweets_describe']).strip(),
                'create_time': row.get('create_time')
            })
    
    logger.info(f"共 {len(duplicate_tweets)} 条需要删除的重复帖子")
    
    # 显示重复信息
    if duplicate_groups:
        logger.info("\n重复帖子详情（前10组）：")
        for i, group in enumerate(duplicate_groups[:10], 1):
            logger.info(f"\n组 {i}: 标题='{group['title'][:50]}...', 地址='{group['address'][:50]}...'")
            logger.info(f"  重复数量: {group['count']} 条")
            logger.info(f"  保留: ID={group['keep_id']}")
            logger.info(f"  删除: IDs={group['delete_ids']}")
        
        if len(duplicate_groups) > 10:
            logger.info(f"\n... 还有 {len(duplicate_groups) - 10} 组重复帖子")
    
    return duplicate_tweets, len(duplicate_groups)


def remove_duplicate_tweets(
    dry_run: bool = False,
    limit: int = None
):
    """
    删除重复的帖子
    
    Args:
        dry_run: 是否为试运行模式
        limit: 限制删除数量（用于测试）
    """
    try:
        # 查找重复帖子
        duplicate_tweets, group_count = find_duplicate_tweets(dry_run)
        
        if not duplicate_tweets:
            logger.info("没有找到重复的帖子")
            return
        
        # 如果指定了限制，只处理前N条
        if limit and limit > 0:
            duplicate_tweets = duplicate_tweets[:limit]
            logger.info(f"限制处理数量为 {limit} 条")
        
        if dry_run:
            logger.info(f"\n[试运行模式] 将删除 {len(duplicate_tweets)} 条重复帖子")
            logger.info("使用 --no-dry-run 参数执行实际删除操作")
            return
        
        # 执行删除
        logger.info(f"\n开始删除 {len(duplicate_tweets)} 条重复帖子...")
        
        deleted_count = 0
        failed_count = 0
        
        # 批量删除（每次删除100条）
        batch_size = 100
        for i in range(0, len(duplicate_tweets), batch_size):
            batch = duplicate_tweets[i:i + batch_size]
            tweet_ids = [tweet['id'] for tweet in batch]
            
            # 构建IN子句（ID是整数，相对安全）
            ids_str = ','.join([str(tweet_id) for tweet_id in tweet_ids])
            
            delete_sql = f"""
                DELETE FROM tweets 
                WHERE id IN ({ids_str})
            """
            
            try:
                rowcount = db.execute_update(delete_sql)
                deleted_count += rowcount
                logger.info(f"已删除 {deleted_count}/{len(duplicate_tweets)} 条...")
            except Exception as e:
                logger.error(f"删除批次失败: {e}")
                failed_count += len(batch)
        
        logger.info(f"\n删除完成: 成功删除 {deleted_count} 条，失败 {failed_count} 条")
        logger.info(f"共处理 {group_count} 组重复帖子")
        
    except Exception as e:
        logger.error(f"删除重复帖子失败: {e}", exc_info=True)
        raise


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description='删除重复帖子脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
功能说明:
  根据标题(tweets_title)和餐厅地址(tweets_describe)识别重复帖子
  保留ID最小的帖子，删除其他重复项

示例:
  # 试运行模式（只查看，不删除）
  python3 remove_duplicate_tweets.py --dry-run
  
  # 实际删除重复帖子
  python3 remove_duplicate_tweets.py --no-dry-run
  
  # 限制删除数量（用于测试）
  python3 remove_duplicate_tweets.py --no-dry-run --limit 10
        """
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=True,
        help='试运行模式（默认开启，只查看不删除）'
    )
    parser.add_argument(
        '--no-dry-run',
        action='store_false',
        dest='dry_run',
        help='执行实际删除操作'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='限制删除数量（用于测试）'
    )
    
    args = parser.parse_args()
    
    try:
        remove_duplicate_tweets(
            dry_run=args.dry_run,
            limit=args.limit
        )
    except KeyboardInterrupt:
        logger.info("\n用户中断操作")
    except Exception as e:
        logger.error(f"执行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

