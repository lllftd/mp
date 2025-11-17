"""
app模块 - 爬虫工具应用层

目录结构：
- services/   核心服务层（AI服务、地址服务、推文处理）
- scripts/    可执行脚本（爬虫、数据处理、数据维护）
- utils/      工具函数库（图片处理、内容处理、评论生成）
- tools/      管理工具（推文类型管理）

使用示例：
    from app.services import get_ai_paraphraser, AddressService
    from app.services import prepare_tweet_data, insert_tweet
    from app.utils import process_note, generate_comments_for_tweet
    from app.utils import update_restaurant_images, BingImageSearcher
"""

__all__ = [
    'services',
    'scripts',
    'utils',
    'tools',
]
