import grpc
import os
import time
from dotenv import load_dotenv
from app.utils.log_utils import log_msg

load_dotenv()

# Retry config — handles Render free-tier cold starts (502 / UNAVAILABLE)
_MAX_RETRIES = 3
_RETRY_DELAY_S = 2.0   # seconds between retries


def _make_channel(target: str):
    """Return a secure channel for *.onrender.com or :443 targets, insecure otherwise."""
    if target.endswith(":443") or ".onrender.com" in target:
        creds = grpc.ssl_channel_credentials()
        # Render TLS — strip port if already present, enforce 443
        host = target.split(":")[0]
        return grpc.secure_channel(f"{host}:443", creds)
    return grpc.insecure_channel(target)


class GRPCBaseClient:
    def __init__(self, stub_class, target: str = "localhost:50051"):
        self.channel = _make_channel(target)
        self.stub = stub_class(self.channel)

    def _get_metadata(self, token=None, require_token=True):
        if require_token:
            return [("authorization", f"Bearer {token}")] if token else []
        return []

    def _call(self, grpc_method, request, token=None, require_token=True):
        metadata = self._get_metadata(token, require_token)
        last_error = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                return grpc_method(request, metadata=metadata)
            except grpc.RpcError as e:
                last_error = e
                # Retry on UNAVAILABLE (cold start 502) and DEADLINE_EXCEEDED
                if e.code() in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED):
                    if attempt < _MAX_RETRIES:
                        log_msg("warn", f"gRPC {e.code()} on attempt {attempt}/{_MAX_RETRIES}, retrying in {_RETRY_DELAY_S}s — {e.details()}")
                        time.sleep(_RETRY_DELAY_S)
                        continue
                # Non-retryable error — raise immediately
                log_msg("error", f"gRPC error: {str(e)}")
                raise e
        log_msg("error", f"gRPC call failed after {_MAX_RETRIES} attempts: {str(last_error)}")
        raise last_error
