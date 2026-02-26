#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
临时脚本：爬取 Trip.com 页面中的价格标识（$符号）并更新到推文的二级类目（tweets_type_cid）
"""
import sys
import os
import logging
import time
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

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

from base.database import db
from app.services.tripcom_service import search_and_crawl_restaurant_detail, create_browser_page
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 价格标识到分类ID的映射（支持单个$和范围格式）
# 45: 人均50元以内
# 41: 人均50至100
# 42: 人均100至200
# 43: 人均200至300
# 44: 人均300以上
PRICE_TO_CID_MAPPING = {
    '$': '45',           # 人均50元以内（单个$）
    '$$': '41',          # 人均50至100（单个$$，或作为范围的下限）
    '$$$': '42',         # 人均100至200（单个$$$，或作为范围的下限）
    '$$$$': '43',        # 人均200至300（单个$$$$，或作为范围的下限）
    '$$$$$': '44',       # 人均300以上（单个$$$$$）
    '$-$$': '41',        # 人均50至100 (范围：$到$$)
    '$$-$$$': '42',      # 人均100至200 (范围：$$到$$$)
    '$$$-$$$$': '43',    # 人均200至300 (范围：$$$到$$$$)
    '$$$$-$$$$$': '44',  # 人均300以上 (范围：$$$$到$$$$$)
}


def price_range_to_cid(price_range: str) -> str:
    if not price_range:
        return ''
    
    # 清理价格标识（去除空格）
    price_range = price_range.strip()
    
    # 直接匹配
    if price_range in PRICE_TO_CID_MAPPING:
        return PRICE_TO_CID_MAPPING[price_range]
    
    # 处理范围格式（如 $-$$, $$-$$$, $$$-$$$$, $$$$-$$$$$）
    if '-' in price_range:
        parts = price_range.split('-')
        if len(parts) == 2:
            start_part = parts[0].strip()
            end_part = parts[1].strip()
            
            # 计算起始和结束的$数量
            start_dollars = start_part.count('$')
            end_dollars = end_part.count('$')
            
            # 根据范围判断分类ID
            # $-$$: 1个$到2个$ -> 人均50至100 (41)
            if start_dollars == 1 and end_dollars == 2:
                return '41'  # 人均50至100
            # $$-$$$: 2个$到3个$ -> 人均100至200 (42)
            elif start_dollars == 2 and end_dollars == 3:
                return '42'  # 人均100至200
            # $$$-$$$$: 3个$到4个$ -> 人均200至300 (43)
            elif start_dollars == 3 and end_dollars == 4:
                return '43'  # 人均200至300
            # $$$$-$$$$$: 4个$到5个$ -> 人均300以上 (44)
            elif start_dollars == 4 and end_dollars == 5:
                return '44'  # 人均300以上
            # 其他范围，根据结束的$数量判断
            elif end_dollars <= 2:
                return '41'  # 人均50至100
            elif end_dollars == 3:
                return '42'  # 人均100至200
            elif end_dollars == 4:
                return '43'  # 人均200至300
            else:
                return '44'  # 人均300以上
    
    # 处理单个价格标识（如 $, $$, $$$, $$$$, $$$$$）
    dollar_count = price_range.count('$')
    if dollar_count == 1:
        return '45'  # 人均50元以内
    elif dollar_count == 2:
        return '41'  # 人均50至100
    elif dollar_count == 3:
        return '42'  # 人均100至200
    elif dollar_count == 4:
        return '43'  # 人均200至300
    elif dollar_count >= 5:
        return '44'  # 人均300以上
    
    logger.warning(f"无法识别价格标识格式: '{price_range}'")
    return ''


def update_price_category_name_in_table(price_cid: str, price_range: str) -> bool:
    """
    更新分类表中价格分类的名称，使用实际爬取的价格标识
    
    Args:
        price_cid: 分类ID（如 '42'）
        price_range: 价格标识（如 '$$-$$$'）
        
    Returns:
        更新成功返回True，否则返回False
    """
    try:
        # 查找分类表（可能是 tweets_type）
        possible_tables = ['tweets_type', 'tweet_type', 'type']
        table_name = None
        
        for table in possible_tables:
            try:
                check_sql = f"SELECT COUNT(*) as count FROM {table} WHERE id = :id"
                result = db.execute_query(check_sql, {'id': int(price_cid)})
                if not result.empty and result.iloc[0]['count'] > 0:
                    table_name = table
                    break
            except Exception:
                continue
        
        if not table_name:
            logger.debug(f"未找到分类表，跳过更新分类名称")
            return False
        
        # 更新分类名称
        # 尝试不同的字段名
        for field_name in ['name', 'type_name', 'category_name', 'label', 'title']:
            try:
                update_sql = f"""
                    UPDATE {table_name} 
                    SET {field_name} = :price_range 
                    WHERE id = :id
                """
                with db.engine.connect() as conn:
                    result = conn.execute(text(update_sql), {'price_range': price_range, 'id': int(price_cid)})
                    conn.commit()
                    if result.rowcount > 0:
                        logger.debug(f"✅ 更新分类表 {table_name} 中 ID {price_cid} 的名称为: {price_range}")
                        return True
            except Exception as e:
                logger.debug(f"使用字段 {field_name} 更新失败: {e}")
                continue
        
        return False
    except Exception as e:
        logger.debug(f"更新分类名称失败: {e}")
        return False


def update_tweet_price_cid(tweet_id: int, price_range: str) -> bool:
    """
    更新推文的二级类目（tweets_type_cid），添加价格相关的分类ID
    同时更新分类表中价格分类的名称，使用实际爬取的价格标识
    
    Args:
        tweet_id: 推文ID
        price_range: 价格标识（如 $$-$$$）
        
    Returns:
        更新成功返回True，否则返回False
    """
    try:
        # 将价格标识转换为分类ID
        price_cid = price_range_to_cid(price_range)
        if not price_cid:
            logger.warning(f"无法将价格标识 '{price_range}' 映射到分类ID")
            return False
        
        # 更新分类表中的名称，使用实际爬取的价格标识
        update_price_category_name_in_table(price_cid, price_range)
        
        # 查询当前的 tweets_type_cid
        query_sql = "SELECT tweets_type_cid FROM tweets WHERE id = :id"
        df = db.execute_query(query_sql, {'id': tweet_id})
        
        if df.empty:
            logger.warning(f"推文 ID={tweet_id} 不存在")
            return False
        
        current_cid = str(df.iloc[0]['tweets_type_cid'] or '').strip()
        
        # 菜系分类ID列表（需要保留）
        CUISINE_CIDS = ['6', '8', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23', '24', '25', '26', '27', '28', '29', '30', '31', '32', '33', '34', '35', '36', '37', '38', '39', '40', '46', '47', '48', '49', '50', '51', '52', '53', '54', '55', '56', '57', '58', '59', '60', '61', '62', '63', '64']
        
        # 价格相关分类ID（需要移除旧的，添加新的）
        price_cids = ['45', '41', '42', '43', '44']
        
        # 解析当前的分类ID列表
        if current_cid:
            cid_list = [cid.strip() for cid in current_cid.split(',') if cid.strip()]
        else:
            cid_list = []
        
        # 分离菜系分类ID和价格分类ID
        cuisine_cids = [cid for cid in cid_list if cid in CUISINE_CIDS]
        other_cids = [cid for cid in cid_list if cid not in CUISINE_CIDS and cid not in price_cids]
        
        # 移除旧的价格分类ID，添加新的价格分类ID
        price_cid_list = [price_cid]  # 只保留新的价格分类ID
        
        # 合并：菜系分类 + 其他分类 + 价格分类
        new_cid_list = cuisine_cids + other_cids + price_cid_list
        
        # 如果没有任何分类，添加默认分类ID 27（特色菜）
        if not new_cid_list:
            new_cid_list = ['27']
        
        # 构建新的分类ID字符串（菜系在前，其他在后，价格分类在最后）
        cuisine_cids_sorted = sorted([cid for cid in new_cid_list if cid in CUISINE_CIDS])
        other_cids_sorted = sorted([cid for cid in new_cid_list if cid not in CUISINE_CIDS])
        new_cid = ','.join(cuisine_cids_sorted + other_cids_sorted)
        
        # 更新数据库
        update_sql = """
            UPDATE tweets 
            SET tweets_type_cid = :cid 
            WHERE id = :id
        """
        with db.engine.connect() as conn:
            result = conn.execute(text(update_sql), {'cid': new_cid, 'id': tweet_id})
            conn.commit()
            return result.rowcount > 0
            
    except Exception as e:
        logger.error(f"更新推文分类ID失败: {e}")
        return False


def crawl_price_tags(after_time="2024-10-28 12:53:44", before_time=None, limit=None, start_rank=1, end_rank=None, dry_run=False):
    """
    爬取指定时间范围内的推文价格标识并更新到二级类目（tweets_type_cid）
    
    Args:
        after_time: 起始时间，只处理此时间之后的帖子
        before_time: 结束时间，只处理此时间之前的帖子。如果为None，则自动查询最新帖子时间
        limit: 限制处理数量（可选，如果指定了start_rank和end_rank，此参数会被忽略）
        start_rank: 起始序号（按ID降序排序后的位置，从1开始）
        end_rank: 结束序号（按ID降序排序后的位置，包含此序号）
        dry_run: 如果为True，只查询不更新（预览模式）
    """
    logger.info("=" * 60)
    logger.info("开始爬取价格标识并更新到二级类目")
    logger.info(f"模式: {'预览模式（不更新数据库）' if dry_run else '更新模式'}")
    logger.info("价格标识映射（只处理范围格式，最多5个$）:")
    logger.info("  $-$$ -> 41 (人均50至100)")
    logger.info("  $$-$$$ -> 42 (人均100至200)")
    logger.info("  $$$-$$$$ -> 43 (人均200至300)")
    logger.info("  $$$$-$$$$$ -> 44 (人均300以上)")
    logger.info("=" * 60)
    
    # 如果未指定结束时间，查询最新帖子的时间
    if before_time is None:
        logger.info("未指定结束时间，查询最新帖子时间...")
        latest_sql = "SELECT MAX(create_time) as latest_time FROM tweets"
        latest_df = db.execute_query(latest_sql, {})
        if not latest_df.empty and latest_df.iloc[0]['latest_time'] is not None:
            before_time = str(latest_df.iloc[0]['latest_time'])
            logger.info(f"✅ 查询到最新帖子时间: {before_time}")
        else:
            logger.warning("⚠️ 未查询到最新帖子时间，使用默认值")
            before_time = "2025-12-31 23:59:59"
    
    # 查询需要处理的推文（按ID降序排列，从后往前处理，先处理最新的ID）
    sql = """
        SELECT id, tweets_title, tweets_location, tweets_type_cid, create_time
        FROM tweets 
        WHERE create_time >= :after_time AND create_time <= :before_time
        ORDER BY id DESC
    """
    
    # 如果指定了序号范围，使用序号范围；否则使用limit
    if start_rank is not None and end_rank is not None:
        # 计算需要查询的数量和偏移量
        offset = start_rank - 1  # SQL的OFFSET从0开始
        count = end_rank - start_rank + 1
        sql += f" LIMIT {count} OFFSET {offset}"
        logger.info(f"查询时间范围: {after_time} 到 {before_time}，序号 {start_rank}-{end_rank} 的推文...")
    elif limit:
        sql += f" LIMIT {limit}"
        logger.info(f"查询时间范围: {after_time} 到 {before_time}，限制 {limit} 条推文...")
    else:
        logger.info(f"查询时间范围: {after_time} 到 {before_time} 的所有推文...")
    
    df = db.execute_query(sql, {'after_time': after_time, 'before_time': before_time})
    
    if df.empty:
        logger.info("没有找到需要处理的推文")
        return
    
    logger.info(f"找到 {len(df)} 条推文，开始爬取价格标识...")
    
    # 确保DataFrame按ID降序排序（从大到小，先处理最新的ID）
    if 'id' in df.columns:
        df = df.sort_values('id', ascending=False).reset_index(drop=True)
        if start_rank is not None and end_rank is not None:
            logger.info(f"已按ID降序排序，序号 {start_rank}-{end_rank}，第一条ID: {df.iloc[0]['id'] if len(df) > 0 else 'N/A'} (时间: {df.iloc[0]['create_time'] if len(df) > 0 else 'N/A'}), 最后一条ID: {df.iloc[-1]['id'] if len(df) > 0 else 'N/A'} (时间: {df.iloc[-1]['create_time'] if len(df) > 0 else 'N/A'})")
        else:
            logger.info(f"已按ID降序排序（从后往前），第一条ID: {df.iloc[0]['id'] if len(df) > 0 else 'N/A'} (时间: {df.iloc[0]['create_time'] if len(df) > 0 else 'N/A'}), 最后一条ID: {df.iloc[-1]['id'] if len(df) > 0 else 'N/A'} (时间: {df.iloc[-1]['create_time'] if len(df) > 0 else 'N/A'})")
    
    success_count = 0
    fail_count = 0
    
    # 创建浏览器实例（在整个脚本运行期间保持打开）
    logger.info("正在启动浏览器...")
    browser_page = create_browser_page(headless=False)
    if not browser_page:
        logger.error("无法创建浏览器，退出")
        return
    
    try:
        for idx, row in df.iterrows():
            tweet_id = row['id']
            title = str(row['tweets_title'] or '')
            location = str(row.get('tweets_location') or '')
            current_cid = str(row.get('tweets_type_cid') or '')
            create_time = row.get('create_time', 'N/A')
            
            # 计算实际序号（考虑start_rank）
            actual_rank = start_rank + idx if start_rank is not None else idx + 1
            logger.info(f"\n[序号{actual_rank}/{start_rank + len(df) - 1 if start_rank is not None else len(df)}] 处理推文 ID={tweet_id} (创建时间: {create_time}): {title}")
            logger.info(f"  当前分类ID: {current_cid}")
            
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
                    browser_page = create_browser_page(headless=False)
                    if not browser_page:
                        logger.error("无法重新创建浏览器，跳过此条")
                        fail_count += 1
                        continue
                    logger.info("✅ 浏览器已重新创建")
                
                # 使用 search_and_crawl_restaurant_detail 函数搜索并爬取价格标识
                logger.debug(f"  🔍 在 Trip.com 搜索并爬取价格标识: {title}")
                
                # 重试逻辑：最多重试3次
                max_retries = 3
                retry_count = 0
                price_range = ''
                
                while retry_count < max_retries:
                    try:
                        # 在每次重试前检查浏览器连接
                        try:
                            _ = browser_page.url
                        except Exception:
                            logger.warning(f"  ⚠️ 浏览器连接已断开，重新创建...")
                            try:
                                browser_page.quit()
                            except:
                                pass
                            browser_page = create_browser_page(headless=False)
                            if not browser_page:
                                logger.error("无法重新创建浏览器")
                                break
                            logger.info("✅ 浏览器已重新创建")
                            time.sleep(1)
                        
                        if retry_count == 0:
                            logger.debug(f"  🔍 搜索餐厅: {title}")
                        else:
                            logger.info(f"  🔄 重试搜索 ({retry_count}/{max_retries-1}): {title}")
                        
                        # 使用 search_and_crawl_restaurant_detail 函数（复用浏览器实例）
                        # 只爬取价格标识，不爬取地址、评论和图片
                        trip_info = search_and_crawl_restaurant_detail(
                            keyword=title,
                            city=location,
                            page=browser_page,
                            extract_address=False,
                            extract_comments=False  # 不提取评论，这样也不会提取图片
                        )
                        
                        if trip_info and trip_info.get('price_range'):
                            price_range = trip_info['price_range']
                            logger.debug(f"  ✅ 成功获取价格标识: {price_range}")
                            break  # 成功获取价格标识，退出重试循环
                        else:
                            retry_count += 1
                            if retry_count < max_retries:
                                logger.warning(f"  ⚠️ 未获取到价格标识，准备重试 ({retry_count}/{max_retries-1})...")
                                time.sleep(1)
                            else:
                                logger.error(f"  ❌ 达到最大重试次数，未获取到价格标识")
                                break
                                
                    except TimeoutError as timeout_err:
                        retry_count += 1
                        logger.warning(f"  ⚠️ 浏览器超时错误 (第 {retry_count} 次): {timeout_err}")
                        
                        if retry_count < max_retries:
                            # 尝试刷新页面或重新创建浏览器
                            try:
                                logger.info(f"  🔄 尝试刷新浏览器页面...")
                                try:
                                    browser_page.refresh()
                                    time.sleep(2)
                                except:
                                    logger.info(f"  🔄 刷新失败，重新创建浏览器...")
                                    try:
                                        browser_page.quit()
                                    except:
                                        pass
                                    browser_page = create_browser_page(headless=False)
                                    if not browser_page:
                                        logger.error("无法重新创建浏览器")
                                        break
                                    logger.info("✅ 浏览器已重新创建")
                                    time.sleep(2)
                            except Exception as refresh_err:
                                logger.error(f"  ❌ 刷新浏览器失败: {refresh_err}")
                                # 尝试重新创建浏览器
                                try:
                                    browser_page.quit()
                                except:
                                    pass
                                browser_page = create_browser_page(headless=False)
                                if not browser_page:
                                    logger.error("无法重新创建浏览器")
                                    break
                                logger.info("✅ 浏览器已重新创建")
                                time.sleep(2)
                        else:
                            logger.error(f"  ❌ 达到最大重试次数，跳过此条")
                            break
                    
                    except Exception as e:
                        # 其他异常，记录并退出重试循环
                        logger.error(f"  ❌ 处理过程中出错: {e}")
                        break
                
                if price_range:
                    # 将价格标识转换为分类ID
                    price_cid = price_range_to_cid(price_range)
                    
                    if not dry_run:
                        # 更新数据库
                        if update_tweet_price_cid(tweet_id, price_range):
                            logger.info(f"  ✅ 价格标识: {price_range} -> 分类ID: {price_cid} (已更新)")
                            success_count += 1
                        else:
                            logger.warning(f"  ⚠️ 价格标识: {price_range} -> 分类ID: {price_cid} (更新失败)")
                            fail_count += 1
                    else:
                        logger.info(f"  [试运行] 价格标识: {price_range} -> 分类ID: {price_cid}")
                        success_count += 1
                else:
                    logger.warning(f"  ⚠️ 未获取到价格标识")
                    fail_count += 1
                    
            except Exception as e:
                logger.error(f"  ❌ 处理失败: {e}", exc_info=True)
                fail_count += 1
            
            # 避免请求过快
            time.sleep(1)
    
    finally:
        # 关闭浏览器
        if browser_page:
            try:
                logger.info("\n所有价格标识爬取完成，正在关闭浏览器...")
                browser_page.quit()
                logger.info("浏览器已关闭")
            except Exception as e:
                logger.warning(f"关闭浏览器时出错: {e}")
    
    logger.info(f"\n处理完成:")
    logger.info(f"  ✅ 成功: {success_count} 条")
    logger.info(f"  ❌ 失败: {fail_count} 条")
    logger.info(f"  📊 总计: {len(df)} 条")
    logger.info(f"  ℹ️  注意：所有推文都会重新处理，即使已有价格分类ID也会更新")
    if dry_run:
        logger.info("")
        logger.info("⚠️  这是预览模式，数据库未实际更新")
        logger.info("如需实际更新，请使用 --no-dry-run 参数")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='爬取 Trip.com 页面中的价格标识并更新到推文的二级类目（tweets_type_cid）')
    parser.add_argument('--limit', type=int, help='限制处理数量（如果指定了--start-rank和--end-rank，此参数会被忽略）')
    parser.add_argument('--after-time', type=str, default="2024-10-28 12:53:44", help='起始时间（格式：YYYY-MM-DD HH:MM:SS），默认为2024-10-28 12:53:44')
    parser.add_argument('--before-time', type=str, default=None, help='结束时间（格式：YYYY-MM-DD HH:MM:SS），默认为None表示查询最新帖子时间')
    parser.add_argument('--start-rank', type=int, help='起始序号（按ID降序排序后的位置，从1开始）')
    parser.add_argument('--end-rank', type=int, help='结束序号（按ID降序排序后的位置，包含此序号）')
    parser.add_argument('--no-dry-run', action='store_true', help='实际更新数据库（默认是预览模式）')
    args = parser.parse_args()
    
    crawl_price_tags(
        after_time=args.after_time, 
        before_time=args.before_time, 
        limit=args.limit,
        start_rank=args.start_rank,
        end_rank=args.end_rank,
        dry_run=not args.no_dry_run
    )

