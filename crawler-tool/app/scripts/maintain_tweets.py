#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一数据维护脚本
整合多个数据修复和更新功能，提供统一的命令行接口
"""
import os
import sys
import logging
import argparse
import json
import re
import time
from typing import Optional, Dict, Tuple, List
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from base.database import db
from app.services.ai_service import get_ai_paraphraser
from app.services.address_service import AddressService
from app.utils.image_utils import prepare_image_json
from base.location_utils import find_county_code
from sqlalchemy import text
import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== 修复未完成推文 ====================

def is_content_incomplete(content: str) -> Tuple[bool, str]:
    """检查推文内容是否未完成"""
    if not content or len(content.strip()) < 10:
        return True, "内容太短"
    
    content = content.strip()
    
    incomplete_patterns = [
        r'[，,]$',
        r'[、]$',
        r'[：:]$',
        r'[^。！？]{0,5}$',
    ]
    
    for pattern in incomplete_patterns:
        if re.search(pattern, content):
            return True, f"匹配模式: {pattern}"
    
    return False, ""


def fix_incomplete_tweets(
    limit: Optional[int] = None,
    offset: int = 0,
    dry_run: bool = False,
    where: Optional[str] = None,
    min_length: int = 50
):
    """修复未完成的推文内容"""
    try:
        ai_paraphraser = get_ai_paraphraser()
        
        is_available, error_msg = ai_paraphraser.check_model_available()
        if not is_available:
            logger.error(f"AI服务不可用: {error_msg}")
            return
        
        # 构建查询SQL
        sql = """
            SELECT 
                id,
                tweets_title,
                tweets_content,
                tweets_describe,
                tweets_location
            FROM tweets
            WHERE tweets_type_pid = 5
        """
        
        conditions = []
        params = {}
        
        if where:
            conditions.append(f"({where})")
        
        if conditions:
            sql += " AND " + " AND ".join(conditions)
        
        sql += " ORDER BY id ASC"
        
        if limit:
            sql += f" LIMIT {limit}"
        if offset:
            sql += f" OFFSET {offset}"
        
        logger.info("查询推文...")
        df = db.execute_query(sql, params)
        
        if df.empty:
            logger.warning("没有找到需要处理的推文")
            return
        
        logger.info(f"找到 {len(df)} 条推文，开始处理...")
        
        fixed_count = 0
        failed_count = 0
        
        for idx, row in df.iterrows():
            tweet_id = row['id']
            title = row['tweets_title']
            content = row['tweets_content']
            
            is_incomplete, reason = is_content_incomplete(content)
            
            if not is_incomplete:
                continue
            
            if len(content) < min_length:
                continue
            
            logger.info(f"\n处理推文 #{tweet_id}: {title[:50]}...")
            logger.info(f"  问题: {reason}")
            
            if dry_run:
                logger.info("  [试运行] 将修复此推文")
                fixed_count += 1
                continue
            
            try:
                # 使用AI重新生成内容
                paraphrased_title, paraphrased_desc, type_cid, comments = ai_paraphraser.paraphrase_restaurant(
                    restaurant_info={'name': title, 'address': row.get('tweets_describe', '')},
                    original_title=title,
                    original_description=content,
                    tweet_id=tweet_id,
                    auto_generate_comments=False
                )
                
                if paraphrased_desc and len(paraphrased_desc) > len(content):
                    update_sql = "UPDATE tweets SET tweets_content = :content WHERE id = :id"
                    db.execute_update(update_sql, {'content': paraphrased_desc, 'id': tweet_id})
                    logger.info(f"  ✅ 修复成功，新长度: {len(paraphrased_desc)} 字符")
                    fixed_count += 1
                else:
                    logger.warning(f"  ⚠️  生成的内容不够长，跳过")
                    failed_count += 1
                    
            except Exception as e:
                logger.error(f"  ❌ 修复失败: {e}")
                failed_count += 1
        
        logger.info(f"\n处理完成: 修复 {fixed_count} 条，失败 {failed_count} 条")
        
    except Exception as e:
        logger.error(f"修复未完成推文失败: {e}", exc_info=True)
        raise


# ==================== 更新推文分类 ====================

def update_tweet_categories(
    limit: Optional[int] = None,
    offset: int = 0,
    batch_size: int = 50,
    dry_run: bool = False,
    where: Optional[str] = None,
    skip_existing: bool = False
):
    """批量更新推文类目"""
    try:
        ai_paraphraser = get_ai_paraphraser()
        
        is_available, error_msg = ai_paraphraser.check_model_available()
        if not is_available:
            logger.error(f"AI服务不可用: {error_msg}")
            return
        
        # 构建查询SQL
        sql = """
            SELECT 
                id,
                tweets_title,
                tweets_content,
                tweets_describe,
                tweets_type_cid
            FROM tweets
            WHERE tweets_type_pid = 5
        """
        
        conditions = []
        params = {}
        
        if skip_existing:
            conditions.append("(tweets_type_cid IS NULL OR tweets_type_cid = '')")
        
        if where:
            conditions.append(f"({where})")
        
        if conditions:
            sql += " AND " + " AND ".join(conditions)
        
        sql += " ORDER BY id ASC"
        
        if limit:
            sql += f" LIMIT {limit}"
        if offset:
            sql += f" OFFSET {offset}"
        
        logger.info("查询推文...")
        df = db.execute_query(sql, params)
        
        if df.empty:
            logger.warning("没有找到需要处理的推文")
            return
        
        logger.info(f"找到 {len(df)} 条推文，开始处理...")
        
        updated_count = 0
        failed_count = 0
        
        for idx, row in df.iterrows():
            tweet_id = row['id']
            title = row['tweets_title']
            content = row['tweets_content']
            describe = row['tweets_describe']
            
            logger.info(f"\n处理推文 #{tweet_id}: {title[:50]}...")
            
            if dry_run:
                logger.info("  [试运行] 将更新分类")
                updated_count += 1
                continue
            
            try:
                type_cid = ai_paraphraser.classify_to_type_cid(title, content, describe)
                
                if type_cid:
                    update_sql = "UPDATE tweets SET tweets_type_cid = :type_cid WHERE id = :id"
                    db.execute_update(update_sql, {'type_cid': type_cid, 'id': tweet_id})
                    logger.info(f"  ✅ 更新成功: {type_cid}")
                    updated_count += 1
                else:
                    logger.warning(f"  ⚠️  无法获取分类")
                    failed_count += 1
                    
            except Exception as e:
                logger.error(f"  ❌ 更新失败: {e}")
                failed_count += 1
        
        logger.info(f"\n处理完成: 更新 {updated_count} 条，失败 {failed_count} 条")
        
    except Exception as e:
        logger.error(f"更新推文分类失败: {e}", exc_info=True)
        raise


# ==================== 更新所属地区 ====================

def update_location_from_code(
    limit: Optional[int] = None,
    offset: int = 0,
    dry_run: bool = False,
    where: Optional[str] = None,
    force: bool = False
):
    """根据tweets_location_code更新tweets_location"""
    try:
        sql = """
            SELECT 
                id,
                tweets_title,
                tweets_location,
                tweets_location_code
            FROM tweets
            WHERE tweets_type_pid = 5
        """
        
        conditions = []
        params = {}
        
        if not force:
            conditions.append("(tweets_location IS NULL OR tweets_location = '' OR tweets_location_code IS NOT NULL)")
        
        if where:
            conditions.append(f"({where})")
        
        if conditions:
            sql += " AND " + " AND ".join(conditions)
        
        sql += " ORDER BY id ASC"
        
        if limit:
            sql += f" LIMIT {limit}"
        if offset:
            sql += f" OFFSET {offset}"
        
        logger.info("查询推文...")
        df = db.execute_query(sql, params)
        
        if df.empty:
            logger.warning("没有找到需要处理的推文")
            return
        
        logger.info(f"找到 {len(df)} 条推文，开始处理...")
        
        updated_count = 0
        failed_count = 0
        
        for idx, row in df.iterrows():
            tweet_id = row['id']
            title = row['tweets_title']
            location_code = row['tweets_location_code']
            current_location = row['tweets_location']
            
            if not location_code:
                continue
            
            logger.info(f"\n处理推文 #{tweet_id}: {title[:50]}...")
            logger.info(f"  当前地区: {current_location}, 代码: {location_code}")
            
            if dry_run:
                logger.info("  [试运行] 将更新地区")
                updated_count += 1
                continue
            
            try:
                location_name = find_county_code(location_code, reverse=True)
                
                if location_name:
                    update_sql = "UPDATE tweets SET tweets_location = :location WHERE id = :id"
                    db.execute_update(update_sql, {'location': location_name, 'id': tweet_id})
                    logger.info(f"  ✅ 更新成功: {location_name}")
                    updated_count += 1
                else:
                    logger.warning(f"  ⚠️  无法找到地区名称")
                    failed_count += 1
                    
            except Exception as e:
                logger.error(f"  ❌ 更新失败: {e}")
                failed_count += 1
        
        logger.info(f"\n处理完成: 更新 {updated_count} 条，失败 {failed_count} 条")
        
    except Exception as e:
        logger.error(f"更新所属地区失败: {e}", exc_info=True)
        raise


# ==================== 从高德API更新 ====================

def update_tweets_from_amap(
    limit: Optional[int] = None,
    offset: int = 0,
    dry_run: bool = False,
    where: Optional[str] = None,
    skip_existing: bool = False,
    type_pid: Optional[int] = None,
    city: Optional[str] = None
):
    """使用高德地图API批量更新推文信息"""
    try:
        address_service = AddressService()
        
        sql = """
            SELECT 
                id,
                tweets_title,
                tweets_describe,
                tweets_location
            FROM tweets
            WHERE tweets_type_pid = :type_pid
        """
        
        params = {'type_pid': type_pid or 5}
        conditions = []
        
        if skip_existing:
            conditions.append("(tweets_describe IS NULL OR tweets_describe = '')")
        
        if city:
            conditions.append("tweets_location = :city")
            params['city'] = city
        
        if where:
            conditions.append(f"({where})")
        
        if conditions:
            sql += " AND " + " AND ".join(conditions)
        
        sql += " ORDER BY id ASC"
        
        if limit:
            sql += f" LIMIT {limit}"
        if offset:
            sql += f" OFFSET {offset}"
        
        logger.info("查询推文...")
        df = db.execute_query(sql, params)
        
        if df.empty:
            logger.warning("没有找到需要处理的推文")
            return
        
        logger.info(f"找到 {len(df)} 条推文，开始处理...")
        
        updated_count = 0
        failed_count = 0
        
        for idx, row in df.iterrows():
            tweet_id = row['id']
            title = row['tweets_title']
            current_city = row['tweets_location'] or city or '上海'
            
            logger.info(f"\n处理推文 #{tweet_id}: {title[:50]}...")
            
            if dry_run:
                logger.info("  [试运行] 将更新地址信息")
                updated_count += 1
                continue
            
            try:
                result = address_service.search_restaurant_address(title, current_city)
                
                if result and result.get('address'):
                    address = result['address']
                    city_name = result.get('city', current_city)
                    if city_name and city_name.endswith('市'):
                        city_name = city_name[:-1]
                    
                    update_sql = """
                        UPDATE tweets 
                        SET tweets_describe = :address,
                            tweets_location = :city,
                            tweets_location_code = :adcode
                        WHERE id = :id
                    """
                    db.execute_update(update_sql, {
                        'address': address,
                        'city': city_name,
                        'adcode': result.get('adcode', ''),
                        'id': tweet_id
                    })
                    logger.info(f"  ✅ 更新成功: {address}")
                    updated_count += 1
                else:
                    logger.warning(f"  ⚠️  高德API未找到地址")
                    failed_count += 1
                
                time.sleep(0.1)  # 避免API限流
                    
            except Exception as e:
                logger.error(f"  ❌ 更新失败: {e}")
                failed_count += 1
        
        logger.info(f"\n处理完成: 更新 {updated_count} 条，失败 {failed_count} 条")
        
    except Exception as e:
        logger.error(f"从高德API更新失败: {e}", exc_info=True)
        raise


# ==================== 验证图片 ====================

def validate_image_url(url: str, timeout: int = 5) -> bool:
    """验证图片URL是否可访问"""
    if not url or not url.strip():
        return False
    
    url = url.strip()
    
    if not url.startswith('http'):
        return False
    
    try:
        response = requests.head(url, timeout=timeout, allow_redirects=True)
        content_type = response.headers.get('Content-Type', '').lower()
        return response.status_code == 200 and ('image' in content_type or 'jpeg' in content_type or 'png' in content_type)
    except:
        return False


def validate_images(
    limit: Optional[int] = None,
    offset: int = 0,
    batch_size: int = 50,
    dry_run: bool = False,
    where: Optional[str] = None,
    max_workers: int = 10
):
    """验证和清理无效图片URL"""
    try:
        sql = """
            SELECT 
                id,
                tweets_title,
                tweets_img
            FROM tweets
            WHERE tweets_type_pid = 5
        """
        
        conditions = []
        params = {}
        
        if where:
            conditions.append(f"({where})")
        
        if conditions:
            sql += " AND " + " AND ".join(conditions)
        
        sql += " ORDER BY id ASC"
        
        if limit:
            sql += f" LIMIT {limit}"
        if offset:
            sql += f" OFFSET {offset}"
        
        logger.info("查询推文...")
        df = db.execute_query(sql, params)
        
        if df.empty:
            logger.warning("没有找到需要处理的推文")
            return
        
        logger.info(f"找到 {len(df)} 条推文，开始处理...")
        
        validated_count = 0
        fixed_count = 0
        failed_count = 0
        
        for idx, row in df.iterrows():
            tweet_id = row['id']
            title = row['tweets_title']
            images_json = row['tweets_img']
            
            logger.info(f"\n处理推文 #{tweet_id}: {title[:50]}...")
            
            if not images_json:
                continue
            
            try:
                if isinstance(images_json, str):
                    images = json.loads(images_json)
                else:
                    images = images_json
                
                if not isinstance(images, list):
                    images = [images]
                
                valid_images = []
                invalid_count = 0
                
                for img_url in images:
                    if not img_url:
                        invalid_count += 1
                        continue
                    
                    if dry_run:
                        is_valid = True  # 试运行时不验证
                    else:
                        is_valid = validate_image_url(img_url)
                    
                    if is_valid:
                        valid_images.append(img_url)
                    else:
                        invalid_count += 1
                        logger.debug(f"  无效图片: {img_url[:50]}...")
                
                if invalid_count > 0:
                    if dry_run:
                        logger.info(f"  [试运行] 将删除 {invalid_count} 个无效图片")
                        fixed_count += 1
                    else:
                        if valid_images:
                            new_images_json = json.dumps(valid_images, ensure_ascii=False)
                            update_sql = "UPDATE tweets SET tweets_img = :images WHERE id = :id"
                            db.execute_update(update_sql, {'images': new_images_json, 'id': tweet_id})
                            logger.info(f"  ✅ 清理成功，删除 {invalid_count} 个无效图片")
                            fixed_count += 1
                        else:
                            logger.warning(f"  ⚠️  所有图片都无效，但保留原值")
                            failed_count += 1
                else:
                    logger.info(f"  ✅ 所有图片有效")
                    validated_count += 1
                    
            except Exception as e:
                logger.error(f"  ❌ 处理失败: {e}")
                failed_count += 1
        
        logger.info(f"\n处理完成: 有效 {validated_count} 条，修复 {fixed_count} 条，失败 {failed_count} 条")
        
    except Exception as e:
        logger.error(f"验证图片失败: {e}", exc_info=True)
        raise


# ==================== 主函数 ====================

def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description='统一数据维护脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
功能说明:
  fix-incomplete     修复未完成的推文内容
  update-categories  更新推文分类
  update-location    从代码更新所属地区
  update-from-amap   从高德API更新地址信息
  validate-images    验证和清理无效图片URL

示例:
  # 修复未完成推文
  python3 maintain_tweets.py fix-incomplete --limit 100 --dry-run
  
  # 更新推文分类
  python3 maintain_tweets.py update-categories --limit 100 --skip-existing
  
  # 更新所属地区
  python3 maintain_tweets.py update-location --limit 100
  
  # 从高德API更新
  python3 maintain_tweets.py update-from-amap --city 上海 --limit 100
  
  # 验证图片
  python3 maintain_tweets.py validate-images --limit 100 --dry-run
        """
    )
    
    subparsers = parser.add_subparsers(dest='action', help='要执行的操作')
    
    # 修复未完成推文
    parser_fix = subparsers.add_parser('fix-incomplete', help='修复未完成的推文内容')
    parser_fix.add_argument('--limit', type=int, help='限制处理数量')
    parser_fix.add_argument('--offset', type=int, default=0, help='起始偏移量')
    parser_fix.add_argument('--dry-run', action='store_true', help='试运行模式')
    parser_fix.add_argument('--where', type=str, help='WHERE子句')
    parser_fix.add_argument('--min-length', type=int, default=50, help='最小内容长度')
    
    # 更新推文分类
    parser_cat = subparsers.add_parser('update-categories', help='更新推文分类')
    parser_cat.add_argument('--limit', type=int, help='限制处理数量')
    parser_cat.add_argument('--offset', type=int, default=0, help='起始偏移量')
    parser_cat.add_argument('--batch-size', type=int, default=50, help='批次大小')
    parser_cat.add_argument('--dry-run', action='store_true', help='试运行模式')
    parser_cat.add_argument('--where', type=str, help='WHERE子句')
    parser_cat.add_argument('--skip-existing', action='store_true', help='跳过已有分类')
    
    # 更新所属地区
    parser_loc = subparsers.add_parser('update-location', help='从代码更新所属地区')
    parser_loc.add_argument('--limit', type=int, help='限制处理数量')
    parser_loc.add_argument('--offset', type=int, default=0, help='起始偏移量')
    parser_loc.add_argument('--dry-run', action='store_true', help='试运行模式')
    parser_loc.add_argument('--where', type=str, help='WHERE子句')
    parser_loc.add_argument('--force', action='store_true', help='强制更新所有记录')
    
    # 从高德API更新
    parser_amap = subparsers.add_parser('update-from-amap', help='从高德API更新地址信息')
    parser_amap.add_argument('--limit', type=int, help='限制处理数量')
    parser_amap.add_argument('--offset', type=int, default=0, help='起始偏移量')
    parser_amap.add_argument('--dry-run', action='store_true', help='试运行模式')
    parser_amap.add_argument('--where', type=str, help='WHERE子句')
    parser_amap.add_argument('--skip-existing', action='store_true', help='跳过已有地址')
    parser_amap.add_argument('--type-pid', type=int, help='推文类型父ID')
    parser_amap.add_argument('--city', type=str, help='城市名称')
    
    # 验证图片
    parser_img = subparsers.add_parser('validate-images', help='验证和清理无效图片URL')
    parser_img.add_argument('--limit', type=int, help='限制处理数量')
    parser_img.add_argument('--offset', type=int, default=0, help='起始偏移量')
    parser_img.add_argument('--batch-size', type=int, default=50, help='批次大小')
    parser_img.add_argument('--dry-run', action='store_true', help='试运行模式')
    parser_img.add_argument('--where', type=str, help='WHERE子句')
    parser_img.add_argument('--max-workers', type=int, default=10, help='最大并发数')
    
    args = parser.parse_args()
    
    if not args.action:
        parser.print_help()
        return
    
    try:
        if args.action == 'fix-incomplete':
            fix_incomplete_tweets(
                limit=args.limit,
                offset=args.offset,
                dry_run=args.dry_run,
                where=args.where,
                min_length=args.min_length
            )
        elif args.action == 'update-categories':
            update_tweet_categories(
                limit=args.limit,
                offset=args.offset,
                batch_size=args.batch_size,
                dry_run=args.dry_run,
                where=args.where,
                skip_existing=args.skip_existing
            )
        elif args.action == 'update-location':
            update_location_from_code(
                limit=args.limit,
                offset=args.offset,
                dry_run=args.dry_run,
                where=args.where,
                force=args.force
            )
        elif args.action == 'update-from-amap':
            update_tweets_from_amap(
                limit=args.limit,
                offset=args.offset,
                dry_run=args.dry_run,
                where=args.where,
                skip_existing=args.skip_existing,
                type_pid=args.type_pid,
                city=args.city
            )
        elif args.action == 'validate-images':
            validate_images(
                limit=args.limit,
                offset=args.offset,
                batch_size=args.batch_size,
                dry_run=args.dry_run,
                where=args.where,
                max_workers=args.max_workers
            )
        else:
            parser.print_help()
            
    except KeyboardInterrupt:
        logger.info("\n用户中断操作")
    except Exception as e:
        logger.error(f"执行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

