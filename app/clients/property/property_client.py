import os
from dotenv import load_dotenv
from app.proto_files.posts import property_pb2_grpc, property_pb2
from app.clients.grpc_base_client import GRPCBaseClient

load_dotenv()


class PropertyServiceClient(GRPCBaseClient):
    def __init__(self):
        target = os.getenv("PROPERTY_SERVICE_URL", "localhost:50054")
        super().__init__(property_pb2_grpc.PropertyServiceStub, target=target)


property_service_client = PropertyServiceClient()
