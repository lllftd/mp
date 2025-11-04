"""数据库操作封装"""
import logging

import pandas as pd
import pymysql
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from config import Config

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
        with self.engine.connect() as conn:
            if params:
                if isinstance(params, dict):
                    try:
                        # 使用text()和参数绑定
                        result = conn.execute(text(query), params)
                        # 获取列名并转换为列表
                        if result.returns_rows:
                            columns = list(result.keys())
                            rows = []
                            for row in result:
                                # 确保row可以转换为字典
                                if hasattr(row, '_asdict'):
                                    rows.append(row._asdict())
                                elif hasattr(row, '_mapping'):
                                    rows.append(dict(row._mapping))
                                else:
                                    # 手动构建字典
                                    rows.append(dict(zip(columns, row)))
                            return pd.DataFrame(rows)
                        else:
                            return pd.DataFrame()
                    except Exception as e:
                        # 如果text()方式失败，尝试使用pandas方式
                        logger.warning(f"使用text()执行查询失败，尝试pandas方式: {e}")
                        return pd.read_sql(query, conn, params=params)
                return pd.read_sql(query, conn, params=params)
            return pd.read_sql(query, conn)

    def execute_update(self, query, params=None):
        with self.engine.connect() as conn:
            result = conn.execute(text(query), params or {})
            conn.commit()
            return result.rowcount


db = Database()

