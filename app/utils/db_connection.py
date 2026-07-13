from sqlalchemy import create_engine, MetaData
from dotenv import load_dotenv
import os

load_dotenv()

_engine = None


def get_db_engine():
    global _engine
    if _engine is not None:
        return _engine

    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME")

    if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_NAME]):
        raise RuntimeError("Missing required env vars: DB_USER, DB_PASSWORD, DB_HOST, DB_NAME")

    DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    ssl_mode = os.getenv("DB_SSLMODE", "")
    connect_args = {"sslmode": ssl_mode} if ssl_mode else {}

    _engine = create_engine(
        DATABASE_URL,
        connect_args=connect_args,
        echo=os.getenv("DB_ECHO", "false").lower() == "true",
        pool_pre_ping=True,   # detects dropped/SSL-closed connections before reuse
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        pool_recycle=1800,    # recycle connections older than 30 min
    )
    print("PostgreSQL engine created successfully!")
    return _engine

