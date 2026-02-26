
import sys
import os
import argparse
import logging
import re
import time
import json
from datetime import datetime

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

from app.services.dianping_service import DianpingService
from base.database import db

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def ensure_table_exists():
    """确保备份表存在（用于单次模式）"""
    sql = """
    CREATE TABLE IF NOT EXISTS dianping_images (
        id INT AUTO_INCREMENT PRIMARY KEY,
        restaurant_name VARCHAR(255) NOT NULL,
        city VARCHAR(100),
        image_url TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_restaurant (restaurant_name)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    try:
        db.execute_update(sql)
    except Exception as e:
        logger.error(f"创建表失败: {e}")

def save_images_to_backup_db(restaurant_name: str, city: str, images: list):
    """保存图片到备份表（单次模式使用）"""
    if not images:
        return
    
    count = 0
    for img_url in images:
        try:
            # 检查图片是否已存在
            check_sql = "SELECT id FROM dianping_images WHERE restaurant_name = :name AND image_url = :url LIMIT 1"
            exists = db.execute_query(check_sql, {'name': restaurant_name, 'url': img_url})
            if not exists.empty:
                continue

            sql = """
            INSERT INTO dianping_images (restaurant_name, city, image_url, created_at)
            VALUES (:name, :city, :url, :time)
            """
            params = {
                'name': restaurant_name,
                'city': city,
                'url': img_url,
                'time': datetime.now()
            }
            db.execute_update(sql, params)
            count += 1
        except Exception as e:
            logger.error(f"保存图片失败: {e}")
            
    if count > 0:
        logger.info(f"成功保存 {count} 张新图片到备份表")

def update_tweet_images(tweet_id: int, current_images: list, new_images: list):
    """
    更新推文的图片字段
    将新图片追加到现有图片列表，直到达到上限
    """
    if not new_images:
        return 0
    
    # 合并并去重
    final_images = current_images[:]
    added_count = 0
    
    for img in new_images:
        if img not in final_images:
            final_images.append(img)
            added_count += 1
    
    # 限制最大数量为 9
    if len(final_images) > 9:
        final_images = final_images[:9]
    
    if added_count == 0:
        return 0
        
    # 动态尝试更新，如果遇到 Data too long 则减少图片
    while True:
        try:
            new_json = json.dumps(final_images, ensure_ascii=False)
            
            sql = "UPDATE tweets SET tweets_img = :images WHERE id = :id"
            db.execute_update(sql, {'images': new_json, 'id': tweet_id})
            
            real_added = len(final_images) - len(current_images)
            logger.info(f"  ✅ 推文 #{tweet_id} 更新成功: 原有 {len(current_images)} 张, 新增 {real_added} 张, 现共 {len(final_images)} 张")
            return real_added
            
        except Exception as e:
            err_msg = str(e)
            # 捕获 MySQL 1406 Data too long 错误
            if ("Data too long" in err_msg or "1406" in err_msg):
                if len(final_images) > len(current_images):
                    logger.warning(f"  ⚠️ 数据过长(len={len(new_json)})，减少一张新图片重试...")
                    final_images.pop()
                else:
                    logger.error(f"  ❌ 即使只保留原有图片也无法更新(可能是原数据编码或格式问题): {e}")
                    return 0
            else:
                logger.error(f"  ❌ 更新推文图片失败: {e}")
                return 0

def extract_city(address):
    """从地址中提取城市名"""
    if not address:
        return None
    
    # 1. 匹配 xx市
    match = re.search(r'(.+?市)', address)
    if match:
        city = match.group(1)
        if len(city) < 10:
            return city
            
    # 2. 匹配直辖市/特别行政区
    special_cities = ['北京', '上海', '天津', '重庆', '香港', '澳门']
    for city in special_cities:
        if city in address:
            return city
            
    # 3. 如果地址很短，直接作为城市名
    if len(address) <= 3:
        return address
        
    return None

def crawl_batch(limit=None, offset=0, headless=False, force=False):
    """批量爬取数据库中的餐厅"""
    logger.info("开始批量爬取模式...")
    
    # 1. 查询餐厅列表（包含现有的图片字段）
    sql = """
    SELECT id, tweets_title, tweets_location, tweets_img
    FROM tweets 
    ORDER BY id DESC
    """
    if limit:
        sql += f" LIMIT {limit} OFFSET {offset}"
    
    try:
        df = db.execute_query(sql)
        if df.empty:
            logger.warning("未找到任何餐厅数据")
            return
    except Exception as e:
        logger.error(f"查询数据库失败: {e}")
        return

    logger.info(f"查询到 {len(df)} 条记录，准备开始处理")
    
    # 2. 初始化爬虫服务
    service = DianpingService(headless=headless)
    
    # 记录当前城市，避免重复切换
    current_city = None
    
    try:
        for index, row in df.iterrows():
            tweet_id = row['id']
            restaurant_name = str(row['tweets_title']).strip()
            location = str(row['tweets_location']).strip() if row['tweets_location'] else ""
            
            # 解析现有图片
            current_images = []
            try:
                img_data = row['tweets_img']
                if img_data:
                    if isinstance(img_data, str):
                        current_images = json.loads(img_data)
                    elif isinstance(img_data, list):
                        current_images = img_data
            except:
                pass
                
            if not isinstance(current_images, list):
                current_images = []
            
            # 检查是否已满
            if len(current_images) >= 9:
                if not force:
                    logger.info(f"[{index + 1}/{len(df)}] {restaurant_name}: 图片已满 ({len(current_images)} 张)，跳过")
                    continue
                else:
                    logger.info(f"[{index + 1}/{len(df)}] {restaurant_name}: 图片已满但强制执行")
            
            # 计算还需要多少张
            needed_count = 9 - len(current_images)
            if needed_count <= 0:
                needed_count = 0 # force 模式下可能为负，但 crawl_images 需要正数
            
            # 即使 force 模式，如果 needed_count 为 0，也许我们想尝试获取更多来替换？
            # 但用户说 "不是替代...而是直到上限"，所以我们只补齐
            if needed_count == 0 and not force:
                 continue

            if not restaurant_name:
                continue
                
            logger.info(f"[{index + 1}/{len(df)}] 处理: {restaurant_name} (地址: {location})")
            logger.info(f"  现有 {len(current_images)} 张图片，计划爬取 {needed_count} 张")
            
            # 提取城市
            city = extract_city(location)
            if not city:
                logger.warning("  无法从地址提取城市，跳过")
                continue
                
            try:
                # 切换城市
                if city != current_city:
                    if service.select_city(city):
                        current_city = city
                    else:
                        logger.error(f"  切换城市失败: {city}，跳过")
                        continue
                
                # 搜索餐厅
                detail_url = service.search_restaurant(restaurant_name)
                if not detail_url:
                    logger.warning(f"  未找到餐厅: {restaurant_name}")
                    continue
                
                # 爬取图片
                # 注意：DianpingService.crawl_images 默认是10，我们传入 needed_count
                # 为了保险，多爬一点点（比如 +2），以防有些图无效，但不要太多
                target_fetch = max(needed_count + 2, 5) 
                
                images = service.crawl_images(detail_url, max_images=target_fetch)
                
                if images:
                    # 更新到 tweets 表
                    update_tweet_images(tweet_id, current_images, images)
                else:
                    logger.warning("  未爬取到图片")
                
                # 适当休息
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"  处理失败: {e}")
                # 尝试重启浏览器
                try:
                    service.close()
                except:
                    pass
                service = DianpingService(headless=headless)
                current_city = None 
                
    finally:
        service.close()

def main():
    parser = argparse.ArgumentParser(description='大众点评餐厅图片爬虫')
    parser.add_argument('--mode', type=str, choices=['single', 'batch'], default='single', help='模式: single(单次), batch(批量)')
    parser.add_argument('--name', type=str, help='餐厅名称 (单次模式必填)')
    parser.add_argument('--city', type=str, help='城市名称 (单次模式必填)')
    parser.add_argument('--headless', action='store_true', help='无头模式运行')
    parser.add_argument('--limit', type=int, default=None, help='最大处理数量 (批量模式)')
    parser.add_argument('--offset', type=int, default=0, help='偏移量 (批量模式)')
    parser.add_argument('--force', action='store_true', help='强制即使图片已满也尝试爬取（但不会超过9张）')
    
    args = parser.parse_args()
    
    ensure_table_exists()
    
    if args.mode == 'batch':
        crawl_batch(limit=args.limit, offset=args.offset, headless=args.headless, force=args.force)
    else:
        if not args.name or not args.city:
            logger.error("单次模式需要提供 --name 和 --city")
            return
        
        logger.info(f"开始任务: 爬取 [{args.city}] 的 [{args.name}]")
        service = DianpingService(headless=args.headless)
        try:
            if not service.select_city(args.city):
                logger.error(f"无法选择城市: {args.city}，程序退出")
                return
            detail_url = service.search_restaurant(args.name)
            if not detail_url:
                logger.error(f"未找到餐厅: {args.name}")
                return
            images = service.crawl_images(detail_url, max_images=20)
            if images:
                logger.info(f"共爬取到 {len(images)} 张图片")
                save_images_to_backup_db(args.name, args.city, images)
            else:
                logger.warning("未爬取到任何图片")
        except Exception as e:
            logger.error(f"任务执行失败: {e}")
        finally:
            service.close()

if __name__ == "__main__":
    main()
