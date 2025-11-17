#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
添加推文类型脚本
用于管理推文类型（tweets_type表）
"""
import os
import sys
import logging
import argparse
from typing import Optional

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from base.database import db
from sqlalchemy import text

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def list_types():
    """列出所有推文类型"""
    try:
        sql = """
            SELECT 
                id,
                name,
                parent_id,
                (SELECT name FROM tweets_type WHERE id = t.parent_id) AS parent_name
            FROM tweets_type t
            ORDER BY parent_id, id
        """
        
        df = db.execute_query(sql)
        
        if df.empty:
            logger.warning("没有找到任何类型记录")
            return
        
        logger.info("=" * 80)
        logger.info("推文类型列表")
        logger.info("=" * 80)
        
        current_parent = None
        for idx, row in df.iterrows():
            parent_id = row['parent_id']
            parent_name = row['parent_name'] if row['parent_name'] else '无'
            
            if current_parent != parent_id:
                logger.info(f"\n父类型: {parent_name} (ID: {parent_id})")
                current_parent = parent_id
            
            logger.info(f"  - {row['name']} (ID: {row['id']})")
        
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"查询失败: {e}", exc_info=True)
        raise


def add_parent_type(name: str) -> Optional[int]:
    """
    添加父类型
    
    Args:
        name: 类型名称
        
    Returns:
        新添加的类型ID，如果失败返回None
    """
    try:
        # 检查是否已存在
        check_sql = "SELECT id FROM tweets_type WHERE name = :name AND parent_id IS NULL"
        existing = db.execute_query(check_sql, {'name': name})
        
        if not existing.empty:
            logger.warning(f"父类型 '{name}' 已存在，ID: {existing.iloc[0]['id']}")
            return int(existing.iloc[0]['id'])
        
        # 获取下一个ID
        max_id_sql = "SELECT MAX(id) AS max_id FROM tweets_type"
        max_result = db.execute_query(max_id_sql)
        next_id = 1
        if not max_result.empty and max_result.iloc[0]['max_id']:
            next_id = int(max_result.iloc[0]['max_id']) + 1
        
        # 插入新类型
        insert_sql = """
            INSERT INTO tweets_type (id, name, parent_id)
            VALUES (:id, :name, NULL)
        """
        db.execute_update(insert_sql, {
            'id': next_id,
            'name': name
        })
        
        logger.info(f"✅ 成功添加父类型: {name} (ID: {next_id})")
        return next_id
        
    except Exception as e:
        logger.error(f"添加父类型失败: {e}", exc_info=True)
        return None


def add_child_type(name: str, parent_id: int) -> Optional[int]:
    """
    添加子类型
    
    Args:
        name: 类型名称
        parent_id: 父类型ID
        
    Returns:
        新添加的类型ID，如果失败返回None
    """
    try:
        # 检查父类型是否存在
        parent_sql = "SELECT id, name FROM tweets_type WHERE id = :parent_id AND parent_id IS NULL"
        parent_result = db.execute_query(parent_sql, {'parent_id': parent_id})
        
        if parent_result.empty:
            logger.error(f"父类型 ID {parent_id} 不存在")
            return None
        
        parent_name = parent_result.iloc[0]['name']
        
        # 检查是否已存在
        check_sql = "SELECT id FROM tweets_type WHERE name = :name AND parent_id = :parent_id"
        existing = db.execute_query(check_sql, {'name': name, 'parent_id': parent_id})
        
        if not existing.empty:
            logger.warning(f"子类型 '{name}' 已存在于父类型 '{parent_name}' (ID: {parent_id})，子类型ID: {existing.iloc[0]['id']}")
            return int(existing.iloc[0]['id'])
        
        # 获取下一个ID
        max_id_sql = "SELECT MAX(id) AS max_id FROM tweets_type"
        max_result = db.execute_query(max_id_sql)
        next_id = 1
        if not max_result.empty and max_result.iloc[0]['max_id']:
            next_id = int(max_result.iloc[0]['max_id']) + 1
        
        # 插入新类型
        insert_sql = """
            INSERT INTO tweets_type (id, name, parent_id)
            VALUES (:id, :name, :parent_id)
        """
        db.execute_update(insert_sql, {
            'id': next_id,
            'name': name,
            'parent_id': parent_id
        })
        
        logger.info(f"✅ 成功添加子类型: {name} (ID: {next_id})，父类型: {parent_name} (ID: {parent_id})")
        return next_id
        
    except Exception as e:
        logger.error(f"添加子类型失败: {e}", exc_info=True)
        return None


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description='管理推文类型',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 列出所有类型
  python3 add_tweet_type.py --list
  
  # 添加父类型
  python3 add_tweet_type.py --parent "旅游"
  
  # 添加子类型
  python3 add_tweet_type.py --child "意大利菜" --parent-id 5
        """
    )
    
    parser.add_argument('--list', action='store_true', help='列出所有类型')
    parser.add_argument('--parent', type=str, help='添加父类型（指定名称）')
    parser.add_argument('--child', type=str, help='添加子类型（指定名称）')
    parser.add_argument('--parent-id', type=int, help='父类型ID（添加子类型时必需）')
    
    args = parser.parse_args()
    
    if args.list:
        list_types()
    elif args.parent:
        add_parent_type(args.parent)
    elif args.child:
        if not args.parent_id:
            logger.error("添加子类型时必须指定 --parent-id")
            parser.print_help()
            sys.exit(1)
        add_child_type(args.child, args.parent_id)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()

