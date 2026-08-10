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
        return self._call("CreateRoom", request, token=token, require_token=True)

    def create_group_room(self, name: str, created_by: str, member_ids: list,
                          token: Optional[str] = None):
        request = chat_pb2.CreateRoomRequest(
            created_by=created_by,
            name=name,
            type=chat_pb2.ROOM_TYPE_GROUP,
            member_ids=member_ids,
        )
        return self._call("CreateRoom", request, token=token, require_token=True)

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
        return self._call("GetMessages", request, token=token, require_token=True)

    # ── Presence ──────────────────────────────────────────────────────────────

    def get_presence(self, user_ids: list, token: Optional[str] = None):
        request = chat_pb2.GetPresenceRequest(user_ids=user_ids)
        return self._call("GetPresence", request, token=token, require_token=True)

    def get_user_rooms(self, user_id: str, token: Optional[str] = None):
        request = chat_pb2.GetUserRoomsRequest(user_id=user_id)
        return self._call("GetUserRooms", request, token=token, require_token=True)

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
        return self._call("RequestUpload", request, token=token, require_token=True)

    def get_download_url(self, user_id: str, media_key: str,
                         token: Optional[str] = None):
        request = chat_pb2.GetDownloadUrlRequest(user_id=user_id, media_key=media_key)
        return self._call("GetDownloadUrl", request, token=token, require_token=True)

    # ── Extended 18 APIs Client Methods ────────────────────────────────────────

    def get_conversation(self, conversation_id: str, user_id: str = "", token: Optional[str] = None):
        request = chat_pb2.GetConversationRequest(conversation_id=conversation_id, user_id=user_id)
        return self._call("GetConversation", request, token=token, require_token=True)

    def send_message(self, conversation_id: str, sender_id: str, content: str = "",
                     message_type: int = 0, media_key: str = "", media_name: str = "",
                     media_size_bytes: int = 0, media_mime_type: str = "",
                     reply_to_message_id: str = "", token: Optional[str] = None):
        request = chat_pb2.SendMessageRequest(
            conversation_id=conversation_id,
            sender_id=sender_id,
            content=content,
            message_type=message_type,
            media_key=media_key,
            media_name=media_name,
            media_size_bytes=media_size_bytes,
            media_mime_type=media_mime_type,
            reply_to_message_id=reply_to_message_id,
        )
        return self._call("SendMessage", request, token=token, require_token=True)

    def search_messages(self, conversation_id: str, query: str, limit: int = 50, token: Optional[str] = None):
        request = chat_pb2.SearchMessagesRequest(
            conversation_id=conversation_id,
            query=query,
            limit=limit,
        )
        return self._call("SearchMessages", request, token=token, require_token=True)

    def delete_message(self, message_id: str, user_id: str, conversation_id: str = "", token: Optional[str] = None):
        request = chat_pb2.DeleteMessageRequest(
            message_id=message_id,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        return self._call("DeleteMessage", request, token=token, require_token=True)

    def edit_message(self, message_id: str, user_id: str, new_content: str, conversation_id: str = "", token: Optional[str] = None):
        request = chat_pb2.EditMessageRequest(
            message_id=message_id,
            user_id=user_id,
            conversation_id=conversation_id,
            new_content=new_content,
        )
        return self._call("EditMessage", request, token=token, require_token=True)

    def mark_message_read(self, conversation_id: str, user_id: str, message_id: str = "", token: Optional[str] = None):
        request = chat_pb2.MarkMessageReadRequest(
            conversation_id=conversation_id,
            user_id=user_id,
            message_id=message_id,
        )
        return self._call("MarkMessageRead", request, token=token, require_token=True)

    def get_unread_count(self, user_id: str, conversation_id: str = "", token: Optional[str] = None):
        request = chat_pb2.GetUnreadCountRequest(
            user_id=user_id,
            conversation_id=conversation_id,
        )
        return self._call("GetUnreadCount", request, token=token, require_token=True)

    def create_group(self, group_name: str, created_by: str, member_ids: list,
                     group_photo: str = "", description: str = "", token: Optional[str] = None):
        request = chat_pb2.CreateGroupRequest(
            created_by=created_by,
            group_name=group_name,
            group_photo=group_photo,
            description=description,
            member_ids=member_ids,
        )
        return self._call("CreateGroup", request, token=token, require_token=True)

    def add_group_member(self, conversation_id: str, user_id: str, operator_id: str = "", role: str = "MEMBER", token: Optional[str] = None):
        request = chat_pb2.AddGroupMemberRequest(
            conversation_id=conversation_id,
            user_id=user_id,
            operator_id=operator_id,
            role=role,
        )
        return self._call("AddGroupMember", request, token=token, require_token=True)

    def remove_group_member(self, conversation_id: str, user_id: str, operator_id: str = "", token: Optional[str] = None):
        request = chat_pb2.RemoveGroupMemberRequest(
            conversation_id=conversation_id,
            user_id=user_id,
            operator_id=operator_id,
        )
        return self._call("RemoveGroupMember", request, token=token, require_token=True)

    def leave_group(self, conversation_id: str, user_id: str, token: Optional[str] = None):
        request = chat_pb2.LeaveGroupRequest(
            conversation_id=conversation_id,
            user_id=user_id,
        )
        return self._call("LeaveGroup", request, token=token, require_token=True)

    def promote_admin(self, conversation_id: str, user_id: str, operator_id: str = "", token: Optional[str] = None):
        request = chat_pb2.PromoteAdminRequest(
            conversation_id=conversation_id,
            user_id=user_id,
            operator_id=operator_id,
        )
        return self._call("PromoteAdmin", request, token=token, require_token=True)

    def transfer_ownership(self, conversation_id: str, current_owner_id: str, new_owner_id: str, token: Optional[str] = None):
        request = chat_pb2.TransferOwnershipRequest(
            conversation_id=conversation_id,
            current_owner_id=current_owner_id,
            new_owner_id=new_owner_id,
        )
        return self._call("TransferOwnership", request, token=token, require_token=True)

    def delete_group(self, conversation_id: str, owner_id: str, token: Optional[str] = None):
        request = chat_pb2.DeleteGroupRequest(
            conversation_id=conversation_id,
            owner_id=owner_id,
        )
        return self._call("DeleteGroup", request, token=token, require_token=True)

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




