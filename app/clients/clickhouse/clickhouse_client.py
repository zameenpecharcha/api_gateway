import os
import threading
from pathlib import Path
from typing import Optional

import clickhouse_connect
from clickhouse_connect.driver.client import Client
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=True)

_thread_local = threading.local()


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name, default)
    if value is None:
        return None
    return value.strip().strip('"').strip("'")


def create_clickhouse_client() -> Client:
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
    verify = (_env("CLICKHOUSE_VERIFY", "true") or "true").lower() in ("1", "true", "yes")

    return clickhouse_connect.get_client(
        host=host,
        port=port,
        username=username,
        password=password,
        database=database,
        secure=secure,
        verify=verify,
    )


def get_clickhouse_client() -> Client:
    client = getattr(_thread_local, "client", None)
    if client is not None:
        return client
    _thread_local.client = create_clickhouse_client()
    return _thread_local.client
