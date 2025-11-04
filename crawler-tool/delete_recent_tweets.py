#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
删除最近上传的推文数据

用法:
    python3 delete_recent_tweets.py [--hours 1] [--limit 100]
    
示例:
    python3 delete_recent_tweets.py --hours 1  # 删除最近1小时的数据
    python3 delete_recent_tweets.py --limit 50  # 删除最近50条数据
"""
import sys
import os
import argparse
import logging
from datetime import datetime, timedelta

# 修复Windows控制台编码问题
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from database import db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def delete_recent_tweets_by_time(hours: int = 1) -> int:
    """
    删除最近N小时内上传的推文
    
    Args:
        hours: 小时数，默认1小时
        
    Returns:
        删除的记录数
    """
    try:
        cutoff_time = datetime.now() - timedelta(hours=hours)
        cutoff_str = cutoff_time.strftime('%Y-%m-%d %H:%M:%S')
        
        sql = """
            DELETE FROM tweets 
            WHERE create_time >= :cutoff_time
        """
        
        deleted_count = db.execute_update(sql, {'cutoff_time': cutoff_str})
        logger.info(f"删除了 {deleted_count} 条最近 {hours} 小时内的推文（截止时间: {cutoff_str}）")
        return deleted_count
        
    except Exception as e:
        logger.error(f"删除失败: {e}")
        raise


def delete_recent_tweets_by_limit(limit: int = 100) -> int:
    """
    删除最近N条推文
    
    Args:
        limit: 要删除的记录数，默认100条
        
    Returns:
        删除的记录数
    """
    try:
        # 先查询要删除的ID
        select_sql = """
            SELECT id FROM tweets 
            ORDER BY create_time DESC 
            LIMIT :limit
        """
        
        result = db.execute_query(select_sql, {'limit': limit})
        
        if result.empty:
            logger.info("没有找到需要删除的记录")
            return 0
        
        ids = result['id'].tolist()
        ids_str = ','.join(map(str, ids))
        
        # 删除这些记录
        delete_sql = f"""
            DELETE FROM tweets 
            WHERE id IN ({ids_str})
        """
        
        deleted_count = db.execute_update(delete_sql)
        logger.info(f"删除了 {deleted_count} 条最近的推文（ID: {ids_str}）")
        return deleted_count
        
    except Exception as e:
        logger.error(f"删除失败: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description='删除最近上传的推文数据')
    parser.add_argument('--hours', type=int, help='删除最近N小时内的数据')
    parser.add_argument('--limit', type=int, help='删除最近N条数据')
    parser.add_argument('--confirm', action='store_true', help='确认删除（不加此参数将只显示统计信息）')
    
    args = parser.parse_args()
    
    if not args.hours and not args.limit:
        print("请指定删除方式：")
        print("  --hours N  删除最近N小时内的数据")
        print("  --limit N  删除最近N条数据")
        print("\n示例：")
        print("  python3 delete_recent_tweets.py --hours 1 --confirm")
        print("  python3 delete_recent_tweets.py --limit 50 --confirm")
        return
    
    if not args.confirm:
        print("[WARN] 警告：此操作将删除数据库中的数据！")
        print("请添加 --confirm 参数来确认删除")
        return
    
    try:
        if args.hours:
            deleted_count = delete_recent_tweets_by_time(args.hours)
        elif args.limit:
            deleted_count = delete_recent_tweets_by_limit(args.limit)
        
        print(f"[OK] 删除完成，共删除 {deleted_count} 条记录")
        
    except Exception as e:
        print(f"[ERROR] 删除失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

