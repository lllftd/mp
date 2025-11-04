"""
推荐引擎（协同过滤 + 内容过滤 + 混合推荐）
"""
import json
import logging
from typing import List, Optional, Dict, Set
from collections import defaultdict
import math

import pandas as pd
import numpy as np
import redis

from config import Config
from database import db

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)


class CollaborativeFilteringRecommender:
    """协同过滤推荐算法（基于用户行为相似度）"""

    def __init__(self):
        self.similarity_threshold = Config.SIMILARITY_THRESHOLD

    def load_user_item_matrix(self) -> pd.DataFrame:
        """加载用户-物品矩阵"""
        query = """
            SELECT 
                tr.client_user_id as user_id,
                tr.tweets_id as item_id,
                CASE 
                    WHEN tr.type = 'like' THEN 5
                    WHEN tr.type = 'collect' THEN 4
                    WHEN tr.type = 'browse' THEN 1
                    ELSE 0
                END as rating
            FROM tweets_records tr
            WHERE tr.type IN ('like', 'collect', 'browse')
        """
        df = db.execute_query(query)
        if df.empty:
            return pd.DataFrame()
        
        # 创建用户-物品矩阵
        matrix = df.groupby(['user_id', 'item_id'])['rating'].sum().reset_index()
        user_item_matrix = matrix.pivot(index='user_id', columns='item_id', values='rating').fillna(0)
        return user_item_matrix

    def cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """计算余弦相似度"""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)

    def find_similar_users(self, user_id: int, user_item_matrix: pd.DataFrame, top_k: int = 20) -> List[int]:
        """找到相似用户"""
        if user_id not in user_item_matrix.index:
            return []
        
        user_vector = user_item_matrix.loc[user_id].values
        similarities = []
        
        for other_user_id in user_item_matrix.index:
            if other_user_id == user_id:
                continue
            other_vector = user_item_matrix.loc[other_user_id].values
            similarity = self.cosine_similarity(user_vector, other_vector)
            if similarity > self.similarity_threshold:
                similarities.append((other_user_id, similarity))
        
        # 按相似度排序，返回top_k个用户
        similarities.sort(key=lambda x: x[1], reverse=True)
        return [uid for uid, _ in similarities[:top_k]]

    def get_recommendations(self, user_id: int, top_n: int = 20) -> List[int]:
        """基于协同过滤生成推荐"""
        try:
            user_item_matrix = self.load_user_item_matrix()
            if user_item_matrix.empty or user_id not in user_item_matrix.index:
                return []
            
            # 找到相似用户
            similar_users = self.find_similar_users(user_id, user_item_matrix)
            if not similar_users:
                return []
            
            # 获取当前用户已交互的物品
            user_items = set(user_item_matrix.columns[user_item_matrix.loc[user_id] > 0])
            
            # 计算推荐分数
            item_scores = defaultdict(float)
            user_vector = user_item_matrix.loc[user_id].values
            
            for similar_user_id in similar_users:
                similarity = self.cosine_similarity(
                    user_vector,
                    user_item_matrix.loc[similar_user_id].values
                )
                similar_user_items = user_item_matrix.loc[similar_user_id]
                
                # 推荐相似用户喜欢但当前用户未交互的物品
                for item_id in similar_user_items.index:
                    if item_id not in user_items and similar_user_items[item_id] > 0:
                        item_scores[item_id] += similarity * similar_user_items[item_id]
            
            # 按分数排序，返回top_n
            recommended_items = sorted(item_scores.items(), key=lambda x: x[1], reverse=True)
            return [item_id for item_id, _ in recommended_items[:top_n]]
            
        except Exception as e:
            logger.error("协同过滤推荐失败: %s", str(e), exc_info=True)
            return []


