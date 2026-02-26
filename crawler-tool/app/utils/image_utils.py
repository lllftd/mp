"""图片处理工具函数模块 - 用于餐厅图片搜索和更新"""
import json
import logging
import time
from typing import List, Dict, Optional
from urllib.parse import urlparse, urlunparse

from base.database import db
from sqlalchemy import text

logger = logging.getLogger(__name__)


def shorten_url(url: str) -> str:
    """缩短URL，移除查询参数"""
    try:
        parsed = urlparse(url)
        # 移除查询参数和片段
        shortened = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
        return shortened
    except:
        return url


def prepare_image_json(image_urls: List[str], max_length: int = 20000) -> tuple[str, List[str]]:
    """
    准备图片JSON字符串，确保不超过长度限制
    
    Args:
        image_urls: 图片URL列表
        max_length: 最大长度限制
        
    Returns:
        (JSON字符串, 最终URL列表)
    """
    if not image_urls:
        return '[]', []
    
    # 先尝试缩短URL
    shortened_urls = [shorten_url(url) for url in image_urls]
    img_json = json.dumps(shortened_urls, ensure_ascii=False)
    
    # 如果还是太长，逐步减少图片数量
    final_urls = shortened_urls.copy()
    while len(img_json) > max_length and len(final_urls) > 1:
        final_urls = final_urls[:-1]
        img_json = json.dumps(final_urls, ensure_ascii=False)
    
    # 如果单个URL就超过限制，截断URL
    if len(img_json) > max_length and len(final_urls) == 1:
        url = final_urls[0]
        max_url_length = max_length - 5  # JSON格式开销
        if len(url) > max_url_length:
            final_urls[0] = url[:max_url_length]
            img_json = json.dumps(final_urls, ensure_ascii=False)
    
    # 最终检查
    if len(img_json) > max_length:
        logger.warning(f"图片JSON超过限制 ({len(img_json)} > {max_length})，尝试截断")
        img_json = img_json[:max_length]
        last_bracket = img_json.rfind(']')
        if last_bracket > 0:
            img_json = img_json[:last_bracket + 1]
        else:
            logger.error("无法生成有效的JSON格式")
            return '[]', []
    
    return img_json, final_urls


def update_restaurant_images(tweet_id: int, image_urls: List[str], max_length: int = 20000) -> bool:
    """
    更新餐厅图片到数据库
    
    Args:
        tweet_id: 推文ID
        image_urls: 图片URL列表
        max_length: 字段最大长度（默认20000；若数据库字段为 longtext 可支持更长）
        
    Returns:
        是否成功
    """
    try:
        img_json, final_urls = prepare_image_json(image_urls, max_length)
        
        if not final_urls:
            logger.warning(f"没有有效的图片URL")
            return False
        
        sql = """
            UPDATE tweets 
            SET tweets_img = :images
            WHERE id = :tweet_id
        """
        params = {
            'images': img_json,
            'tweet_id': tweet_id
        }
        
        with db.engine.connect() as conn:
            conn.execute(text(sql), params)
            conn.commit()
        
        logger.info(f"  ✅ 成功更新图片: {len(final_urls)} 张 (JSON长度: {len(img_json)}字符)")
        if len(final_urls) < len(image_urls):
            logger.warning(f"  ⚠️  原始图片数量: {len(image_urls)}，实际保存: {len(final_urls)} (因长度限制)")
        
        return True
        
    except Exception as e:
        logger.error(f"  ❌ 更新图片失败: {e}")
        return False


