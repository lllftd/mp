"""数据库操作封装"""
import logging
import time
from functools import wraps

import pandas as pd
import pymysql
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, DisconnectionError
from sqlalchemy.orm import sessionmaker

from base.config import Config

logger = logging.getLogger(__name__)


def retry_db_operation(max_retries=3, initial_delay=1, backoff_factor=2):
    """
    数据库操作重试装饰器
    
    Args:
        max_retries: 最大重试次数
        initial_delay: 初始延迟（秒）
        backoff_factor: 退避因子（每次重试延迟时间 = initial_delay * backoff_factor^retry_count）
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            last_exception = None
            delay = initial_delay
            
            for attempt in range(max_retries):
                try:
                    return func(self, *args, **kwargs)
                except (OperationalError, DisconnectionError, pymysql.err.OperationalError) as e:
                    last_exception = e
                    
                    # 提取错误代码
                    error_code = None
                    error_msg = str(e).lower()
                    
                    # 尝试从 SQLAlchemy 异常中提取原始错误
                    if hasattr(e, 'orig'):
                        if hasattr(e.orig, 'args') and len(e.orig.args) > 0:
                            error_code = e.orig.args[0]
                    elif isinstance(e, pymysql.err.OperationalError):
                        if hasattr(e, 'args') and len(e.args) > 0:
                            error_code = e.args[0]
                    
                    # 判断是否为连接相关错误（需要重试）
                    is_connection_error = (
                        error_code in (2003, 2006, 2013, 2014) or  # MySQL连接错误代码
                        'timed out' in error_msg or
                        "can't connect" in error_msg or
                        'connection' in error_msg or
                        'lost connection' in error_msg
                    )
                    
                    if is_connection_error:
                        if attempt < max_retries - 1:
                            logger.warning(
                                f"数据库连接失败 (尝试 {attempt + 1}/{max_retries}): {e}. "
                                f"等待 {delay:.1f} 秒后重试..."
                            )
                            time.sleep(delay)
                            delay *= backoff_factor
                            
                            # 尝试重新创建连接池
                            try:
                                self._recreate_engine()
                            except Exception as recreate_error:
                                logger.warning(f"重新创建连接池失败: {recreate_error}")
                        else:
                            logger.error(f"数据库操作失败，已重试 {max_retries} 次: {e}")
                    else:
                        # 其他类型的错误，直接抛出
                        raise
                except Exception as e:
                    # 非连接相关的错误，直接抛出
                    raise
            
            # 所有重试都失败，抛出最后一个异常
            raise last_exception
        return wrapper
    return decorator


class Database:
    def __init__(self):
        self._create_engine()

    def _create_engine(self):
        """创建数据库引擎"""
        try:
            # 添加连接超时参数
            connect_args = {
                'connect_timeout': 10,  # 连接超时10秒
                'read_timeout': 30,     # 读取超时30秒
                'write_timeout': 30,    # 写入超时30秒
            }
            
            self.engine = create_engine(
                f"mysql+pymysql://{Config.DB_USER}:{Config.DB_PASSWORD}@{Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}?charset=utf8mb4",
                pool_pre_ping=True,
                pool_recycle=Config.DB_POOL_RECYCLE,
                pool_size=Config.DB_POOL_SIZE,
                max_overflow=Config.DB_MAX_OVERFLOW,
                connect_args=connect_args,
                echo=False
            )
            self.Session = sessionmaker(bind=self.engine)
            logger.info("数据库连接池初始化成功")
        except Exception as exc:
            logger.error("数据库连接初始化失败: %s", exc)
            raise

    def _recreate_engine(self):
        """重新创建数据库引擎（用于连接失败后重建）"""
        try:
            if hasattr(self, 'engine'):
                self.engine.dispose()
        except Exception:
            pass
        self._create_engine()

    def get_connection(self):
        return self.engine.connect()

    @retry_db_operation(max_retries=3, initial_delay=2, backoff_factor=2)
    def execute_query(self, query, params=None):
        """
        执行查询并返回DataFrame
        
        Args:
            query: SQL查询语句
            params: 查询参数（字典或元组）
            
        Returns:
            pandas.DataFrame: 查询结果
        """
        with self.engine.connect() as conn:
            try:
                # 使用text()和参数绑定（更安全）
                if params:
                    result = conn.execute(text(query), params)
                else:
                    result = conn.execute(text(query))
                
                # 如果有返回行，转换为DataFrame
                if result.returns_rows:
                    columns = list(result.keys())
                    rows = []
                    for row in result:
                        # 转换为字典
                        if hasattr(row, '_mapping'):
                            rows.append(dict(row._mapping))
                        elif hasattr(row, '_asdict'):
                            rows.append(row._asdict())
                        else:
                            rows.append(dict(zip(columns, row)))
                    return pd.DataFrame(rows)
                else:
                    return pd.DataFrame()
            except Exception as e:
                # 如果text()方式失败，回退到pandas方式
                logger.warning(f"使用text()执行查询失败，尝试pandas方式: {e}")
                return pd.read_sql(query, conn, params=params)

    @retry_db_operation(max_retries=3, initial_delay=2, backoff_factor=2)
    def execute_update(self, query, params=None):
        """执行更新操作（带重试机制）"""
        with self.engine.connect() as conn:
            result = conn.execute(text(query), params or {})
            conn.commit()
            return result.rowcount


db = Database()
