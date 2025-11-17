#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成评论脚本
为每个帖子生成35-75条随机评论，使用小红书风格用户名
"""
import json
import logging
import os
import sys
import random
import argparse
from typing import List, Dict

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from base.config import Config
from base.database import db
from app.services.ai_service import get_ai_paraphraser
from base.utils import get_random_username

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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
            # 尝试提取JSON部分
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
                # 如果解析失败，尝试查找JSON对象
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
            
            # 生成随机用户名
            username = get_random_username()
            
            comments.append({
                'tweets_id': tweet_id,
                'evaluate_user': username,
                'evaluate_content': content.strip(),
                'evaluate_time': None  # 数据库会自动设置时间
            })
        
        logger.info(f"成功生成 {len(comments)} 条评论")
        return comments
        
    except Exception as e:
        logger.error(f"生成评论失败: {str(e)}", exc_info=True)
        return []


def insert_comments(comments: List[Dict]) -> int:
    """
    批量插入评论到数据库
    
    Args:
        comments: 评论列表
        
    Returns:
        成功插入的数量
    """
    if not comments:
        return 0
    
    try:
        from sqlalchemy import text
        
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
                logger.error(f"评论数据: {comment}")
        
        return success_count
        
    except Exception as e:
        logger.error(f"批量插入评论失败: {str(e)}", exc_info=True)
        return 0


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='为推文生成评论')
    parser.add_argument('--tweet-id', type=int, help='指定推文ID（如果不指定，则为所有推文生成评论）')
    parser.add_argument('--count', type=int, help='每条推文的评论数量（默认：35-75随机）')
    parser.add_argument('--limit', type=int, default=100, help='处理推文数量限制（默认：100）')
    
    args = parser.parse_args()
    
    try:
        # 查询推文
        if args.tweet_id:
            query = "SELECT id, tweets_title, tweets_content FROM tweets WHERE id = :tweet_id"
            tweets = db.execute_query(query, {'tweet_id': args.tweet_id})
        else:
            query = f"SELECT id, tweets_title, tweets_content FROM tweets ORDER BY id DESC LIMIT :limit"
            tweets = db.execute_query(query, {'limit': args.limit})
        
        if tweets.empty:
            logger.warning("没有找到推文")
            return
        
        logger.info(f"找到 {len(tweets)} 条推文，开始生成评论...")
        
        total_comments = 0
        total_inserted = 0
        
        for idx, row in tweets.iterrows():
            tweet_id = row['id']
            tweet_title = row['tweets_title']
            tweet_content = row['tweets_content']
            
            logger.info(f"\n处理推文 {idx + 1}/{len(tweets)}: ID={tweet_id}, 标题={tweet_title}")
            
            # 生成评论
            comments = generate_comments_for_tweet(
                tweet_id=tweet_id,
                tweet_content=tweet_content,
                tweet_title=tweet_title,
                comment_count=args.count
            )
            
            if comments:
                total_comments += len(comments)
                # 插入评论
                inserted = insert_comments(comments)
                total_inserted += inserted
                logger.info(f"推文 {tweet_id}: 生成 {len(comments)} 条，插入 {inserted} 条")
            else:
                logger.warning(f"推文 {tweet_id}: 未能生成评论")
        
        logger.info(f"\n完成！总共生成 {total_comments} 条评论，成功插入 {total_inserted} 条")
        
    except Exception as e:
        logger.error(f"执行失败: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

