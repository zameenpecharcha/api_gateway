import time
import uuid
from typing import Optional, Iterable

from app.clients.grpc_base_client import GRPCBaseClient
from app.proto_files.chat import chat_pb2, chat_pb2_grpc


class ChatServiceClient(GRPCBaseClient):
    def __init__(self, target: str = 'localhost:50060'):
        super().__init__(chat_pb2_grpc.ChatServiceStub, target=target)

    def chat(self, outgoing: Iterable[chat_pb2.ClientMessage], token: Optional[str] = None):
        metadata = self._get_metadata(token, require_token=False)
        return self.stub.Chat(outgoing, metadata=metadata)

    @staticmethod
    def make_message(room_id: str, user_id: str, text: str = "") -> chat_pb2.ClientMessage:
        return chat_pb2.ClientMessage(
            room_id=room_id,
            user_id=user_id,
            message_id=str(uuid.uuid4()),
            text=text,
            sent_at_unix_ms=int(time.time() * 1000),
        )


chat_service_client = ChatServiceClient()


