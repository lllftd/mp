#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量上传帖子到数据库

用法:
    python3 batch_upload_tweets.py <file_path> [--format csv|json|excel]
    
示例:
    python3 batch_upload_tweets.py tweets.csv --format csv
    python3 batch_upload_tweets.py tweets.json --format json
    python3 batch_upload_tweets.py tweets.xlsx --format excel
"""
import sys
import os
import json
import csv
import logging
from typing import List, Dict, Optional, Tuple

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from database import db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def validate_type_ids(type_pid: int, type_cids: str) -> Tuple[bool, str]:
    """验证类型ID是否存在"""
    try:
        # 验证父ID
        pid_query = "SELECT id FROM tweets_type WHERE id = :pid"
        pid_result = db.execute_query(pid_query, {'pid': type_pid})
        if pid_result.empty:
            return False, f"父类型ID {type_pid} 不存在"
        
        # 验证子ID
        if type_cids:
            cid_list = [cid.strip() for cid in str(type_cids).split(',') if cid.strip()]
            if cid_list:
                placeholders = ','.join([f':cid{i}' for i in range(len(cid_list))])
                cid_query = f"""
                    SELECT id FROM tweets_type 
                    WHERE id IN ({placeholders}) AND parent_id = :parent_id
                """
                params = {f'cid{i}': int(cid) for i, cid in enumerate(cid_list)}
                params['parent_id'] = type_pid
                
                cid_result = db.execute_query(cid_query, params)
                found_ids = set(cid_result['id'].tolist())
                expected_ids = {int(cid) for cid in cid_list}
                
                if found_ids != expected_ids:
                    missing = expected_ids - found_ids
                    return False, f"子类型ID {missing} 不存在或不属于父类型 {type_pid}"
        
        return True, ""
    except Exception as e:
        return False, f"验证类型ID失败: {str(e)}"


def load_csv(file_path: str) -> List[Dict]:
    """从CSV文件加载数据"""
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data


def load_json(file_path: str) -> List[Dict]:
    """从JSON文件加载数据"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if isinstance(data, dict):
        # 如果JSON是对象，尝试找data字段
        data = data.get('data', [data])
    if not isinstance(data, list):
        data = [data]
    return data


def load_excel(file_path: str) -> List[Dict]:
    """从Excel文件加载数据"""
    df = pd.read_excel(file_path)
    return df.to_dict('records')


def prepare_tweet_data(row: Dict) -> Dict:
    """准备插入数据库的数据"""
    tweet = {}
    
    # 必填字段（NOT NULL）
    # 标题
    tweet['tweets_title'] = str(row.get('tweets_title') or row.get('title', '')).strip()
    if not tweet['tweets_title']:
        raise ValueError("标题(tweets_title)不能为空")
    
    # 类型父ID（必填）
    type_pid = row.get('tweets_type_pid') or row.get('type_pid')
    if type_pid:
        try:
            tweet['tweets_type_pid'] = int(type_pid)
        except (ValueError, TypeError):
            raise ValueError("推文类型父ID(tweets_type_pid)必须是整数")
    else:
        raise ValueError("推文类型父ID(tweets_type_pid)不能为空")
    
    # 类型子ID（必填）
    type_cid = row.get('tweets_type_cid') or row.get('type_cid')
    if type_cid:
        tweet['tweets_type_cid'] = str(type_cid).strip()
        if not tweet['tweets_type_cid']:
            raise ValueError("推文类型子ID(tweets_type_cid)不能为空")
    else:
        raise ValueError("推文类型子ID(tweets_type_cid)不能为空")
    
    # 验证类型ID是否存在于数据库中
    is_valid, error_msg = validate_type_ids(tweet['tweets_type_pid'], tweet['tweets_type_cid'])
    if not is_valid:
        raise ValueError(error_msg)
    
    # 简介（必填）
    tweet['tweets_describe'] = str(row.get('tweets_describe') or row.get('describe') or row.get('description', '')).strip()
    if not tweet['tweets_describe']:
        raise ValueError("简介(tweets_describe)不能为空")
    
    # 图片（必填）- 支持JSON数组格式或逗号分隔的URL
    img_raw = row.get('tweets_img') or row.get('image') or row.get('images') or row.get('img', '')
    if not img_raw:
        raise ValueError("图片(tweets_img)不能为空")
    
    img_str = str(img_raw).strip()
    # 如果已经是JSON数组格式，直接使用；否则转换为JSON数组
    if img_str.startswith('[') and img_str.endswith(']'):
        try:
            # 验证是否为有效JSON
            json.loads(img_str)
            tweet['tweets_img'] = img_str
        except json.JSONDecodeError:
            # 如果不是有效JSON，按逗号分隔处理
            img_list = [url.strip() for url in img_str.strip('[]').split(',') if url.strip()]
            tweet['tweets_img'] = json.dumps(img_list, ensure_ascii=False)
    else:
        # 逗号分隔的URL列表，转换为JSON数组
        img_list = [url.strip() for url in img_str.split(',') if url.strip()]
        if not img_list:
            raise ValueError("图片(tweets_img)不能为空")
        tweet['tweets_img'] = json.dumps(img_list, ensure_ascii=False)
    
    # 验证图片字段长度（JSON字符串）
    if len(tweet['tweets_img']) > 300:
        raise ValueError(f"图片字段长度超过300字符限制: {len(tweet['tweets_img'])}")
    
    # 内容（必填）
    tweet['tweets_content'] = str(row.get('tweets_content') or row.get('content', '')).strip()
    if not tweet['tweets_content']:
        raise ValueError("内容(tweets_content)不能为空")
    
    # 可选字段
    tweets_user = row.get('tweets_user') or row.get('user') or row.get('author')
    if tweets_user:
        tweet['tweets_user'] = str(tweets_user).strip()[:20]  # 限制长度varchar(20)
    
    # 统计字段（默认为0，数据库有默认值）
    like_num = row.get('like_num') or row.get('likes')
    if like_num is not None:
        tweet['like_num'] = int(like_num)
    
    collect_num = row.get('collect_num') or row.get('collects')
    if collect_num is not None:
        tweet['collect_num'] = int(collect_num)
    
    browse_num = row.get('browse_num') or row.get('browses') or row.get('views')
    if browse_num is not None:
        tweet['browse_num'] = int(browse_num)
    
    # 用户字段（可选，限制长度）
    create_user = row.get('create_user') or row.get('creator')
    if create_user:
        tweet['create_user'] = str(create_user).strip()[:10]
    
    client_create_user = row.get('client_create_user') or row.get('client_creator')
    if client_create_user:
        tweet['client_create_user'] = str(client_create_user).strip()[:10]
    
    update_user = row.get('update_user')
    if update_user:
        tweet['update_user'] = str(update_user).strip()[:10]
    
    # 字段长度验证（集中验证）
    if len(tweet['tweets_title']) > 120:
        raise ValueError(f"标题长度超过120字符限制: {len(tweet['tweets_title'])}")
    if len(tweet['tweets_describe']) > 400:
        raise ValueError(f"简介长度超过400字符限制: {len(tweet['tweets_describe'])}")
    if len(tweet['tweets_content']) > 2000:
        raise ValueError(f"内容长度超过2000字符限制: {len(tweet['tweets_content'])}")
    if len(tweet['tweets_type_cid']) > 70:
        raise ValueError(f"类型子ID长度超过70字符限制: {len(tweet['tweets_type_cid'])}")
    
    return tweet


