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
import random
from typing import Optional, Dict, Tuple, List
from concurrent.futures import ThreadPoolExecutor, as_completed

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
from app.services.address_service import AddressService
from app.utils.image_utils import prepare_image_json
from app.utils.category_utils import get_cuisine_type_cid
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


# ==================== AI检查内容完整性 + Trip.com改写 ====================

def _looks_like_tripcom_field_style(content: str) -> bool:
    """快速识别“评分/评价数/地址”字段堆砌式内容"""
    if not content:
        return False
    markers = ["评分：", "评价数：", "地址："]
    return all(m in content for m in markers) and "/5" in content


def ai_check_and_rewrite_incomplete_with_tripcom(
    limit: Optional[int] = None,
    offset: int = 0,
    dry_run: bool = False,
    where: Optional[str] = None,
    type_pid: int = 5,
    recrawl: bool = True,
    show_browser: bool = False,
    sleep_seconds: float = 1.0,
    skip_rewritten: bool = True
):
    """
    全库扫描推文：用AI判断正文是否完整；不完整则用 Trip.com 用户评价参考改写成小红书风格正文。
    标题保持不变，仅更新 tweets_content。
    """
    ai = get_ai_paraphraser()
    is_available, error_msg = ai.check_model_available()
    if not is_available:
        logger.error(f"AI服务不可用: {error_msg}")
        return

    # 浏览器（可选复用）
    page = None
    if recrawl:
        try:
            from app.services.tripcom_service import create_browser_page
            page = create_browser_page(headless=(not show_browser))
        except Exception as e:
            logger.warning(f"创建Trip.com浏览器失败，将退化为不重抓（仅用存量内容）: {e}")
            recrawl = False

    sql = """
        SELECT id, tweets_title, tweets_content, tweets_describe, tweets_location
        FROM tweets
        WHERE 1=1
    """
    params = {}
    if type_pid:
        sql += " AND tweets_type_pid = :type_pid"
        params["type_pid"] = type_pid
    if skip_rewritten:
        sql += " AND (tweets_content IS NULL OR tweets_content NOT LIKE '%- Trip.com：%')"
        sql += " AND (tweets_content IS NULL OR tweets_content NOT LIKE '%- Trip.com:%')"
    if where:
        sql += f" AND ({where})"
    sql += " ORDER BY id ASC"
    if limit:
        sql += " LIMIT :limit"
        params["limit"] = limit
    if offset:
        sql += " OFFSET :offset"
        params["offset"] = offset

    df = db.execute_query(sql, params)
    if df.empty:
        logger.info("没有找到需要扫描的推文")
        return

    total = len(df)
    checked = 0
    rewritten = 0
    skipped = 0
    failed = 0

    from app.services.tripcom_service import search_and_crawl_restaurant_detail

    for idx, row in df.iterrows():
        tweet_id = int(row["id"])
        title = (row.get("tweets_title") or "").strip()
        content = (row.get("tweets_content") or "").strip()
        address = (row.get("tweets_describe") or "").strip()
        city = (row.get("tweets_location") or "").strip()

        checked += 1
        logger.info(f"\n[{checked}/{total}] 检查推文 #{tweet_id}: {title[:50]}")

        # 快速跳过：已改写标记
        if skip_rewritten and (("- Trip.com：" in content) or ("- Trip.com:" in content)):
            skipped += 1
            continue

        # 1) AI判定完整性（字段堆砌的直接判不完整）
        if _looks_like_tripcom_field_style(content):
            is_complete, reason = False, "字段堆砌风格"
        else:
            is_complete, reason = ai.check_note_complete(title, content)

        if is_complete:
            logger.info(f"  ✅ 内容完整，跳过（原因: {reason}）")
            skipped += 1
            continue

        logger.info(f"  ⚠️ 内容不完整，将尝试Trip.com改写（原因: {reason}）")

        # 2) 获取Trip.com评价（默认重抓）
        trip_reviews = []
        if recrawl and page:
            try:
                info = search_and_crawl_restaurant_detail(
                    keyword=title,
                    city=city or "",
                    page=page,
                    extract_address=False,
                    extract_comments=True,
                    min_image_size=240,
                    max_images=5
                )
                if info:
                    comments = info.get("comments") or []
                    for c in comments:
                        if isinstance(c, dict):
                            t = (c.get("content") or "").strip()
                        else:
                            t = str(c).strip()
                        if len(t) >= 12:
                            trip_reviews.append(t)
                    trip_reviews = trip_reviews[:10]
            except Exception as e:
                logger.warning(f"  ⚠️ Trip.com抓评价失败: {e}")

        # 3) 改写正文（标题保持不变）
        # 评分/评价数：尽量从旧内容中解析（若没有也不影响）
        rating = None
        review_count = None
        try:
            m = re.search(r"评分[:：]\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*5", content)
            if m:
                rating = float(m.group(1))
            m = re.search(r"评价数[:：]\s*(\d+)\s*条", content)
            if m:
                review_count = int(m.group(1))
        except Exception:
            pass

        new_title, new_desc = ai.paraphrase_tripcom_restaurant_note(
            restaurant_name=title,
            restaurant_desc="",
            tripcom_rating=rating,
            tripcom_review_count=review_count,
            tripcom_reviews=trip_reviews,
            include_score_line=False,
            include_address_line=False,
            address_text=""
        )

        if not new_desc:
            logger.warning("  ❌ 改写失败（返回为空），跳过")
            failed += 1
            continue

        max_len = 2000
        if len(new_desc) > max_len:
            new_desc = new_desc[:max_len] + "..."

        if dry_run:
            logger.info("  [dry-run] 将更新 tweets_content（标题不变）")
            logger.info(f"  新正文长度: {len(new_desc)}")
            rewritten += 1
        else:
            try:
                db.execute_update(
                    "UPDATE tweets SET tweets_content = :content WHERE id = :id",
                    {"content": new_desc, "id": tweet_id}
                )
                logger.info("  ✅ 更新成功")
                rewritten += 1
            except Exception as e:
                logger.error(f"  ❌ 更新失败: {e}")
                failed += 1

        if sleep_seconds and sleep_seconds > 0:
            time.sleep(sleep_seconds)

    if page:
        try:
            page.quit()
        except Exception:
            pass

    logger.info("\n" + "=" * 60)
    logger.info(f"完成：扫描 {checked} 条；改写 {rewritten} 条；跳过 {skipped} 条；失败 {failed} 条")

