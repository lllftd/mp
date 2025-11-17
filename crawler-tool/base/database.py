"""数据库操作封装"""
import logging

import pandas as pd
import pymysql
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from base.config import Config

logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        try:
            self.engine = create_engine(
                f"mysql+pymysql://{Config.DB_USER}:{Config.DB_PASSWORD}@{Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}?charset=utf8mb4",
                pool_pre_ping=True,
                pool_recycle=Config.DB_POOL_RECYCLE,
                pool_size=Config.DB_POOL_SIZE,
                max_overflow=Config.DB_MAX_OVERFLOW,
                echo=False
            )
            self.Session = sessionmaker(bind=self.engine)
            logger.info("数据库连接池初始化成功")
        except Exception as exc:
            logger.error("数据库连接初始化失败: %s", exc)
            raise

    def get_connection(self):
        return self.engine.connect()

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

    def execute_update(self, query, params=None):
        with self.engine.connect() as conn:
            result = conn.execute(text(query), params or {})
            conn.commit()
            return result.rowcount


db = Database()