class ContentBasedRecommender:
    """内容过滤推荐算法（基于用户标签和推文类型）"""

    def __init__(self):
        pass

    def load_user_tags(self, user_id: int) -> Set[str]:
        """加载用户标签"""
        query = """
            SELECT tags FROM client_user WHERE id = :user_id
        """
        result = db.execute_query(query, {'user_id': user_id})
        if result.empty or result.iloc[0]['tags'] is None:
            return set()
        tags_str = result.iloc[0]['tags']
        if isinstance(tags_str, str):
            return set(tag.strip() for tag in tags_str.split(',') if tag.strip())
        return set()

    def load_user_preferred_types(self, user_id: int) -> Dict[str, float]:
        """加载用户偏好的推文类型（基于历史行为）"""
        query = """
            SELECT 
                t.tweets_type_cid,
                COUNT(*) as count,
                SUM(CASE WHEN tr.type = 'like' THEN 5 WHEN tr.type = 'collect' THEN 4 ELSE 1 END) as score
            FROM tweets_records tr
            LEFT JOIN tweets t ON tr.tweets_id = t.id
            WHERE tr.client_user_id = :user_id
            GROUP BY t.tweets_type_cid
        """
        result = db.execute_query(query, {'user_id': user_id})
        if result.empty:
            return {}
        
        type_scores = {}
        total_score = result['score'].sum()
        if total_score > 0:
            for _, row in result.iterrows():
                type_id = str(row['tweets_type_cid'])
                type_scores[type_id] = row['score'] / total_score
        return type_scores

    def load_candidate_tweets(self, limit: int = 200) -> pd.DataFrame:
        """加载候选推文"""
        query = """
            SELECT 
                id,
                tweets_title,
                tweets_describe,
                tweets_type_cid,
                like_num,
                collect_num,
                browse_num
            FROM tweets
            WHERE status IS NULL OR status != '0'
            ORDER BY (like_num * 3 + collect_num * 2 + browse_num * 1) DESC
            LIMIT :limit
        """
        return db.execute_query(query, {'limit': limit})

    def get_recommendations(self, user_id: int, top_n: int = 20) -> List[int]:
        """基于内容过滤生成推荐"""
        try:
            # 加载用户偏好
            user_tags = self.load_user_tags(user_id)
            type_preferences = self.load_user_preferred_types(user_id)
            
            # 加载用户已交互的推文
            query = """
                SELECT DISTINCT tweets_id FROM tweets_records 
                WHERE client_user_id = :user_id
            """
            interacted_items = set(db.execute_query(query, {'user_id': user_id})['tweets_id'].tolist())
            
            # 加载候选推文
            candidates = self.load_candidate_tweets(limit=min(200, top_n * 10))
            if candidates.empty:
                return []
            
            # 计算推荐分数
            item_scores = []
            for _, tweet in candidates.iterrows():
                item_id = tweet['id']
                if item_id in interacted_items:
                    continue
                
                score = 0.0
                
                # 类型匹配分数
                type_cid = str(tweet['tweets_type_cid']) if pd.notna(tweet['tweets_type_cid']) else ''
                if type_cid in type_preferences:
                    score += type_preferences[type_cid] * 0.6
                
                # 热度分数（归一化）
                popularity = (tweet['like_num'] * 3 + tweet['collect_num'] * 2 + tweet['browse_num'] * 1)
                score += math.log1p(popularity) * 0.4
                
                item_scores.append((item_id, score))
            
            # 按分数排序，返回top_n
            item_scores.sort(key=lambda x: x[1], reverse=True)
            return [item_id for item_id, _ in item_scores[:top_n]]
            
        except Exception as e:
            logger.error("内容过滤推荐失败: %s", str(e), exc_info=True)
            return []


