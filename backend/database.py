import os
import mysql.connector
from mysql.connector import pooling
from dotenv import load_dotenv

load_dotenv()

_db_pool = None


def get_db_config():
    """Retrieve database connection parameters from environment variables."""
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": os.getenv("DB_NAME", "f1_strategy_db"),
    }


def init_db_pool(pool_name="f1_strategy_pool", pool_size=10):
    """Initialize the MySQL connection pool."""
    global _db_pool
    if _db_pool is None:
        config = get_db_config()
        _db_pool = pooling.MySQLConnectionPool(
            pool_name=pool_name,
            pool_size=pool_size,
            pool_reset_session=True,
            **config
        )
    return _db_pool


def get_db_connection():
    """Acquire a MySQL connection from the pool, falling back to direct connection if needed."""
    global _db_pool
    if _db_pool is None:
        try:
            init_db_pool()
        except Exception:
            pass

    if _db_pool is not None:
        try:
            return _db_pool.get_connection()
        except Exception:
            pass

    # Fallback to direct connection if pool fails or is exhausted
    return mysql.connector.connect(**get_db_config())