# ==================== 更新推文分类 (AI方式) ====================

def update_tweet_categories_ai(
    limit: Optional[int] = None,
    offset: int = 0,
    batch_size: int = 50,
    dry_run: bool = False,
    where: Optional[str] = None,
    skip_existing: bool = False
):
    """批量更新推文类目（使用AI）"""
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


# ==================== 去重与重分类 (规则方式) ====================

def find_duplicate_restaurants(
    city: Optional[str] = None,
    since_date: Optional[str] = None,
    since_datetime: Optional[str] = None,
    tweets_type_pid: int = 5
) -> List[Dict]:
    """查找重复的餐厅记录"""
    where_clauses = [f"tweets_type_pid = {tweets_type_pid}"]
    params = {}
    
    if city:
        where_clauses.append("(tweets_location = :city OR tweets_location LIKE :city_like)")
        params['city'] = city
        params['city_like'] = f"{city}%"
    
    if since_datetime:
        where_clauses.append("create_time >= :since_datetime")
        params['since_datetime'] = since_datetime
    elif since_date:
        where_clauses.append("create_time >= :since_date")
        params['since_date'] = since_date
    
    where_sql = " AND ".join(where_clauses)
    
    # 查找重复的餐厅名称
    query = f"""
        SELECT 
            tweets_title,
            COUNT(*) as count,
            GROUP_CONCAT(id ORDER BY id DESC) as ids,
            MAX(id) as keep_id,
            GROUP_CONCAT(id ORDER BY id DESC SEPARATOR ',') as all_ids
        FROM tweets
        WHERE {where_sql}
        GROUP BY tweets_title
        HAVING COUNT(*) > 1
        ORDER BY count DESC, tweets_title
    """
    
    logger.info(f"查询重复餐厅...")
    df = db.execute_query(query, params)
    
    duplicates = []
    for _, row in df.iterrows():
        title = row['tweets_title']
        count = row['count']
        keep_id = row['keep_id']
        all_ids = [int(id_str) for id_str in str(row['all_ids']).split(',')]
        delete_ids = [id for id in all_ids if id != keep_id]
        
        duplicates.append({
            'title': title,
            'count': count,
            'keep_id': keep_id,
            'delete_ids': delete_ids
        })
    
    return duplicates


def delete_duplicate_records(delete_ids: List[int], dry_run: bool = False) -> int:
    """删除重复的记录"""
    if not delete_ids:
        return 0
    
    if dry_run:
        logger.info(f"[试运行] 将删除 {len(delete_ids)} 条重复记录: {delete_ids}")
        return len(delete_ids)
    
    ids_str = ','.join(map(str, delete_ids))
    query = f"DELETE FROM tweets WHERE id IN ({ids_str})"
    
    try:
        with db.engine.connect() as conn:
            result = conn.execute(text(query))
            conn.commit()
            return result.rowcount
    except Exception as e:
        logger.error(f"❌ 删除记录失败: {e}")
        raise