def insert_tweet(tweet: Dict) -> Optional[int]:
    """插入单条推文，返回插入的ID"""
    try:
        # 构建INSERT语句
        columns = []
        values = []
        params = {}
        
        for key, value in tweet.items():
            if value is not None:
                columns.append(key)
                values.append(f":{key}")
                params[key] = value
        
        if not columns:
            logger.warning("没有有效字段可插入")
            return None
        
        sql = f"""
            INSERT INTO tweets ({', '.join(columns)})
            VALUES ({', '.join(values)})
        """
        
        with db.engine.connect() as conn:
            result = conn.execute(text(sql), params)
            conn.commit()
            # 获取插入的ID
            last_id = result.lastrowid
            return last_id
            
    except Exception as e:
        logger.error(f"插入推文失败: {str(e)}")
        logger.error(f"数据: {tweet}")
        raise


def batch_insert_tweets(tweets: List[Dict], batch_size: int = 100) -> Dict:
    """批量插入推文"""
    total = len(tweets)
    success_count = 0
    fail_count = 0
    inserted_ids = []
    errors = []
    
    logger.info(f"开始批量插入 {total} 条推文...")
    
    for idx, row in enumerate(tweets, 1):
        try:
            tweet_data = prepare_tweet_data(row)
            tweet_id = insert_tweet(tweet_data)
            
            if tweet_id:
                success_count += 1
                inserted_ids.append(tweet_id)
                if idx % 10 == 0:
                    logger.info(f"已处理 {idx}/{total} 条...")
            else:
                fail_count += 1
                errors.append(f"第 {idx} 行: 插入失败（返回ID为空）")
                
        except Exception as e:
            fail_count += 1
            error_msg = f"第 {idx} 行: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)
    
    return {
        'total': total,
        'success': success_count,
        'failed': fail_count,
        'inserted_ids': inserted_ids,
        'errors': errors
    }


def main():
    if len(sys.argv) < 2:
        print("用法: python3 batch_upload_tweets.py <file_path> [--format csv|json|excel]")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    # 检测文件格式
    file_format = 'csv'
    if '--format' in sys.argv:
        idx = sys.argv.index('--format')
        if idx + 1 < len(sys.argv):
            file_format = sys.argv[idx + 1].lower()
    else:
        # 根据扩展名自动检测
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.json':
            file_format = 'json'
        elif ext in ['.xlsx', '.xls']:
            file_format = 'excel'
    
    if not os.path.exists(file_path):
        logger.error(f"文件不存在: {file_path}")
        sys.exit(1)
    
    logger.info(f"读取文件: {file_path} (格式: {file_format})")
    
    try:
        # 加载数据
        if file_format == 'csv':
            data = load_csv(file_path)
        elif file_format == 'json':
            data = load_json(file_path)
        elif file_format == 'excel':
            data = load_excel(file_path)
        else:
            logger.error(f"不支持的文件格式: {file_format}")
            sys.exit(1)
        
        if not data:
            logger.error("文件中没有数据")
            sys.exit(1)
        
        logger.info(f"成功加载 {len(data)} 条记录")
        
        # 批量插入
        result = batch_insert_tweets(data)
        
        # 输出结果
        print("\n" + "="*50)
        print("批量导入结果")
        print("="*50)
        print(f"总数: {result['total']}")
        print(f"成功: {result['success']}")
        print(f"失败: {result['failed']}")
        
        if result['inserted_ids']:
            print(f"\n插入的ID范围: {min(result['inserted_ids'])} ~ {max(result['inserted_ids'])}")
        
        if result['errors']:
            print(f"\n错误详情 (前10条):")
            for error in result['errors'][:10]:
                print(f"  - {error}")
            if len(result['errors']) > 10:
                print(f"  ... 还有 {len(result['errors']) - 10} 条错误")
        
        print("="*50)
        
    except Exception as e:
        logger.error(f"批量导入失败: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

