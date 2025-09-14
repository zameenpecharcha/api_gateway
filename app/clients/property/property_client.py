from app.proto_files.posts import property_pb2_grpc, property_pb2
from app.clients.grpc_base_client import GRPCBaseClient


class PropertyServiceClient(GRPCBaseClient):
    def __init__(self):
        super().__init__(property_pb2_grpc.PropertyServiceStub, target='localhost:50054')


property_service_client = PropertyServiceClient()