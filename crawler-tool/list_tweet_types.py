#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查询推文类型（tweets_type表）

用法:
    python3 list_tweet_types.py [--parent-id <parent_id>]
    
示例:
    python3 list_tweet_types.py                    # 查询所有类型
    python3 list_tweet_types.py --parent-id 5     # 查询父id为5的所有子类型
"""
import sys
import os
import argparse

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import db


def list_all_types():
    """列出所有类型"""
    query = """
        SELECT 
            id,
            name,
            parent_id,
            CASE 
                WHEN parent_id IS NULL THEN '一级分类'
                ELSE CONCAT('子分类 (父ID: ', parent_id, ')')
            END as level
        FROM tweets_type
        ORDER BY COALESCE(parent_id, 0), id
    """
    result = db.execute_query(query)
    return result


def list_child_types(parent_id: int):
    """列出指定父id的所有子类型"""
    query = """
        SELECT 
            id,
            name,
            parent_id
        FROM tweets_type
        WHERE parent_id = :parent_id
        ORDER BY id
    """
    result = db.execute_query(query, {'parent_id': parent_id})
    return result


def list_parent_types():
    """列出所有一级分类（父类型）"""
    query = """
        SELECT 
            id,
            name,
            parent_id
        FROM tweets_type
        WHERE parent_id IS NULL
        ORDER BY id
    """
    result = db.execute_query(query)
    return result


def main():
    parser = argparse.ArgumentParser(description="查询推文类型")
    parser.add_argument('--parent-id', type=int, help='查询指定父ID的子类型')
    parser.add_argument('--only-parents', action='store_true', help='只显示一级分类')
    args = parser.parse_args()
    
    try:
        if args.only_parents:
            result = list_parent_types()
            print("\n" + "="*50)
            print("一级分类列表")
            print("="*50)
        elif args.parent_id:
            result = list_child_types(args.parent_id)
            print("\n" + "="*50)
            print(f"父ID {args.parent_id} 的子类型列表")
            print("="*50)
        else:
            result = list_all_types()
            print("\n" + "="*50)
            print("所有类型列表")
            print("="*50)
        
        if result.empty:
            print("没有找到类型数据")
        else:
            print(result.to_string(index=False))
            
            if args.parent_id:
                cid_list = ','.join([str(row['id']) for _, row in result.iterrows()])
                print(f"\n子ID列表（用于tweets_type_cid）: {cid_list}")
        
        print("="*50)
        
    except Exception as e:
        print(f"查询失败: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