def reclassify_restaurants_rule(
    city: Optional[str] = None,
    since_date: Optional[str] = None,
    since_datetime: Optional[str] = None,
    limit: Optional[int] = None,
    dry_run: bool = False,
    tweets_type_pid: int = 5
) -> Dict:
    """重新分类餐厅的二级类目（使用规则）并更新地区"""
    where_clauses = [f"tweets_type_pid = {tweets_type_pid}"]
    params = {}
    
    if city:
        where_clauses.append("(tweets_location = :city OR tweets_location LIKE :city_like)")
        params['city'] = city
        params['city_like'] = f"{city}%"
    
    if since_datetime:
        where_clauses.append("create_time >= :since_datetime")
        params['since_datetime'] = since_datetime
    elif since_date:
        where_clauses.append("create_time >= :since_date")
        params['since_date'] = since_date
    
    where_sql = " AND ".join(where_clauses)
    
    query = f"""
        SELECT 
            id,
            tweets_title,
            tweets_content,
            tweets_describe,
            tweets_type_cid,
            tweets_location
        FROM tweets
        WHERE {where_sql}
        ORDER BY id DESC
    """
    
    if limit:
        query += " LIMIT :limit"
        params['limit'] = limit
    
    logger.info("查询需要重新分类的餐厅...")
    df = db.execute_query(query, params)
    
    stats = {
        'total': len(df),
        'updated': 0,
        'unchanged': 0,
        'failed': 0,
        'errors': []
    }
    
    logger.info(f"找到 {stats['total']} 个餐厅需要处理")
    
    for idx, row in df.iterrows():
        tweet_id = row['id']
        title = row['tweets_title']
        content = row['tweets_content'] or ''
        describe = row['tweets_describe'] or ''
        old_cid = row['tweets_type_cid'] or ''
        
        try:
            # 1. 提取菜系类型
            cuisine_type = ''
            if '菜系：' in content:
                parts = content.split('菜系：')
                if len(parts) > 1:
                    cuisine_type = parts[1].split('\n')[0].strip().split('，')[0].split(',')[0].strip()
            
            if not cuisine_type:
                # 简单关键词匹配
                for kw in ['火锅', '川菜', '粤菜', '西餐', '日料', '烧烤', '咖啡', '面']:
                    if kw in title or kw in content:
                        cuisine_type = kw
                        break
            
            # 2. 重新分类
            new_cid = get_cuisine_type_cid(
                cuisine_type=cuisine_type,
                description=content,
                restaurant_name=title
            )
            
            # 3. 更新所属地区
            current_location = row['tweets_location'] or ''
            address = describe
            new_location = None
            
            if address and '区' in address and '·' not in current_location:
                try:
                    district_match = re.search(r'([\u4e00-\u9fa5]{2,5}区)', address)
                    if district_match:
                        district = district_match.group(1)
                        if address.index(district) < 15:
                            base_city = current_location
                            if base_city.endswith('市'):
                                base_city = base_city[:-1]
                            if not base_city and '市' in address:
                                city_match = re.search(r'([\u4e00-\u9fa5]{2,5}市)', address)
                                if city_match:
                                    base_city = city_match.group(1)[:-1]
                            
                            if base_city:
                                new_location = f"{base_city}·{district}"
                except:
                    pass
            
            # 检查是否需要更新
            needs_update = False
            update_fields = []
            update_params = {'tweet_id': tweet_id}
            
            if new_cid != old_cid:
                needs_update = True
                update_fields.append("tweets_type_cid = :new_cid")
                update_params['new_cid'] = new_cid
                
            if new_location and new_location != current_location:
                needs_update = True
                update_fields.append("tweets_location = :new_location")
                update_params['new_location'] = new_location
            
            if not needs_update:
                stats['unchanged'] += 1
                continue
            
            if dry_run:
                logger.info(f"[试运行] ID={tweet_id}, 更新: CID {old_cid}->{new_cid}, Loc {current_location}->{new_location}")
                stats['updated'] += 1
            else:
                update_query = f"UPDATE tweets SET {', '.join(update_fields)} WHERE id = :tweet_id"
                db.execute_update(update_query, update_params)
                stats['updated'] += 1
                
        except Exception as e:
            logger.error(f"处理ID={tweet_id}失败: {e}")
            stats['failed'] += 1
            stats['errors'].append(f"ID={tweet_id}: {str(e)}")
    
    return stats


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
            
            if dry_run:
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
            
            if dry_run:
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
                
                time.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"  ❌ 更新失败: {e}")
                failed_count += 1
        
        logger.info(f"\n处理完成: 更新 {updated_count} 条，失败 {failed_count} 条")
        
    except Exception as e:
        logger.error(f"从高德API更新失败: {e}", exc_info=True)
        raise


# ==================== 验证图片 ====================

