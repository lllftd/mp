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
                    result = conn.execute(text(query), params)
                    rows = [dict(row) for row in result]
                    return pd.DataFrame(rows, columns=result.keys())
                return pd.read_sql(query, conn, params=params)
            return pd.read_sql(query, conn)

    def execute_update(self, query, params=None):
        with self.engine.connect() as conn:
            result = conn.execute(text(query), params or {})
            conn.commit()
            return result.rowcount


db = Database()

