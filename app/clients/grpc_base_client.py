import grpc
from app.utils.log_utils import log_msg


class GRPCBaseClient:
    def __init__(self, stub_class, target='localhost:50051'):
        self.channel = grpc.insecure_channel(target)
        self.stub = stub_class(self.channel)

    def _get_metadata(self, token=None, require_token=True):
        if not require_token or not token:
            return []

        token = token.strip()
        log_msg("info", f"Preparing gRPC metadata with token: {repr(token[:30]) if token else 'None'}")
        if token.lower().startswith("bearer "):
            token = token[7:].strip()

        return [("authorization", f"Bearer {token}")]

    def _call(self, method_name, request, token=None, require_token=True):
        try:
            metadata = self._get_metadata(token, require_token)
            grpc_method = getattr(self.stub, method_name)
            return grpc_method(request, metadata=metadata)
        except grpc.RpcError as e:
            log_msg("error", f"gRPC error: {str(e)}")
            raise e