def validate_image_url(url: str, timeout: int = 5) -> bool:
    """验证图片URL是否可访问且不是头像"""
    if not url or not url.strip():
        return False
    
    url = url.strip()
    
    if not url.startswith('http'):
        return False
        
    # 过滤头像特征
    if any(kw in url.lower() for kw in ['headphoto', 'avatar', 'icon', 'logo', 'user']):
        return False
        
    # 过滤小尺寸图片 (Trip.com 特征)
    import re
    size_match = re.search(r'_[CR]_(\d+)_(\d+)', url)
    if size_match:
        w, h = int(size_match.group(1)), int(size_match.group(2))
        if w < 100 or h < 100:
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
                        is_valid = True
                    else:
                        is_valid = validate_image_url(img_url)
                    
                    if is_valid:
                        valid_images.append(img_url)
                    else:
                        invalid_count += 1
                
                if invalid_count > 0:
                    if dry_run:
                        logger.info(f"  [试运行] 将删除 {invalid_count} 个无效图片")
                        fixed_count += 1
                    else:
                        # 即使没有有效图片了，也更新为空列表
                        new_images_json = json.dumps(valid_images, ensure_ascii=False)
                        update_sql = "UPDATE tweets SET tweets_img = :images WHERE id = :id"
                        db.execute_update(update_sql, {'images': new_images_json, 'id': tweet_id})
                        logger.info(f"  ✅ 清理成功，删除 {invalid_count} 个无效图片 (剩余 {len(valid_images)} 个)")
                        fixed_count += 1
                else:
                    validated_count += 1
                    
            except Exception as e:
                logger.error(f"  ❌ 处理失败: {e}")
                failed_count += 1
        
        logger.info(f"\n处理完成: 有效 {validated_count} 条，修复 {fixed_count} 条，失败 {failed_count} 条")
        
    except Exception as e:
        logger.error(f"验证图片失败: {e}", exc_info=True)
        raise


# ==================== 评论生成功能 ====================

def generate_comments_for_tweet(tweet_id: int, tweet_content: str, tweet_title: str, comment_count: int = None) -> List[Dict]:
    """为指定推文生成评论"""
    if comment_count is None:
        comment_count = random.randint(35, 75)
    
    logger.info(f"为推文 {tweet_id} ({tweet_title}) 生成 {comment_count} 条评论...")
    
    ai_paraphraser = get_ai_paraphraser()
    comments = []
    
    prompt = f"""请为以下餐厅/美食内容生成{comment_count}条真实、自然的大众点评风格评论。

餐厅名称：{tweet_title}
内容：{tweet_content}

要求：
1. 评论要真实自然，符合大众点评的风格
2. 评论内容要多样化，包括：口味评价、环境评价、服务评价、价格评价、推荐理由等
3. 每条评论长度控制在20-100字之间
4. 评论要有真实感，不要过于夸张
5. 返回JSON格式，格式如下：
{{
    "comments": [
        {{"content": "评论内容1"}},
        {{"content": "评论内容2"}},
        ...
    ]
}}

只返回JSON，不要其他内容。"""
    
    try:
        response = ai_paraphraser.paraphrase(prompt)
        
        # 解析JSON响应
        if isinstance(response, str):
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:]
            if response.startswith('```'):
                response = response[3:]
            if response.endswith('```'):
                response = response[:-3]
            response = response.strip()
            
            try:
                data = json.loads(response)
            except json.JSONDecodeError:
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                else:
                    logger.error(f"无法解析AI响应为JSON: {response[:200]}")
                    return []
        else:
            data = response
        
        # 提取评论列表
        if isinstance(data, dict) and 'comments' in data:
            comment_list = data['comments']
        elif isinstance(data, list):
            comment_list = data
        else:
            logger.error(f"AI响应格式不正确: {type(data)}")
            return []
        
        # 为每条评论生成随机用户名并构建评论数据
        for comment_item in comment_list:
            if isinstance(comment_item, dict):
                content = comment_item.get('content', '')
            elif isinstance(comment_item, str):
                content = comment_item
            else:
                continue
            
            if not content or len(content.strip()) < 5:
                continue
            
            comments.append({
                'tweets_id': tweet_id,
                'client_user_id': 1,  # 默认用户ID
                'evaluate_content': content.strip(),
                'evaluate_time': None
            })
        
        logger.info(f"成功生成 {len(comments)} 条评论")
        return comments
        
    except Exception as e:
        logger.error(f"生成评论失败: {str(e)}", exc_info=True)
        return []


def insert_comments(comments: List[Dict]) -> int:
    """批量插入评论到数据库"""
    if not comments:
        return 0
    
    try:
        success_count = 0
        for comment in comments:
            try:
                sql = """
                    INSERT INTO tweets_evaluate (client_user_id, tweets_id, evaluate_content)
                    VALUES (:client_user_id, :tweets_id, :evaluate_content)
                """
                params = {
                    'client_user_id': comment.get('client_user_id', 1),
                    'tweets_id': comment['tweets_id'],
                    'evaluate_content': comment['evaluate_content']
                }
                
                db.execute_update(sql, params)
                success_count += 1
            except Exception as e:
                logger.error(f"插入评论失败: {str(e)}")
        
        return success_count
        
    except Exception as e:
        logger.error(f"批量插入评论失败: {str(e)}", exc_info=True)
        return 0


