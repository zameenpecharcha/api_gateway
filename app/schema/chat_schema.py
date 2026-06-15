import typing
import strawberry
import grpc
from strawberry.types import Info

from app.clients.chat.chat_client import chat_service_client
from app.utils.log_utils import log_msg


# ── Response types ─────────────────────────────────────────────────────────────

@strawberry.type
class ChatRoomResponse:
    room_id: str
    name: str


@strawberry.type
class ChatUploadResponse:
    media_key: str
    upload_url: str
    expires_at_unix_ms: int


@strawberry.type
class ChatDownloadUrlResponse:
    url: str
    expires_at_unix_ms: int


@strawberry.type
class ChatMessage:
    """A single persisted chat message returned by getMessages."""
    room_id: str
    user_id: str
    message_id: str
    text: str
    sent_at: int            # Unix ms
    delivered_at: int       # Unix ms
    type: int               # 0=TEXT 1=IMAGE 2=VIDEO 3=AUDIO 4=FILE
    media_key: str
    media_name: str
    media_size_bytes: int
    media_mime_type: str
    media_url: str
    reply_to_message_id: str
    is_deleted: bool
    event_type: int
    status: int             # 0=SENDING 1=SENT 2=DELIVERED 3=READ


@strawberry.type
class GetMessagesResponse:
    messages: typing.List[ChatMessage]
    has_more: bool


@strawberry.type
class PresenceInfo:
    user_id: str
    is_online: bool
    last_seen_unix_ms: int


# ── Query ──────────────────────────────────────────────────────────────────────

@strawberry.type
class Query:

    @strawberry.field
    def chat_download_url(
        self,
        user_id: str,
        media_key: str,
    ) -> ChatDownloadUrlResponse:
        """Return a short-lived presigned GET URL to download a chat media file."""
        try:
            log_msg("info", f"GetDownloadUrl user={user_id} key={media_key}")
            resp = chat_service_client.get_download_url(user_id, media_key)
            return ChatDownloadUrlResponse(
                url=resp.url,
                expires_at_unix_ms=resp.expires_at_unix_ms,
            )
        except grpc.RpcError as e:
            log_msg("error", f"GetDownloadUrl error: {str(e)}")
            raise

    @strawberry.field
    def get_messages(
        self,
        room_id: str,
        user_id: str,
        limit: typing.Optional[int] = 50,
        before_unix_ms: typing.Optional[int] = 0,
    ) -> GetMessagesResponse:
        """
        Load paginated message history for a room (newest first).
        Pass before_unix_ms for cursor-based pagination to load older messages.
        """
        try:
            log_msg("info", f"GetMessages room={room_id} user={user_id} limit={limit}")
            resp = chat_service_client.get_messages(room_id, user_id, limit, before_unix_ms or 0)
            messages = [
                ChatMessage(
                    room_id=m.room_id,
                    user_id=m.user_id,
                    message_id=m.message_id,
                    text=m.text,
                    sent_at=m.sent_at_unix_ms,
                    delivered_at=m.delivered_at_unix_ms,
                    type=m.type,
                    media_key=m.media_key,
                    media_name=m.media_name,
                    media_size_bytes=m.media_size_bytes,
                    media_mime_type=m.media_mime_type,
                    media_url=m.media_url,
                    reply_to_message_id=m.reply_to_message_id,
                    is_deleted=m.is_deleted,
                    event_type=m.event_type,
                    status=m.status,
                )
                for m in resp.messages
            ]
            return GetMessagesResponse(messages=messages, has_more=resp.has_more)
        except grpc.RpcError as e:
            log_msg("error", f"GetMessages error: {str(e)}")
            raise

    @strawberry.field
    def get_presence(
        self,
        user_ids: typing.List[str],
    ) -> typing.List[PresenceInfo]:
        """Batch presence lookup — returns online status and last-seen time."""
        try:
            resp = chat_service_client.get_presence(user_ids)
            return [
                PresenceInfo(
                    user_id=u.user_id,
                    is_online=u.is_online,
                    last_seen_unix_ms=u.last_seen_unix_ms,
                )
                for u in resp.users
            ]
        except grpc.RpcError as e:
            log_msg("error", f"GetPresence error: {str(e)}")
            raise


# ── Mutation ───────────────────────────────────────────────────────────────────

