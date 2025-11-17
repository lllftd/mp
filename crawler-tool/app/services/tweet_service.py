#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
推文数据处理模块
提供推文数据准备、插入等功能
"""
import json
import logging
import os
import sys
from typing import Dict, List, Optional, Tuple

from sqlalchemy import text

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from base.database import db
from base.location_utils import extract_district_from_address, find_county_code

logger = logging.getLogger(__name__)


def validate_type_ids(type_pid: int, type_cids: str) -> Tuple[bool, str]:
    """
    验证类型ID是否存在
    
    Args:
        type_pid: 父类型ID
        type_cids: 子类型ID（可以是逗号分隔的多个ID）
        
    Returns:
        (是否有效, 错误信息)
    """
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
                # 使用更安全的方式构建查询，避免参数绑定问题
                try:
                    # 先转换为整数列表
                    cid_int_list = [int(cid) for cid in cid_list]
                    
                    # 构建参数化的IN查询
                    placeholders = ','.join([f':cid{i}' for i in range(len(cid_int_list))])
                    cid_query = f"""
                        SELECT id FROM tweets_type 
                        WHERE id IN ({placeholders}) AND parent_id = :parent_id
                    """
                    
                    # 构建参数字典
                    params = {}
                    for i, cid_val in enumerate(cid_int_list):
                        params[f'cid{i}'] = cid_val
                    params['parent_id'] = type_pid
                    
                    # 执行查询
                    cid_result = db.execute_query(cid_query, params)
                    
                    # 检查结果
                    if cid_result.empty:
                        return False, f"子类型ID {type_cids} 不存在或不属于父类型 {type_pid}"
                    
                    found_ids = set(cid_result['id'].tolist())
                    expected_ids = set(cid_int_list)
                    
                    if found_ids != expected_ids:
                        missing = expected_ids - found_ids
                        return False, f"子类型ID {missing} 不存在或不属于父类型 {type_pid}"
                except ValueError as ve:
                    return False, f"子类型ID格式错误: {str(ve)}"
        
        return True, ""
    except Exception as e:
        return False, f"验证类型ID失败: {str(e)}"


def _remove_duplicate_city_in_address(address: str) -> str:
    """
    移除地址中重复的城市名称
    
    Args:
        address: 原始地址
        
    Returns:
        清理后的地址
    """
    if not address or not address.strip():
        return address
    
    import re
    
    address = address.strip()
    
    # 常见城市列表（带"市"后缀）
    cities_with_suffix = [
        '北京市', '上海市', '广州市', '深圳市', '杭州市', '成都市', '南京市', 
        '武汉市', '西安市', '重庆市', '苏州市', '天津市', '长沙市', '郑州市',
        '青岛市', '大连市', '宁波市', '厦门市', '福州市', '合肥市', '昆明市',
        '太原市', '石家庄市', '哈尔滨市', '长春市', '沈阳市', '济南市', '南昌市',
        '南宁市', '海口市', '贵阳市', '拉萨市', '银川市', '乌鲁木齐市', '呼和浩特市'
    ]
    
    # 检查是否有重复的城市名称
    for city_with_suffix in cities_with_suffix:
        # 检查是否出现重复（如"上海市上海市"）
        pattern = f'({city_with_suffix})\\1'
        if re.search(pattern, address):
            # 替换为单个城市名
            address = re.sub(pattern, r'\1', address)
    
    # 更通用的模式：检查连续重复的城市名（如"XX市XX市"）
    pattern = r'([^省市区县]{2,4}市)\1'
    matches = re.findall(pattern, address)
    if matches:
        for match in matches:
            address = address.replace(match + match, match)
    
    return address.strip()


def prepare_tweet_data(row: Dict) -> Dict:
    """
    准备插入数据库的数据
    
    Args:
        row: 原始数据字典
        
    Returns:
        处理后的推文数据字典
        
    Raises:
        ValueError: 当必填字段缺失或格式错误时
    """
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
    
    # 清理地址中重复的城市名称（防止出现"上海市上海市"）
    tweet['tweets_describe'] = _remove_duplicate_city_in_address(tweet['tweets_describe'])
    
    # 图片（必填）- 支持JSON数组格式或逗号分隔的URL
    img_raw = row.get('tweets_img') or row.get('image') or row.get('images') or row.get('img', '')
    if not img_raw:
        raise ValueError("图片(tweets_img)不能为空")
    
    img_str = str(img_raw).strip()
    img_list = []
    
    # 如果已经是JSON数组格式，直接使用；否则转换为JSON数组
    if img_str.startswith('[') and img_str.endswith(']'):
        try:
            # 验证是否为有效JSON
            img_list = json.loads(img_str)
            if not isinstance(img_list, list):
                img_list = [img_list]
        except json.JSONDecodeError:
            # 如果不是有效JSON，按逗号分隔处理
            img_list = [url.strip() for url in img_str.strip('[]').split(',') if url.strip()]
    else:
        # 逗号分隔的URL列表，转换为JSON数组
        img_list = [url.strip() for url in img_str.split(',') if url.strip()]
    
    if not img_list:
        raise ValueError("图片(tweets_img)不能为空")
    
    # 如果图片列表的JSON字符串超过300字符，逐步减少图片数量
    max_length = 300
    while len(json.dumps(img_list, ensure_ascii=False)) > max_length and len(img_list) > 1:
        img_list = img_list[:-1]  # 移除最后一个图片
    
    tweet['tweets_img'] = json.dumps(img_list, ensure_ascii=False)
    
    # 最终验证图片字段长度（如果单个图片URL就超过300字符，至少保留一个）
    if len(tweet['tweets_img']) > max_length:
        # 如果即使只有一个图片也超过限制，截断单个URL
        if len(img_list) == 1 and len(img_list[0]) > max_length - 10:  # 留出JSON格式空间
            # 截断URL，保留前面的部分
            max_url_length = max_length - 10  # 减去 '[""]' 的长度
            img_list[0] = img_list[0][:max_url_length]
            tweet['tweets_img'] = json.dumps(img_list, ensure_ascii=False)
    
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
    
    # 处理区代码：优先使用用户提供的值，否则自动提取
    if row.get('tweets_location_code'):
        # 如果用户明确提供了tweets_location_code，使用用户提供的值
        tweet['tweets_location_code'] = str(row.get('tweets_location_code')).strip()[:20]
    elif tweet.get('tweets_describe'):
        # 否则自动提取区代码（如果地址存在）
        try:
            district = extract_district_from_address(tweet['tweets_describe'])
            if district:
                city_name = row.get('tweets_location') or tweet.get('tweets_location')
                county_code = find_county_code(district, city_name)
                if county_code:
                    tweet['tweets_location_code'] = county_code
                    logger.debug(f"自动提取区代码: {district} -> {county_code}")
        except Exception as e:
            logger.debug(f"提取区代码失败: {e}")
    
    # 字段长度验证（仅保留类型子ID的验证，标题和描述不再限制长度）
    if len(tweet['tweets_type_cid']) > 70:
        raise ValueError(f"类型子ID长度超过70字符限制: {len(tweet['tweets_type_cid'])}")
    
    return tweet


def insert_tweet(tweet: Dict) -> Optional[int]:
    """
    插入单条推文，返回插入的ID
    
    Args:
        tweet: 推文数据字典
        
    Returns:
        插入的推文ID，失败返回None
    """
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
    """
    批量插入推文
    
    Args:
        tweets: 推文数据列表
        batch_size: 批次大小（未使用，保留用于未来优化）
        
    Returns:
        插入结果统计字典
    """
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