def generate_comments(
    tweet_id: Optional[int] = None,
    count: Optional[int] = None,
    limit: int = 100
):
    """为推文生成评论"""
    try:
        if tweet_id:
            query = "SELECT id, tweets_title, tweets_content FROM tweets WHERE id = :tweet_id"
            tweets = db.execute_query(query, {'tweet_id': tweet_id})
        else:
            query = "SELECT id, tweets_title, tweets_content FROM tweets ORDER BY id DESC LIMIT :limit"
            tweets = db.execute_query(query, {'limit': limit})
        
        if tweets.empty:
            logger.warning("没有找到推文")
            return
        
        logger.info(f"找到 {len(tweets)} 条推文，开始生成评论...")
        
        total_comments = 0
        total_inserted = 0
        
        for idx, row in tweets.iterrows():
            tweet_id_val = row['id']
            tweet_title = row['tweets_title']
            tweet_content = row['tweets_content']
            
            logger.info(f"\n处理推文 {idx + 1}/{len(tweets)}: ID={tweet_id_val}, 标题={tweet_title}")
            
            comments = generate_comments_for_tweet(
                tweet_id=tweet_id_val,
                tweet_content=tweet_content,
                tweet_title=tweet_title,
                comment_count=count
            )
            
            if comments:
                total_comments += len(comments)
                inserted = insert_comments(comments)
                total_inserted += inserted
                logger.info(f"推文 {tweet_id_val}: 生成 {len(comments)} 条，插入 {inserted} 条")
            else:
                logger.warning(f"推文 {tweet_id_val}: 未能生成评论")
        
        logger.info(f"\n完成！总共生成 {total_comments} 条评论，成功插入 {total_inserted} 条")
        
    except Exception as e:
        logger.error(f"执行失败: {str(e)}", exc_info=True)
        raise


# ==================== 图片搜索功能 ====================

def search_images(
    method: str = "bing",
    city: str = "上海",
    limit: Optional[int] = None,
    tweet_id: Optional[int] = None,
    force: bool = False,
    since_time: Optional[str] = None
):
    """搜索并更新推文图片"""
    try:
        from app.utils.search_images import process_restaurants
        
        stats = process_restaurants(
            limit=limit,
            city=city,
            tweet_id=tweet_id,
            skip_existing=not force,
            since_time=since_time,
            method=method
        )
        
        logger.info("\n处理完成")
        logger.info(f"总计: {stats['total']} 个")
        logger.info(f"已处理: {stats['processed']} 个")
        logger.info(f"成功: {stats['success']} 个")
        logger.info(f"失败: {stats['failed']} 个")
        logger.info(f"跳过: {stats['skipped']} 个")
        
    except Exception as e:
        logger.error(f"搜索图片失败: {e}", exc_info=True)
        raise


# ==================== 从Trip.com更新图片 ====================