@strawberry.type
class Mutation:

    @strawberry.mutation
    def create_dm_room(
        self,
        created_by: str,
        user_a: str,
        user_b: str,
    ) -> ChatRoomResponse:
        """
        Create (or return the existing) DM room between two users.
        The room_id is deterministic — calling this twice for the same pair
        returns the same room.
        """
        try:
            log_msg("info", f"CreateDMRoom by={created_by} members={user_a},{user_b}")
            resp = chat_service_client.create_dm_room(user_a, user_b, created_by)
            return ChatRoomResponse(room_id=resp.room_id, name=resp.name)
        except grpc.RpcError as e:
            log_msg("error", f"CreateDMRoom error: {str(e)}")
            raise

    @strawberry.mutation
    def create_group_room(
        self,
        created_by: str,
        name: str,
        member_ids: typing.List[str],
    ) -> ChatRoomResponse:
        """Create a new group chat room. Requires at least 2 member_ids."""
        try:
            log_msg("info", f"CreateGroupRoom name={name} by={created_by}")
            resp = chat_service_client.create_group_room(name, created_by, member_ids)
            return ChatRoomResponse(room_id=resp.room_id, name=resp.name)
        except grpc.RpcError as e:
            log_msg("error", f"CreateGroupRoom error: {str(e)}")
            raise

    @strawberry.mutation
    def request_chat_upload(
        self,
        user_id: str,
        room_id: str,
        file_name: str,
        mime_type: str,
        file_size_bytes: int,
    ) -> ChatUploadResponse:
        """
        Get a presigned HTTP PUT URL to upload a file directly to object storage.
        Pass the returned media_key in the WebSocket message to share the file.
        """
        try:
            log_msg("info", f"RequestUpload user={user_id} room={room_id} file={file_name}")
            resp = chat_service_client.request_upload(
                user_id, room_id, file_name, mime_type, file_size_bytes
            )
            return ChatUploadResponse(
                media_key=resp.media_key,
                upload_url=resp.upload_url,
                expires_at_unix_ms=resp.expires_at_unix_ms,
            )
        except grpc.RpcError as e:
            log_msg("error", f"RequestUpload error: {str(e)}")
            raise



# ── Response types ─────────────────────────────────────────────────────────────

@strawberry.type
class ChatRoomResponse:
    room_id: str
    name: str


@strawberry.type
class ChatUploadResponse:
    media_key: str
    upload_url: str
    expires_at_unix_ms: int


@strawberry.type
class ChatDownloadUrlResponse:
    url: str
    expires_at_unix_ms: int


# ── Query ──────────────────────────────────────────────────────────────────────

@strawberry.type
class Query:

    @strawberry.field
    def chat_download_url(
        self,
        user_id: str,
        media_key: str,
    ) -> ChatDownloadUrlResponse:
        """Return a short-lived presigned GET URL to download a chat media file."""
        try:
            log_msg("info", f"GetDownloadUrl user={user_id} key={media_key}")
            resp = chat_service_client.get_download_url(user_id, media_key)
            return ChatDownloadUrlResponse(
                url=resp.url,
                expires_at_unix_ms=resp.expires_at_unix_ms,
            )
        except grpc.RpcError as e:
            log_msg("error", f"GetDownloadUrl error: {str(e)}")
            raise


# ── Mutation ───────────────────────────────────────────────────────────────────

@strawberry.type
class Mutation:

    @strawberry.mutation
    def create_dm_room(
        self,
        created_by: str,
        user_a: str,
        user_b: str,
    ) -> ChatRoomResponse:
        """
        Create (or return the existing) DM room between two users.
        The room_id is deterministic — calling this twice for the same pair
        returns the same room.
        """
        try:
            log_msg("info", f"CreateDMRoom by={created_by} members={user_a},{user_b}")
            resp = chat_service_client.create_dm_room(user_a, user_b, created_by)
            return ChatRoomResponse(room_id=resp.room_id, name=resp.name)
        except grpc.RpcError as e:
            log_msg("error", f"CreateDMRoom error: {str(e)}")
            raise

    @strawberry.mutation
    def create_group_room(
        self,
        created_by: str,
        name: str,
        member_ids: typing.List[str],
    ) -> ChatRoomResponse:
        """Create a new group chat room. Requires at least 2 member_ids."""
        try:
            log_msg("info", f"CreateGroupRoom name={name} by={created_by}")
            resp = chat_service_client.create_group_room(name, created_by, member_ids)
            return ChatRoomResponse(room_id=resp.room_id, name=resp.name)
        except grpc.RpcError as e:
            log_msg("error", f"CreateGroupRoom error: {str(e)}")
            raise

    @strawberry.mutation
    def request_chat_upload(
        self,
        user_id: str,
        room_id: str,
        file_name: str,
        mime_type: str,
        file_size_bytes: int,
    ) -> ChatUploadResponse:
        """
        Get a presigned HTTP PUT URL to upload a file directly to object storage.
        Pass the returned media_key in the WebSocket message to share the file.
        """
        try:
            log_msg("info", f"RequestUpload user={user_id} room={room_id} file={file_name}")
            resp = chat_service_client.request_upload(
                user_id, room_id, file_name, mime_type, file_size_bytes
            )
            return ChatUploadResponse(
                media_key=resp.media_key,
                upload_url=resp.upload_url,
                expires_at_unix_ms=resp.expires_at_unix_ms,
            )
        except grpc.RpcError as e:
            log_msg("error", f"RequestUpload error: {str(e)}")
            raise
