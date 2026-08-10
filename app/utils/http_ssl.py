import os
from typing import Union


def http_ssl_verify() -> Union[bool, str]:
    """CA bundle for httpx; set HTTP_SSL_VERIFY=false on Windows/Docker if verify fails."""
    flag = os.getenv("HTTP_SSL_VERIFY", "true").strip().lower()
    if flag in ("0", "false", "no"):
        return False
    try:
        import certifi

        return certifi.where()
    except ImportError:
        return True
