"""配置模块"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """应用配置"""

    # 数据库配置（默认值，可通过.env文件或环境变量覆盖）
    DB_HOST = os.getenv('DB_HOST', '47.121.133.201')
    DB_PORT = int(os.getenv('DB_PORT', 3306))
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'adminMysql')
    DB_NAME = os.getenv('DB_NAME', 'jxwq_end')

    # Redis配置
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')
    REDIS_DB = int(os.getenv('REDIS_DB', 0))

    # 推荐参数
    RECOMMENDATION_COUNT = int(os.getenv('RECOMMENDATION_COUNT', 20))
    CACHE_EXPIRE_TIME = int(os.getenv('CACHE_EXPIRE_TIME', 3600))

    DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', 5))
    DB_MAX_OVERFLOW = int(os.getenv('DB_MAX_OVERFLOW', 10))
    DB_POOL_RECYCLE = int(os.getenv('DB_POOL_RECYCLE', 3600))
    
    # 推荐算法参数
    SIMILARITY_THRESHOLD = float(os.getenv('SIMILARITY_THRESHOLD', 0.1))  # 协同过滤相似度阈值
    
    # 强化学习参数
    RL_LEARNING_RATE = float(os.getenv('RL_LEARNING_RATE', 0.1))  # 强化学习率
    RL_EXPLORATION_RATE = float(os.getenv('RL_EXPLORATION_RATE', 0.2))  # 探索率（尝试新类型）
    RL_ENABLED = os.getenv('RL_ENABLED', 'true').lower() == 'true'  # 是否启用强化学习
