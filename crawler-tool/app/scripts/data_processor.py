#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一数据处理脚本
整合内容处理、评论生成、图片搜索等功能
"""
import os
import sys
import logging
import argparse
import json
import random
import time
from typing import List, Dict, Optional

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.utils.process_content import process_note
from app.services.ai_service import get_ai_paraphraser
from app.services.address_service import AddressService
from app.utils.image_utils import update_restaurant_images, build_tweets_query, process_restaurant_batch
from base.database import db
from base.utils import get_random_username
from base.config import Config
from sqlalchemy import text

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== 从 process_content.py 导入 ====================
# process_note 函数已经在 process_content.py 中定义，直接导入使用


# ==================== 评论生成功能 ====================

def generate_comments_for_tweet(tweet_id: int, tweet_content: str, tweet_title: str, comment_count: int = None) -> List[Dict]:
    """
    为指定推文生成评论
    
    Args:
        tweet_id: 推文ID
        tweet_content: 推文内容
        tweet_title: 推文标题（餐厅名称）
        comment_count: 评论数量（如果为None，则随机生成35-75条）
        
    Returns:
        评论列表
    """
    if comment_count is None:
        comment_count = random.randint(35, 75)
    
    logger.info(f"为推文 {tweet_id} ({tweet_title}) 生成 {comment_count} 条评论...")
    
    ai_paraphraser = get_ai_paraphraser()
    comments = []
    
    # 生成评论提示词
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
        # 调用AI生成评论
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
            
            username = get_random_username()
            
            comments.append({
                'tweets_id': tweet_id,
                'evaluate_user': username,
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
                    INSERT INTO tweets_evaluate (tweets_id, evaluate_user, evaluate_content)
                    VALUES (:tweets_id, :evaluate_user, :evaluate_content)
                """
                params = {
                    'tweets_id': comment['tweets_id'],
                    'evaluate_user': comment['evaluate_user'],
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
        # 查询推文
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
            
            # 生成评论
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
    """
    搜索并更新推文图片
    
    Args:
        method: 搜索方法（bing/amap）
        city: 城市名称
        limit: 限制处理数量
        tweet_id: 指定推文ID
        force: 是否强制更新已有图片
        since_time: 起始时间
    """
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


# ==================== 主函数 ====================

def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description='统一数据处理脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
功能说明:
  process        处理笔记内容，提取餐厅，AI转述，上传数据库
  comments       为推文生成评论
  images         搜索并更新推文图片

示例:
  # 处理笔记内容
  python3 data_processor.py process --file notes.json --city 上海
  
  # 生成评论
  python3 data_processor.py comments --limit 100
  
  # 搜索图片
  python3 data_processor.py images --method bing --city 上海 --limit 10
        """
    )
    
    subparsers = parser.add_subparsers(dest='action', help='要执行的操作')
    
    # 处理内容
    parser_process = subparsers.add_parser('process', help='处理笔记内容')
    parser_process.add_argument('--title', type=str, help='餐厅名')
    parser_process.add_argument('--description', type=str, help='笔记描述')
    parser_process.add_argument('--city', type=str, default='上海', help='城市名称')
    parser_process.add_argument('--images', type=str, nargs='+', help='图片URL列表')
    parser_process.add_argument('--file', type=str, help='笔记文件路径（JSON格式）')
    parser_process.add_argument('--limit', type=int, help='处理数量限制')
    parser_process.add_argument('--no-comments', action='store_true', help='不生成评论')
    
    # 生成评论
    parser_comments = subparsers.add_parser('comments', help='为推文生成评论')
    parser_comments.add_argument('--tweet-id', type=int, help='指定推文ID')
    parser_comments.add_argument('--count', type=int, help='每条推文的评论数量')
    parser_comments.add_argument('--limit', type=int, default=100, help='处理推文数量限制')
    
    # 搜索图片
    parser_images = subparsers.add_parser('images', help='搜索并更新推文图片')
    parser_images.add_argument('--method', type=str, default='bing', choices=['bing', 'amap'], help='搜索方法')
    parser_images.add_argument('--city', type=str, help='城市名称')
    parser_images.add_argument('--limit', type=int, help='限制处理数量')
    parser_images.add_argument('--tweet-id', type=int, help='指定推文ID')
    parser_images.add_argument('--force', action='store_true', help='强制更新已有图片')
    parser_images.add_argument('--since-time', type=str, help='起始时间（格式：YYYY-MM-DD HH:MM:SS）')
    
    args = parser.parse_args()
    
    if not args.action:
        parser.print_help()
        return
    
    try:
        if args.action == 'process':
            # 处理笔记内容
            from app.utils.process_content import process_note
            from base.monitors import MemoryMonitor
            
            memory_monitor = MemoryMonitor()
            memory_monitor.start_monitoring()
            
            try:
                total_stats = {
                    'total_notes': 0,
                    'total_restaurants': 0,
                    'total_success': 0,
                    'total_failed': 0,
                    'total_comments': 0,
                    'all_errors': []
                }
                
                if args.file:
                    # 从文件读取笔记
                    logger.info(f"从文件读取笔记: {args.file}")
                    
                    notes = []
                    with open(args.file, 'r', encoding='utf-8') as f:
                        for line_num, line in enumerate(f, 1):
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                note = json.loads(line)
                                notes.append(note)
                            except json.JSONDecodeError as e:
                                logger.warning(f"第 {line_num} 行JSON解析失败: {e}")
                                continue
                    
                    if args.limit:
                        notes = notes[:args.limit]
                    
                    logger.info(f"共读取 {len(notes)} 条笔记")
                    
                    # 处理每条笔记
                    for idx, note in enumerate(notes, 1):
                        logger.info(f"\n处理笔记 {idx}/{len(notes)}")
                        
                        title = note.get('title', note.get('tweets_title', ''))
                        description = note.get('description', note.get('tweets_content', note.get('content', '')))
                        city = note.get('city', note.get('tweets_location', args.city))
                        images = note.get('images', note.get('tweets_img', []))
                        
                        if isinstance(images, str):
                            try:
                                images = json.loads(images)
                            except:
                                images = [images]
                        
                        if not title or not description:
                            logger.warning(f"笔记 {idx} 缺少标题或描述，跳过")
                            continue
                        
                        stats = process_note(title, description, city, images, 
                                           generate_comments=not args.no_comments)
                        
                        total_stats['total_notes'] += 1
                        total_stats['total_restaurants'] += stats['total_restaurants']
                        total_stats['total_success'] += stats['success']
                        total_stats['total_failed'] += stats['failed']
                        total_stats['total_comments'] += stats['comments_generated']
                        total_stats['all_errors'].extend(stats['errors'])
                
                elif args.title:
                    # 处理单条笔记
                    if not args.description:
                        args.description = args.title
                        logger.info("未提供描述，使用标题作为描述")
                    
                    images = args.images or []
                    
                    stats = process_note(args.title, args.description, args.city, images,
                                       generate_comments=not args.no_comments)
                    
                    total_stats['total_notes'] = 1
                    total_stats['total_restaurants'] = stats['total_restaurants']
                    total_stats['total_success'] = stats['success']
                    total_stats['total_failed'] = stats['failed']
                    total_stats['total_comments'] = stats['comments_generated']
                    total_stats['all_errors'] = stats['errors']
                
                else:
                    parser_process.print_help()
                    return
                
                # 打印最终统计
                logger.info("\n处理完成！统计信息：")
                logger.info(f"处理笔记数: {total_stats['total_notes']}")
                logger.info(f"提取餐厅数: {total_stats['total_restaurants']}")
                logger.info(f"成功插入: {total_stats['total_success']}")
                logger.info(f"失败数量: {total_stats['total_failed']}")
                logger.info(f"生成评论数: {total_stats['total_comments']}")
                
                if total_stats['all_errors']:
                    logger.warning(f"\n错误列表（共 {len(total_stats['all_errors'])} 个）:")
                    for error in total_stats['all_errors'][:10]:
                        logger.warning(f"  - {error}")
                    if len(total_stats['all_errors']) > 10:
                        logger.warning(f"  ... 还有 {len(total_stats['all_errors']) - 10} 个错误未显示")
                
            finally:
                try:
                    memory_monitor.stop_monitoring()
                except:
                    pass
            
        elif args.action == 'comments':
            generate_comments(
                tweet_id=args.tweet_id,
                count=args.count,
                limit=args.limit
            )
            
        elif args.action == 'images':
            search_images(
                method=args.method,
                city=args.city,
                limit=args.limit,
                tweet_id=args.tweet_id,
                force=args.force,
                since_time=args.since_time
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

