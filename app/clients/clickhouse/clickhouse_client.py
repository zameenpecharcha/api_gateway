import os
import threading
from typing import Optional

import clickhouse_connect
from clickhouse_connect.driver.client import Client
from dotenv import load_dotenv

load_dotenv()

_client_lock = threading.Lock()
_clickhouse_client: Optional[Client] = None


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name, default)
    if value is None:
        return None
    return value.strip().strip('"').strip("'")


def get_clickhouse_client() -> Client:
    global _clickhouse_client
    with _client_lock:
        if _clickhouse_client is not None:
            return _clickhouse_client

        host = _env("CLICKHOUSE_HOST")
        if not host:
            raise RuntimeError(
                "CLICKHOUSE_HOST is not configured. Set ClickHouse connection env vars on the API gateway."
            )

        port = int(_env("CLICKHOUSE_PORT", "8443") or "8443")
        username = _env("CLICKHOUSE_USERNAME", "default") or "default"
        password = _env("CLICKHOUSE_PASSWORD", "") or ""
        database = _env("CLICKHOUSE_DATABASE", "default") or "default"
        secure = (_env("CLICKHOUSE_SECURE", "true") or "true").lower() in ("1", "true", "yes")

        _clickhouse_client = clickhouse_connect.get_client(
            host=host,
            port=port,
            username=username,
            password=password,
            database=database,
            secure=secure,
        )
        return _clickhouse_client
