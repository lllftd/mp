"""
base模块 - 爬虫工具基础层

提供基础功能：
- config: 配置管理
- database: 数据库操作
- utils: 基础工具函数
- location_utils: 位置相关工具
- monitors: 监控工具
- browser_cleanup: 浏览器清理工具

使用示例：
    from base.config import Config
    from base.database import db
    from base.utils import get_random_username
    from base.location_utils import find_county_code
"""

from base.config import Config
from base.database import db
from base.utils import get_random_username
from base.location_utils import find_county_code, extract_district_from_address
from base.monitors import MemoryMonitor

__all__ = [
    'Config',
    'db',
    'get_random_username',
    'find_county_code',
    'extract_district_from_address',
    'MemoryMonitor',
]