def update_images_from_tripcom(
    limit: Optional[int] = None,
    offset: int = 0,
    dry_run: bool = False,
    where: Optional[str] = None,
    since_time: Optional[str] = None,
    city: Optional[str] = None,
    max_images: int = 20,
    min_image_size: int = 220,
    show_browser: bool = False,
    delay_min: float = 0.5,
    delay_max: float = 1.5,
    force: bool = False,
    img_max_length: int = 20000
):
    """从Trip.com搜索并更新餐厅图片（使用严格黑名单和更多图片）"""
    try:
        from app.services.tripcom_service import search_and_crawl_restaurant_detail, create_browser_page
        from app.utils.image_utils import update_restaurant_images
        from app.utils.search_images import BingImageSearcher
        
        # 创建图片验证器（使用严格黑名单）
        image_validator = BingImageSearcher()
        
        sql = """
            SELECT 
                id,
                tweets_title,
                tweets_location,
                tweets_img
            FROM tweets
            WHERE tweets_type_pid = 5
        """
        
        conditions = []
        params = {}
        
        if city:
            conditions.append("tweets_location = :city")
            params['city'] = city
            
        if since_time:
            conditions.append("create_time >= :since_time")
            params['since_time'] = since_time
            
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
            
        # 强制最小尺寸阈值：默认220，且不允许小于220（避免大量非高清/占位小图混入）
        try:
            min_image_size = int(min_image_size)
        except Exception:
            min_image_size = 220
        if min_image_size < 220:
            logger.warning(f"min_image_size={min_image_size} 过小，已自动提升到 220")
            min_image_size = 220

        logger.info(f"找到 {len(df)} 条推文，开始处理...")
        logger.info(f"配置: 最大图片数={max_images}, 最小图片尺寸={min_image_size}x{min_image_size}, 使用严格黑名单")
        
        updated_count = 0
        failed_count = 0
        skipped_count = 0
        
        # 创建浏览器实例（在整个脚本运行期间保持打开，提高效率）
        logger.info("正在启动浏览器...")
        browser_page = create_browser_page(headless=(not show_browser))
        if not browser_page:
            logger.error("无法创建浏览器，退出")
            return
        
        try:
            for idx, row in df.iterrows():
                tweet_id = row['id']
                title = row['tweets_title']
                current_city = row['tweets_location'] or city or ''
                existing_imgs = row.get('tweets_img')
                
                logger.info(f"\n处理推文 #{tweet_id}: {title[:50]}...")
                
                if dry_run:
                    logger.info("  [试运行] 将搜索并更新图片")
                    updated_count += 1
                    continue

                # 默认跳过：如果已有图片数量 >= max_images 且未强制刷新
                if not force and existing_imgs:
                    try:
                        existing_list = json.loads(existing_imgs) if isinstance(existing_imgs, str) else existing_imgs
                        if isinstance(existing_list, list) and len(existing_list) >= max_images:
                            logger.info(f"  ⏭️  已有 {len(existing_list)} 张图片（>= {max_images}），跳过（可用 --force 强制更新）")
                            skipped_count += 1
                            continue
                    except Exception:
                        pass
                    
                try:
                    # 检查浏览器是否仍然有效
                    try:
                        _ = browser_page.url
                    except Exception as e:
                        logger.warning(f"浏览器连接已断开，重新创建浏览器: {e}")
                        try:
                            browser_page.quit()
                        except:
                            pass
                        browser_page = create_browser_page(headless=(not show_browser))
                        if not browser_page:
                            logger.error("无法重新创建浏览器，跳过此条")
                            failed_count += 1
                            continue
                        logger.info("✅ 浏览器已重新创建")
                    
                    # 1. 搜索并抓取详情页图片（使用浏览器方式，获取更多图片）
                    detail_info = search_and_crawl_restaurant_detail(
                        keyword=title,
                        city=current_city,
                        page=browser_page,
                        extract_address=False,  # 不提取地址，加快速度
                        extract_comments=False,  # 不提取评论，加快速度
                        min_image_size=min_image_size,
                        max_images=max_images * 2  # 先获取更多图片，后续再用黑名单过滤
                    )
                    
                    if not detail_info or not detail_info.get('images'):
                        logger.warning(f"  ⚠️  未找到Trip.com详情页或未提取到图片")
                        failed_count += 1
                        continue
                    
                    raw_images = detail_info['images']
                    logger.info(f"  📸 原始提取到 {len(raw_images)} 张图片")
                    
                    # 2. 使用严格黑名单过滤图片（提速：够用就停 + 本地快速过滤）
                    valid_images = []
                    filtered_count = 0
                    seen_urls = set()

                    # 本地快速过滤：关键词 + 尺寸（尽量减少网络HEAD/GET）
                    invalid_kw = (
                        'logo', 'avatar', 'icon', 'placeholder', 'data:image',
                        'headphoto', 'user', 'tripcdn.com/packages',
                        # Trip.com banner/marketing assets（常见带品牌logo/文案，非餐厅实拍图）
                        '/images/fd/tg/',
                        # Trip.com 通用占位图（本地快速过滤，避免进入网络验证）
                        '05e2j12000cjsihpq0418',
                        '05e5k12000cjsg4e48d91',
                        '05e2z12000cjsfsqb7a2b',
                        '05e5112000f3br0wz5303',
                        '05e6e12000cjso3ro7bee',
                        '05e4f12000cjsls8g082a',
                        '0m74z2224tibbx728d6ef',
                        # 实测：翠湖广东乡下菜命中的banner（包含logo/文案）
                        'cghzgvw7usiazm7daaa0kqyhcl8653',
                    )
                    size_re = re.compile(r'_[CR]_(\d+)_(\d+)')

                    for img_url in raw_images:
                        if len(valid_images) >= max_images:
                            break
                        if not img_url or not isinstance(img_url, str) or not img_url.startswith('http'):
                            filtered_count += 1
                            continue

                        img_url = img_url.strip()
                        if not img_url or img_url in seen_urls:
                            filtered_count += 1
                            continue
                        seen_urls.add(img_url)

                        low = img_url.lower()
                        if any(k in low for k in invalid_kw):
                            filtered_count += 1
                            continue

                        # Trip.com 常见尺寸编码：_C_宽_高_ / _R_宽_高_
                        m = size_re.search(img_url)
                        if m:
                            try:
                                w, h = int(m.group(1)), int(m.group(2))
                                if w < min_image_size or h < min_image_size:
                                    filtered_count += 1
                                    continue
                            except Exception:
                                pass

                        # 严格黑名单 + 可访问性验证（会发HEAD/GET，较慢）
                        if image_validator.validate_image_url(img_url):
                            valid_images.append(img_url)
                        else:
                            filtered_count += 1
                            logger.debug(f"    ❌ 过滤无效图片: {img_url[:60]}...")
                    
                    logger.info(f"  ✅ 通过严格验证: {len(valid_images)} 张，过滤: {filtered_count} 张")
                    
                    # 3. 限制最大图片数量（保留前N张）
                    if len(valid_images) > max_images:
                        valid_images = valid_images[:max_images]
                        logger.info(f"  📝 限制为前 {max_images} 张图片")
                    
                    if not valid_images:
                        logger.warning(f"  ⚠️  没有有效的图片（全部被过滤）")
                        failed_count += 1
                        continue
                    
                    # 4. 更新数据库（tweets_img 字段为 longtext 时可存更多图片）
                    if update_restaurant_images(tweet_id, valid_images, max_length=img_max_length):
                        logger.info(f"  ✅ 更新成功: {len(valid_images)} 张图片")
                        updated_count += 1
                    else:
                        logger.error(f"  ❌ 更新数据库失败")
                        failed_count += 1
                        
                    # 避免请求过快
                    try:
                        dmin = float(delay_min)
                        dmax = float(delay_max)
                        if dmin < 0:
                            dmin = 0
                        if dmax < dmin:
                            dmax = dmin
                    except Exception:
                        dmin, dmax = 0.5, 1.5
                    time.sleep(random.uniform(dmin, dmax))
                    
                except Exception as e:
                    logger.error(f"  ❌ 处理失败: {e}", exc_info=True)
                    failed_count += 1
                    
        finally:
            # 关闭浏览器
            if browser_page:
                try:
                    logger.info("\n所有图片更新完成，正在关闭浏览器...")
                    browser_page.quit()
                    logger.info("浏览器已关闭")
                except Exception as e:
                    logger.warning(f"关闭浏览器时出错: {e}")
        
        logger.info(f"\n处理完成: 更新 {updated_count} 条，跳过 {skipped_count} 条，失败 {failed_count} 条")
        
    except Exception as e:
        logger.error(f"从Trip.com更新图片失败: {e}", exc_info=True)
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
  update-categories  更新推文分类 (AI方式)
  deduplicate        去重并重分类 (规则方式)
  update-location    从代码更新所属地区
  update-from-amap   从高德API更新地址信息
  validate-images    验证和清理无效图片URL
  generate-comments  为推文生成评论
  search-images      搜索并更新推文图片 (Bing/Amap)
  update-tripcom-img 从Trip.com搜索并更新图片（使用严格黑名单，支持更多图片）