class ReinforcementLearningRecommender:
    """强化学习推荐器（基于用户反馈优化推荐）"""

    def __init__(self):
        self.learning_rate = Config.RL_LEARNING_RATE
        self.exploration_rate = Config.RL_EXPLORATION_RATE
        self.enabled = Config.RL_ENABLED

    def load_user_feedback(self, user_id: int) -> Dict:
        """加载用户反馈数据"""
        query = """
            SELECT 
                rf.tweets_id,
                rf.feedback,
                rf.reward,
                t.tweets_type_cid,
                DATE_FORMAT(rf.create_time, '%Y-%m-%d') as date
            FROM recommendation_feedback rf
            LEFT JOIN tweets t ON rf.tweets_id = t.id
            WHERE rf.client_user_id = :user_id
            ORDER BY rf.create_time DESC
            LIMIT 100
        """
        result = db.execute_query(query, {'user_id': user_id})
        if result.empty:
            return {
                'liked_items': set(),
                'disliked_items': set(),
                'liked_types': defaultdict(float),
                'disliked_types': defaultdict(float),
                'type_weights': {}
            }
        
        liked_items = set()
        disliked_items = set()
        liked_types = defaultdict(float)
        disliked_types = defaultdict(float)
        type_weights = defaultdict(float)
        
        for _, row in result.iterrows():
            item_id = row['tweets_id']
            feedback = row['feedback']
            reward = row['reward'] if pd.notna(row['reward']) else (1 if feedback == 'like' else -1)
            type_cid = str(row['tweets_type_cid']) if pd.notna(row['tweets_type_cid']) else ''
            
            if feedback == 'like':
                liked_items.add(item_id)
                if type_cid:
                    liked_types[type_cid] += reward
                    type_weights[type_cid] += reward * self.learning_rate
            elif feedback == 'dislike':
                disliked_items.add(item_id)
                if type_cid:
                    disliked_types[type_cid] += abs(reward)
                    type_weights[type_cid] -= abs(reward) * self.learning_rate
        
        return {
            'liked_items': liked_items,
            'disliked_items': disliked_items,
            'liked_types': dict(liked_types),
            'disliked_types': dict(disliked_types),
            'type_weights': dict(type_weights)
        }

    def apply_rl_filtering(self, recommendations: List[int], user_id: int) -> List[int]:
        """应用强化学习过滤和调整"""
        feedback_data = self.load_user_feedback(user_id)
        
        # 过滤掉用户明确不喜欢的推文
        filtered_recs = [item_id for item_id in recommendations 
                        if item_id not in feedback_data['disliked_items']]
        
        # 如果过滤后结果太少，使用原始推荐
        if len(filtered_recs) < len(recommendations) * 0.5:
            filtered_recs = recommendations
        
        return filtered_recs

    def apply_rl_scoring(self, recommendations: List[int], user_id: int) -> List[int]:
        """应用强化学习评分调整"""
        feedback_data = self.load_user_feedback(user_id)
        type_weights = feedback_data['type_weights']
        
        if not type_weights or not recommendations:
            return recommendations
        
        # 加载推文类型信息（使用数据库连接池）
        if len(recommendations) == 0:
            return recommendations
        
        # 使用参数化查询构建IN子句（安全方式）
        placeholders = ','.join([':id' + str(i) for i in range(len(recommendations))])
        params = {f'id{i}': item_id for i, item_id in enumerate(recommendations)}
        query = f"""
            SELECT id, tweets_type_cid 
            FROM tweets 
            WHERE id IN ({placeholders})
        """
        
        # 使用封装的数据库查询方法
        tweet_types = db.execute_query(query, params)
        
        if tweet_types.empty:
            return recommendations
        
        # 计算调整后的分数
        item_scores = []
        for item_id in recommendations:
            score = 1.0  # 基础分数
            
            # 查找推文类型
            tweet_type = tweet_types[tweet_types['id'] == item_id]
            if not tweet_type.empty:
                type_cid = str(tweet_type.iloc[0]['tweets_type_cid']) if pd.notna(tweet_type.iloc[0]['tweets_type_cid']) else ''
                
                # 应用强化学习权重
                if type_cid in type_weights:
                    score += type_weights[type_cid]
                
                # 用户喜欢的类型加分
                if type_cid in feedback_data['liked_types']:
                    score += feedback_data['liked_types'][type_cid] * 0.5
                
                # 用户不喜欢的类型减分
                if type_cid in feedback_data['disliked_types']:
                    score -= feedback_data['disliked_types'][type_cid] * 0.3
            
            item_scores.append((item_id, score))
        
        # 按调整后的分数重新排序
        item_scores.sort(key=lambda x: x[1], reverse=True)
        return [item_id for item_id, _ in item_scores]


