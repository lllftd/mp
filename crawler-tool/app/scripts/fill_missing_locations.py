#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
脚本：使用AI补全缺失的地区编码和所属地区
说明：针对数据库中只有地址但没有adcode的记录，使用AI分析地址并补全信息。
不使用本地JSON映射文件，也不使用高德API。
"""
import os
import sys
import time
import argparse
import logging
import pandas as pd
from sqlalchemy import text

# 解决Windows终端乱码问题
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# 添加项目根目录到路径
if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from base.database import db
from app.services.ai_service import get_ai_paraphraser

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def fill_missing_locations(limit: int = 100, city_filter: str = None, dry_run: bool = False):
    """
    补全缺失的地区编码
    """
    ai_service = get_ai_paraphraser()
    
    # 1. 查询需要处理的记录
    # 条件：tweets_describe(地址)不为空，但 tweets_location_code(地区编码)为空
    sql = """
        SELECT id, tweets_title, tweets_describe, tweets_location 
        FROM tweets 
        WHERE (tweets_location_code IS NULL OR tweets_location_code = '')
        AND (tweets_describe IS NOT NULL AND tweets_describe != '')
    """
    
    params = {}
    
    if city_filter:
        sql += " AND tweets_location LIKE :city"
        params['city'] = f"%{city_filter}%"
        
    sql += " ORDER BY id DESC"
    
    if limit:
        sql += " LIMIT :limit"
        params['limit'] = limit
        
    logger.info("正在查询缺失地区编码的记录...")
    df = db.execute_query(sql, params)
    
    if df.empty:
        logger.info("没有找到需要处理的记录。")
        return
        
    logger.info(f"找到 {len(df)} 条记录需要处理。")
    
    success_count = 0
    fail_count = 0
    
    for idx, row in df.iterrows():
        record_id = row['id']
        title = row['tweets_title']
        address = row['tweets_describe']
        current_city = row['tweets_location']
        
        logger.info(f"[{idx+1}/{len(df)}] 处理: {title}")
        logger.info(f"   地址: {address}")
        logger.info(f"   当前城市: {current_city}")
        
        # 2. 使用AI提取地区信息
        # 优先使用地址，如果地址太短（比如只有"分店"），结合标题和城市
        context_city = current_city if current_city else ""
        full_address_info = address
        if len(address) < 5:
            full_address_info = f"{context_city} {title} {address}"
            
        location_info = ai_service.extract_location_info(full_address_info, context_city)
        
        if location_info and location_info.get('adcode'):
            adcode = location_info.get('adcode')
            district = location_info.get('district', '')
            ai_city = location_info.get('city', '')
            
            logger.info(f"   ✅ AI识别结果: {ai_city} {district} (Code: {adcode})")
            
            if not dry_run:
                try:
                    # 3. 更新数据库
                    update_sql = """
                        UPDATE tweets 
                        SET tweets_location_code = :adcode
                    """
                    update_params = {'adcode': adcode, 'id': record_id}
                    
                    # 如果当前城市为空，或者为占位符，或者AI返回了更具体的城市/区县信息
                    # 我们优先使用AI返回的城市信息（如果有）
                    invalid_cities = [None, '', 'Unknown', '未知', '地址未知']
                    if current_city in invalid_cities and ai_city:
                        update_sql += ", tweets_location = :city"
                        update_params['city'] = ai_city
                    
                    update_sql += " WHERE id = :id"
                    
                    db.execute_update(update_sql, update_params)
                    success_count += 1
                except Exception as e:
                    logger.error(f"   ❌ 更新数据库失败: {e}")
                    fail_count += 1
            else:
                logger.info("   [试运行] 不更新数据库")
                success_count += 1
                
        else:
            logger.warning("   ⚠️  AI无法识别地区编码")
            fail_count += 1
            
        # 避免请求过快
        time.sleep(1)
        
    logger.info("="*50)
    logger.info(f"处理完成。成功: {success_count}, 失败: {fail_count}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='使用AI补全缺失的地区编码')
    parser.add_argument('--limit', type=int, default=100, help='处理数量限制')
    parser.add_argument('--city', type=str, help='按城市筛选')
    parser.add_argument('--dry-run', action='store_true', help='试运行模式')
    
    args = parser.parse_args()
    
    fill_missing_locations(limit=args.limit, city_filter=args.city, dry_run=args.dry_run)

