import os
import time
import threading
import boto3
from typing import Optional, Tuple, Dict
from urllib.parse import urlparse, unquote


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name, default)
    if value is None:
        return None
    return value.strip().strip('"').strip("'")


_client_lock = threading.Lock()
_s3_clients: Dict[str, object] = {}
_presign_lock = threading.Lock()
# source_url -> (signed_url, expires_at_monotonic)
_presign_get_cache: Dict[str, Tuple[str, float]] = {}


def _s3_client(region: Optional[str] = None):
    region_name = _env("AWS_REGION") or _env("AWS_DEFAULT_REGION") or region or "us-east-1"
    with _client_lock:
        cached = _s3_clients.get(region_name)
        if cached is not None:
            return cached

        client_kwargs = {"region_name": region_name}
        aws_access_key_id = _env("AWS_ACCESS_KEY_ID")
        aws_secret_access_key = _env("AWS_SECRET_ACCESS_KEY")
        aws_session_token = _env("AWS_SESSION_TOKEN")

        if aws_access_key_id and aws_secret_access_key:
            client_kwargs.update({
                "aws_access_key_id": aws_access_key_id,
                "aws_secret_access_key": aws_secret_access_key,
            })
            if aws_session_token:
                client_kwargs["aws_session_token"] = aws_session_token

        client = boto3.client("s3", **client_kwargs)
        _s3_clients[region_name] = client
        return client


def build_post_object_key(file_name: str) -> str:
    return f"uploads/post/{file_name}"


def generate_presigned_put_url(file_name: str, content_type: Optional[str] = None, expires_in: int = 3600) -> Tuple[str, str, str]:
    bucket = _env("S3_BUCKET_NAME") or _env("AWS_S3_BUCKET") or "zpc-app"
    region = _env("AWS_REGION") or _env("AWS_DEFAULT_REGION") or "us-east-1"
    key = build_post_object_key(file_name)

    s3 = _s3_client(region)
    params = {"Bucket": bucket, "Key": key}
    if content_type:
        params["ContentType"] = content_type

    url = s3.generate_presigned_url(
        ClientMethod="put_object",
        Params=params,
        ExpiresIn=expires_in,
    )
    public_url = f"https://{bucket}.s3.{region}.amazonaws.com/{key}"
    return url, key, public_url


def generate_presigned_get_url_from_url(s3_url: str, expires_in: int = 3600) -> Optional[str]:
    """Presign S3 GET with client reuse + short TTL cache (hot path for feed)."""
    if not s3_url:
        return None

    now = time.monotonic()
    with _presign_lock:
        cached = _presign_get_cache.get(s3_url)
        if cached and cached[1] > now:
            return cached[0]

    try:
        parsed = urlparse(s3_url)
        if not parsed.netloc or not parsed.path:
            return None

        hostname_parts = parsed.netloc.split(".")
        bucket = hostname_parts[0]
        # zpc-app.s3.us-east-1.amazonaws.com OR zpc-app.s3.amazonaws.com
        region = "us-east-1"
        if len(hostname_parts) >= 5 and hostname_parts[1] == "s3":
            region = hostname_parts[2]
        elif _env("AWS_REGION"):
            region = _env("AWS_REGION") or region

        key = unquote(parsed.path.lstrip("/"))
        s3 = _s3_client(region)
        url = s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in,
        )

        # Refresh cache a bit before real expiry
        cache_ttl = max(60.0, float(expires_in) * 0.75)
        with _presign_lock:
            _presign_get_cache[s3_url] = (url, now + cache_ttl)
            # Prevent unbounded growth
            if len(_presign_get_cache) > 2000:
                stale = [k for k, (_, exp) in _presign_get_cache.items() if exp <= now]
                for k in stale[:500]:
                    _presign_get_cache.pop(k, None)

        return url
    except Exception:
        return None
