import os
import time
import uuid
from typing import Optional, Iterable
from dotenv import load_dotenv

from app.clients.grpc_base_client import GRPCBaseClient
from app.proto_files.chat import chat_pb2, chat_pb2_grpc

load_dotenv()


class ChatServiceClient(GRPCBaseClient):
    def __init__(self):
        target = os.getenv("CHAT_SERVICE_URL", "localhost:50051")
        super().__init__(chat_pb2_grpc.ChatServiceStub, target=target)

    # ── Bidi stream (used by the WebSocket bridge in chat_api.py) ─────────────

    def chat(self, outgoing: Iterable[chat_pb2.ClientMessage], token: Optional[str] = None):
        metadata = self._get_metadata(token, require_token=False)
        return self.stub.Chat(outgoing, metadata=metadata)

    # ── Room management ───────────────────────────────────────────────────────

    def create_dm_room(self, user_a: str, user_b: str, created_by: str,
                       token: Optional[str] = None):
        request = chat_pb2.CreateRoomRequest(
            created_by=created_by,
            type=chat_pb2.ROOM_TYPE_DM,
            member_ids=[user_a, user_b],
        )
        return self._call(self.stub.CreateRoom, request, token=token, require_token=False)

    def create_group_room(self, name: str, created_by: str, member_ids: list,
                          token: Optional[str] = None):
        request = chat_pb2.CreateRoomRequest(
            created_by=created_by,
            name=name,
            type=chat_pb2.ROOM_TYPE_GROUP,
            member_ids=member_ids,
        )
        return self._call(self.stub.CreateRoom, request, token=token, require_token=False)

    # ── Message history ───────────────────────────────────────────────────────

    def get_messages(self, room_id: str, user_id: str,
                     limit: int = 50, before_unix_ms: int = 0,
                     token: Optional[str] = None):
        request = chat_pb2.GetMessagesRequest(
            room_id=room_id,
            user_id=user_id,
            limit=limit,
            before_unix_ms=before_unix_ms,
        )
        return self._call(self.stub.GetMessages, request, token=token, require_token=False)

    # ── Presence ──────────────────────────────────────────────────────────────

    def get_presence(self, user_ids: list, token: Optional[str] = None):
        request = chat_pb2.GetPresenceRequest(user_ids=user_ids)
        return self._call(self.stub.GetPresence, request, token=token, require_token=False)

    # ── Media upload / download ───────────────────────────────────────────────

    def request_upload(self, user_id: str, room_id: str, file_name: str,
                       mime_type: str, file_size_bytes: int,
                       token: Optional[str] = None):
        request = chat_pb2.UploadRequest(
            user_id=user_id,
            room_id=room_id,
            file_name=file_name,
            mime_type=mime_type,
            file_size_bytes=file_size_bytes,
        )
        return self._call(self.stub.RequestUpload, request, token=token, require_token=False)

    def get_download_url(self, user_id: str, media_key: str,
                         token: Optional[str] = None):
        request = chat_pb2.GetDownloadUrlRequest(user_id=user_id, media_key=media_key)
        return self._call(self.stub.GetDownloadUrl, request, token=token, require_token=False)

    # ── Helper ────────────────────────────────────────────────────────────────

    @staticmethod
    def make_message(room_id: str, user_id: str, text: str = "",
                     message_type: int = 0, media_key: str = "",
                     media_name: str = "", media_size_bytes: int = 0,
                     media_mime_type: str = "") -> chat_pb2.ClientMessage:
        return chat_pb2.ClientMessage(
            room_id=room_id,
            user_id=user_id,
            message_id=str(uuid.uuid4()),
            text=text,
            sent_at_unix_ms=int(time.time() * 1000),
            type=message_type,
            media_key=media_key,
            media_name=media_name,
            media_size_bytes=media_size_bytes,
            media_mime_type=media_mime_type,
        )


chat_service_client = ChatServiceClient()


