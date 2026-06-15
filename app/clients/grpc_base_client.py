import grpc
import os
import time
from dotenv import load_dotenv
from app.utils.log_utils import log_msg

load_dotenv()

_MAX_RETRIES = 5
_RETRY_DELAY_S = 3.0


def _make_channel(target: str):
    if target.endswith(":443") or ".onrender.com" in target:
        creds = grpc.ssl_channel_credentials()
        host = target.split(":")[0]
        return grpc.secure_channel(f"{host}:443", creds)
    return grpc.insecure_channel(target)


class GRPCBaseClient:
    def __init__(self, stub_class, target: str = "localhost:50051"):
        self._target = target
        self._stub_class = stub_class
        self._make_stub()

    def _make_stub(self):
        self.channel = _make_channel(self._target)
        self.stub = self._stub_class(self.channel)

    def _get_metadata(self, token=None, require_token=True):
        if require_token:
            return [("authorization", f"Bearer {token}")] if token else []
        return []

    def _call(self, method_name: str, request, token=None, require_token=True):
        """
        Call a gRPC method by name. Recreates the channel on UNAVAILABLE so
        stale channels (from cold-start 502s) don't block future requests.
        """
        metadata = self._get_metadata(token, require_token)
        last_error = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                method = getattr(self.stub, method_name)
                return method(request, metadata=metadata)
            except grpc.RpcError as e:
                last_error = e
                if e.code() in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED):
                    if attempt < _MAX_RETRIES:
                        log_msg("warn", f"gRPC {e.code()} on attempt {attempt}/{_MAX_RETRIES}, "
                                        f"reconnecting in {_RETRY_DELAY_S}s — {e.details()}")
                        time.sleep(_RETRY_DELAY_S)
                        self._make_stub()   # fresh channel + stub
                        continue
                log_msg("error", f"gRPC error: {str(e)}")
                raise e
            except ValueError as e:
                # "Cannot invoke RPC on closed channel" — always reconnect
                last_error = e
                if attempt < _MAX_RETRIES:
                    log_msg("warn", f"Closed channel on attempt {attempt}/{_MAX_RETRIES}, reconnecting — {e}")
                    time.sleep(_RETRY_DELAY_S)
                    self._make_stub()
                    continue
                raise e
        log_msg("error", f"gRPC call failed after {_MAX_RETRIES} attempts: {str(last_error)}")
        raise last_error
