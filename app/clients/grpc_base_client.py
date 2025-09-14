import grpc
from app.utils.log_utils import log_msg


class GRPCBaseClient:
    def __init__(self, stub_class, target='localhost:50051'):
        self.channel = grpc.insecure_channel(target)
        self.stub = stub_class(self.channel)

    def _get_metadata(self, token=None, require_token=True):
        if require_token:
            return [("authorization", f"Bearer {token}")] if token else []
        return []

    def _call(self, grpc_method, request, token=None, require_token=True):
        try:
            metadata = self._get_metadata(token, require_token)
            return grpc_method(request, metadata=metadata)
        except grpc.RpcError as e:
            log_msg("error", f"gRPC error: {str(e)}")
            raise e