示例:
  # 从Trip.com更新指定时间后的图片（默认最多20张，最小尺寸200x200）
  python3 maintain_tweets.py update-tripcom-img --since-time "2025-11-30 08:03:12" --city 上海
  
  # 每个餐厅最多30张图片，最小尺寸300x300（最低阈值）
  python3 maintain_tweets.py update-tripcom-img --city 上海 --max-images 30 --min-image-size 300
  
  # 只处理前10个餐厅
  python3 maintain_tweets.py update-tripcom-img --city 上海 --limit 10 --max-images 25
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
    
    # 去重与重分类 (规则方式)
    parser_dedup = subparsers.add_parser('deduplicate', help='去重并重分类 (规则方式)')
    parser_dedup.add_argument('--city', type=str, help='城市筛选')
    parser_dedup.add_argument('--since-date', type=str, help='起始日期')
    parser_dedup.add_argument('--since-datetime', type=str, help='起始日期时间')
    parser_dedup.add_argument('--limit', type=int, help='限制处理数量')
    parser_dedup.add_argument('--dry-run', action='store_true', help='试运行模式')
    parser_dedup.add_argument('--skip-deduplicate', action='store_true', help='跳过去重')
    parser_dedup.add_argument('--skip-reclassify', action='store_true', help='跳过重分类')
    
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
    
    # 生成评论
    parser_comments = subparsers.add_parser('generate-comments', help='为推文生成评论')
    parser_comments.add_argument('--tweet-id', type=int, help='指定推文ID')
    parser_comments.add_argument('--count', type=int, help='每条推文的评论数量')
    parser_comments.add_argument('--limit', type=int, default=100, help='处理推文数量限制')
    
    # 搜索图片
    parser_search_img = subparsers.add_parser('search-images', help='搜索并更新推文图片')
    parser_search_img.add_argument('--method', type=str, default='bing', choices=['bing', 'amap'], help='搜索方法')
    parser_search_img.add_argument('--city', type=str, help='城市名称')
    parser_search_img.add_argument('--limit', type=int, help='限制处理数量')
    parser_search_img.add_argument('--tweet-id', type=int, help='指定推文ID')
    parser_search_img.add_argument('--force', action='store_true', help='强制更新已有图片')
    parser_search_img.add_argument('--since-time', type=str, help='起始时间（格式：YYYY-MM-DD HH:MM:SS）')
    
    # 从Trip.com更新图片
    parser_trip = subparsers.add_parser('update-tripcom-img', help='从Trip.com搜索并更新图片（使用严格黑名单）')
    parser_trip.add_argument('--limit', type=int, help='限制处理数量')
    parser_trip.add_argument('--offset', type=int, default=0, help='起始偏移量')
    parser_trip.add_argument('--dry-run', action='store_true', help='试运行模式')
    parser_trip.add_argument('--where', type=str, help='WHERE子句')
    parser_trip.add_argument('--since-time', type=str, help='起始时间')
    parser_trip.add_argument('--city', type=str, help='城市名称')
    parser_trip.add_argument('--max-images', type=int, default=20, help='每个餐厅最大图片数量（默认：20）')
    parser_trip.add_argument('--min-image-size', type=int, default=220, help='最小图片尺寸（宽或高，默认：220，且最低不小于220）')
    parser_trip.add_argument('--show-browser', action='store_true', help='显示浏览器窗口（默认无头更快）')
    parser_trip.add_argument('--delay-min', type=float, default=0.5, help='每条推文处理完成后的最小延迟秒数（默认：0.5）')
    parser_trip.add_argument('--delay-max', type=float, default=1.5, help='每条推文处理完成后的最大延迟秒数（默认：1.5）')
    parser_trip.add_argument('--force', action='store_true', help='强制更新（即使已有足够图片也重新抓取）')
    parser_trip.add_argument('--img-max-length', type=int, default=20000, help='tweets_img JSON最大长度（默认：20000；库字段longtext可更大）')

    # AI检查完整性 + Trip.com改写正文
    parser_rewrite = subparsers.add_parser('ai-rewrite-incomplete-tripcom', help='AI检查内容完整性，不完整则基于Trip.com评价改写正文（标题不变）')
    parser_rewrite.add_argument('--limit', type=int, help='限制处理数量')
    parser_rewrite.add_argument('--offset', type=int, default=0, help='起始偏移量')
    parser_rewrite.add_argument('--dry-run', action='store_true', help='试运行模式')
    parser_rewrite.add_argument('--where', type=str, help='WHERE子句')
    parser_rewrite.add_argument('--type-pid', type=int, default=5, help='推文类型父ID（默认：5-美食；填0表示不限制）')
    parser_rewrite.add_argument('--no-recrawl', action='store_true', help='不去Trip.com重抓评价，仅用存量内容（不推荐）')
    parser_rewrite.add_argument('--show-browser', action='store_true', help='显示浏览器窗口（默认无头更快）')
    parser_rewrite.add_argument('--sleep', type=float, default=1.0, help='每条之间睡眠秒数')
    parser_rewrite.add_argument('--no-skip-rewritten', action='store_true', help='不跳过已包含“- Trip.com：”标记的推文')
    
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
            update_tweet_categories_ai(
                limit=args.limit,
                offset=args.offset,
                batch_size=args.batch_size,
                dry_run=args.dry_run,
                where=args.where,
                skip_existing=args.skip_existing
            )
        elif args.action == 'deduplicate':
            # 去重步骤
            if not args.skip_deduplicate:
                duplicates = find_duplicate_restaurants(
                    city=args.city,
                    since_date=args.since_date,
                    since_datetime=args.since_datetime
                )
                if duplicates:
                    logger.info(f"找到 {len(duplicates)} 组重复餐厅")
                    total_delete = sum(len(d['delete_ids']) for d in duplicates)
                    logger.info(f"总共将删除 {total_delete} 条重复记录")
                    if not args.dry_run:
                        confirm = input("确认删除？(yes/no): ")
                        if confirm.lower() == 'yes':
                            for dup in duplicates:
                                delete_duplicate_records(dup['delete_ids'])
                    else:
                        logger.info("[试运行] 不执行删除")
            
            # 重分类步骤
            if not args.skip_reclassify:
                stats = reclassify_restaurants_rule(
                    city=args.city,
                    since_date=args.since_date,
                    since_datetime=args.since_datetime,
                    limit=args.limit,
                    dry_run=args.dry_run
                )
                logger.info(f"重分类完成: 更新 {stats['updated']}, 不变 {stats['unchanged']}")
                
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
        elif args.action == 'generate-comments':
            generate_comments(
                tweet_id=args.tweet_id,
                count=args.count,
                limit=args.limit
            )
        elif args.action == 'search-images':
            search_images(
                method=args.method,
                city=args.city,
                limit=args.limit,
                tweet_id=args.tweet_id,
                force=args.force,
                since_time=args.since_time
            )
        elif args.action == 'update-tripcom-img':
            update_images_from_tripcom(
                limit=args.limit,
                offset=args.offset,
                dry_run=args.dry_run,
                where=args.where,
                since_time=args.since_time,
                city=args.city,
                max_images=args.max_images,
                min_image_size=args.min_image_size,
                show_browser=args.show_browser,
                delay_min=args.delay_min,
                delay_max=args.delay_max,
                force=args.force,
                img_max_length=args.img_max_length
            )
        elif args.action == 'ai-rewrite-incomplete-tripcom':
            ai_check_and_rewrite_incomplete_with_tripcom(
                limit=args.limit,
                offset=args.offset,
                dry_run=args.dry_run,
                where=args.where,
                type_pid=args.type_pid,
                recrawl=(not args.no_recrawl),
                show_browser=args.show_browser,
                sleep_seconds=args.sleep,
                skip_rewritten=(not args.no_skip_rewritten)
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