def build_tweets_query(
    tweet_id: Optional[int] = None,
    city: Optional[str] = None,
    since_time: Optional[str] = None,
    skip_existing: bool = True,
    limit: Optional[int] = None
) -> tuple[str, dict]:
    """
    构建tweets表查询SQL和参数
    
    Args:
        tweet_id: 指定推文ID
        city: 城市筛选
        since_time: 起始时间
        skip_existing: 是否跳过已有图片的记录
        limit: 限制数量
        
    Returns:
        (SQL查询语句, 参数字典)
    """
    if tweet_id:
        query = """
            SELECT id, tweets_title, tweets_content, tweets_location, tweets_img, create_time
            FROM tweets 
            WHERE id = :tweet_id
        """
        return query, {'tweet_id': tweet_id}
    
    where_clauses = []
    params = {}
    
    if city:
        where_clauses.append("tweets_location = :city")
        params['city'] = city
    
    if since_time:
        where_clauses.append("create_time >= :since_time")
        params['since_time'] = since_time
    
    if skip_existing:
        where_clauses.append("(tweets_img IS NULL OR tweets_img = '' OR tweets_img = '[]')")
    
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
    
    query = f"""
        SELECT id, tweets_title, tweets_content, tweets_location, tweets_img, create_time
        FROM tweets 
        WHERE {where_sql}
        ORDER BY create_time DESC
    """
    
    if limit:
        query += " LIMIT :limit"
        params['limit'] = limit
    
    return query, params


def process_restaurant_batch(
    restaurants,
    searcher,
    skip_existing: bool = True
) -> Dict:
    """
    批量处理餐厅图片搜索和更新（通用处理逻辑）
    
    Args:
        restaurants: 餐厅DataFrame
        searcher: 图片搜索器实例（需要有search_images方法）
        skip_existing: 是否跳过已有图片的记录
        
    Returns:
        处理结果统计
    """
    stats = {
        'total': 0,
        'processed': 0,
        'success': 0,
        'failed': 0,
        'skipped': 0,
        'errors': []
    }
    
    if restaurants.empty:
        logger.warning("未找到需要处理的餐厅")
        return stats
    
    stats['total'] = len(restaurants)
    logger.info(f"找到 {stats['total']} 个餐厅需要处理")
    
    for idx, row in restaurants.iterrows():
        tweet_id = row['id']
        restaurant_name = row['tweets_title']
        restaurant_desc = row.get('tweets_content', '')
        city_name = row.get('tweets_location') or '上海'
        existing_images = row.get('tweets_img')
        
        logger.info(f"\n处理餐厅 {stats['processed'] + 1}/{stats['total']}: ID={tweet_id}, 名称={restaurant_name}")
        stats['processed'] += 1
        
        # 检查是否已有图片
        if skip_existing and existing_images:
            try:
                existing_list = json.loads(existing_images) if isinstance(existing_images, str) else existing_images
                if isinstance(existing_list, list) and len(existing_list) >= 3:
                    logger.info(f"  ⏭️  已有 {len(existing_list)} 张图片，跳过")
                    stats['skipped'] += 1
                    continue
            except:
                pass
        
        try:
            # 搜索图片
            logger.info(f"  搜索图片: {restaurant_name}")
            image_urls = searcher.search_images(
                restaurant_name=restaurant_name,
                restaurant_desc=restaurant_desc[:200] if restaurant_desc else "",
                city=city_name,
                max_images=3
            )
            
            if not image_urls:
                logger.warning(f"  ⚠️  未找到图片")
                stats['failed'] += 1
                stats['errors'].append(f"{restaurant_name}: 未找到图片")
                continue
            
            # 验证图片URL
            valid_urls = []
            for url in image_urls:
                if hasattr(searcher, 'validate_image_url'):
                    if searcher.validate_image_url(url):
                        valid_urls.append(url)
                elif hasattr(searcher, '_is_valid_image_url'):
                    if searcher._is_valid_image_url(url):
                        valid_urls.append(url)
                else:
                    valid_urls.append(url)  # 如果没有验证方法，直接使用
            
            if not valid_urls:
                logger.warning(f"  ⚠️  没有有效的图片URL")
                stats['failed'] += 1
                stats['errors'].append(f"{restaurant_name}: 没有有效的图片URL")
                continue
            
            logger.info(f"  ✅ 找到 {len(valid_urls)} 张有效图片")
            
            # 更新数据库
            if update_restaurant_images(tweet_id, valid_urls):
                stats['success'] += 1
            else:
                stats['failed'] += 1
                stats['errors'].append(f"{restaurant_name}: 更新数据库失败")
            
            # 延迟，避免请求过快
            import time
            time.sleep(3)
            
        except Exception as e:
            logger.error(f"  ❌ 处理失败: {e}", exc_info=True)
            stats['failed'] += 1
            stats['errors'].append(f"{restaurant_name}: {str(e)}")
    
    return stats

