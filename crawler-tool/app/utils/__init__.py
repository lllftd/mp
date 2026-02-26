"""
工具函数库
提供图片处理、内容处理、评论生成、图片搜索等工具函数
"""

from app.utils.image_utils import (
    update_restaurant_images,
    build_tweets_query,
    process_restaurant_batch,
    prepare_image_json
)
from app.utils.process_content import process_note
from app.utils.search_images import BingImageSearcher, AmapImageSearcher, process_restaurants

# 可选导入：如果 generate_comments 模块存在则导入
try:
    from app.utils.generate_comments import generate_comments_for_tweet, insert_comments
    _has_generate_comments = True
except ImportError:
    _has_generate_comments = False
    generate_comments_for_tweet = None
    insert_comments = None

__all__ = [
    'update_restaurant_images',
    'build_tweets_query',
    'process_restaurant_batch',
    'prepare_image_json',
    'process_note',
    'BingImageSearcher',
    'AmapImageSearcher',
    'process_restaurants',
]

# 如果 generate_comments 模块存在，添加到 __all__
if _has_generate_comments:
    __all__.extend(['generate_comments_for_tweet', 'insert_comments'])