class Recommender:
    """对外提供推荐的引擎（协同过滤 + 内容过滤 + 混合推荐 + 强化学习）"""

    def __init__(self):
        try:
            self.redis_client = redis.Redis(
                host=Config.REDIS_HOST,
                port=Config.REDIS_PORT,
                password=Config.REDIS_PASSWORD,
                db=Config.REDIS_DB,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            self.redis_client.ping()
        except Exception as e:
            logger.error("Redis连接失败: %s", str(e))
            self.redis_client = None

        self.cf_recommender = CollaborativeFilteringRecommender()
        self.cb_recommender = ContentBasedRecommender()
        self.rl_recommender = ReinforcementLearningRecommender()

    def load_tweets_data(self):
        query = """
            SELECT 
                id as item_id,
                like_num,
                collect_num,
                browse_num,
                create_time
            FROM tweets
            WHERE status IS NULL OR status != '0'
        """
        return db.execute_query(query)

    def get_recommendations(self, user_id: int, method: str = 'hybrid', top_n: Optional[int] = None) -> List[int]:
        """获取推荐"""
        top_n = top_n or Config.RECOMMENDATION_COUNT
        cache_key = f"recommendations:{user_id}:{method}:{top_n}"

        if self.redis_client:
            try:
                cached = self.redis_client.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception as e:
                logger.error("读取推荐缓存失败: %s", str(e))

        try:
            recommendations = []
            
            if method == 'collaborative' or method == 'cf':
                recommendations = self.cf_recommender.get_recommendations(user_id, top_n)
            elif method == 'content' or method == 'cb':
                recommendations = self.cb_recommender.get_recommendations(user_id, top_n)
            elif method == 'hybrid':
                # 混合推荐：结合协同过滤和内容过滤
                cf_recs = self.cf_recommender.get_recommendations(user_id, top_n)
                cb_recs = self.cb_recommender.get_recommendations(user_id, top_n)
                
                # 合并结果，优先协同过滤，补充内容过滤
                recommendations = list(cf_recs)
                for item_id in cb_recs:
                    if item_id not in recommendations:
                        recommendations.append(item_id)
                    if len(recommendations) >= top_n:
                        break
            else:
                # 默认使用混合推荐
                recommendations = self.get_recommendations(user_id, 'hybrid', top_n)

            # 如果没有推荐结果，返回热门物品
            if not recommendations:
                recommendations = self.get_popular_items(top_n)
            
            # 应用强化学习优化（基于用户反馈）
            if recommendations and self.rl_recommender.enabled:
                try:
                    # 1. 过滤掉用户明确不喜欢的推文
                    recommendations = self.rl_recommender.apply_rl_filtering(recommendations, user_id)
                    
                    # 2. 根据用户反馈调整推荐排序
                    recommendations = self.rl_recommender.apply_rl_scoring(recommendations, user_id)
                    
                    # 确保返回top_n个结果
                    recommendations = recommendations[:top_n]
                except Exception as e:
                    logger.error("强化学习优化失败: %s", str(e), exc_info=True)
                    # 如果强化学习失败，继续使用原始推荐

            if recommendations and self.redis_client:
                try:
                    self.redis_client.setex(cache_key, Config.CACHE_EXPIRE_TIME, json.dumps(recommendations))
                except Exception as e:
                    logger.error("写入推荐缓存失败: %s", str(e))

            return recommendations

        except Exception as e:
            logger.error("推荐执行错误: %s", str(e), exc_info=True)
            return self.get_popular_items(top_n)

    def get_popular_items(self, top_n: int = 20) -> List[int]:
        """获取热门物品"""
        cache_key = f"popular_items:{top_n}"
        if self.redis_client:
            try:
                cached = self.redis_client.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception as e:
                logger.error("读取热门缓存失败: %s", str(e))

        tweets_df = self.load_tweets_data()
        if tweets_df.empty:
            return []

        tweets_df['popularity_score'] = (
            (tweets_df['like_num'].fillna(0) * 3) +
            (tweets_df['collect_num'].fillna(0) * 2) +
            (tweets_df['browse_num'].fillna(0) * 1)
        ) / (pd.Timestamp.now() - pd.to_datetime(tweets_df['create_time'])).dt.total_seconds() / 86400 + 1

        popular = tweets_df.nlargest(top_n, 'popularity_score')['item_id'].tolist()

        if self.redis_client:
            try:
                self.redis_client.setex(cache_key, 1800, json.dumps(popular))
            except Exception as e:
                logger.error("写入热门缓存失败: %s", str(e))

        return popular
