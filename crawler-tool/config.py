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

    # 数据库连接池配置
    DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', 5))
    DB_MAX_OVERFLOW = int(os.getenv('DB_MAX_OVERFLOW', 10))
    DB_POOL_RECYCLE = int(os.getenv('DB_POOL_RECYCLE', 3600))

    # 爬虫配置
    CRAWLER_DELAY = float(os.getenv('CRAWLER_DELAY', 1.0))  # 请求间隔（秒）
    CRAWLER_TIMEOUT = int(os.getenv('CRAWLER_TIMEOUT', 30))  # 请求超时（秒）
    DOWNLOAD_DIR = os.getenv('DOWNLOAD_DIR', './downloads')  # 图片下载目录
    SAVE_DIR = os.getenv('SAVE_DIR', './saved_data')  # 数据保存目录（文本和JSON）
    DEFAULT_TYPE_PID = int(os.getenv('DEFAULT_TYPE_PID', 5))  # 默认父类型ID
    DEFAULT_TYPE_CID = os.getenv('DEFAULT_TYPE_CID', '10,42')  # 默认子类型ID

    # AI转述配置（使用Ollama）
    LLM_API_BASE = os.getenv('LLM_API_BASE', 'http://localhost:11434/v1')
    # 默认模型选择（可根据硬件配置选择）：
    # - deepseek-r1:32b (最高质量，需要32GB+ RAM，约18GB)
    # - qwen2.5:32b (中文优化，高质量，需要32GB+ RAM，约20GB)
    # - deepseek-r1:14b (平衡选择，需要16GB+ RAM，约8GB) - 当前默认
    # - qwen2.5:14b (中文优化，平衡选择，需要16GB+ RAM，约9GB)
    # - llama3.1:70b (最强大，需要64GB+ RAM，约40GB)
    LLM_MODEL = os.getenv('LLM_MODEL', 'deepseek-r1:14b')  # 默认模型，可通过环境变量覆盖
    LLM_MAX_TOKENS = int(os.getenv('LLM_MAX_TOKENS', 500))
    LLM_TEMPERATURE = float(os.getenv('LLM_TEMPERATURE', 0.7))  # 创造性参数（0-1）
    
    # 图片处理配置
    REMOVE_WATERMARK = os.getenv('REMOVE_WATERMARK', 'true').lower() == 'true'  # 是否去除水印

