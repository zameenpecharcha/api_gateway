import typing
import strawberry
import grpc
from typing import NewType
from strawberry.types import Info

from app.clients.chat.chat_client import chat_service_client
from app.utils.log_utils import log_msg


def _normalize_room_id(room_id: str) -> str:
    if not room_id:
        return room_id
    if room_id.startswith("dm-"):
        parts = room_id.split("-")
        if len(parts) >= 3 and parts[1] and parts[2]:
            user_a = parts[1]
            user_b = "-".join(parts[2:])
            if user_a and user_b:
                ordered = sorted([user_a, user_b])
                return f"dm:{ordered[0]}:{ordered[1]}"
    if room_id.startswith("dm:"):
        parts = room_id.split(":")
        if len(parts) >= 3 and parts[1] and parts[2]:
            ordered = sorted([parts[1], parts[2]])
            return f"dm:{ordered[0]}:{ordered[1]}"
    return room_id


# GraphQL Int is 32-bit; chat timestamps are Unix ms and exceed that range.
BigInt = strawberry.scalar(
    NewType("BigInt", int),
    serialize=lambda v: int(v),
    parse_value=lambda v: int(v),
)


def _authorization_from_info(info: Info) -> typing.Optional[str]:
    try:
        request = info.context.get("request") if info and info.context else None
        if not request:
            return None
        auth_header = request.headers.get("authorization")
        if auth_header:
            return auth_header

        # Fallback for deployments that keep access token in cookies.
        cookie_token = (
            request.cookies.get("token")
            or request.cookies.get("access_token")
            or request.cookies.get("auth_token")
        )
        if cookie_token:
            return cookie_token if cookie_token.lower().startswith("bearer ") else f"Bearer {cookie_token}"

        return None
    except Exception:
        return None


def _alternate_dm_room_id(room_id: str) -> typing.Optional[str]:
    if room_id.startswith("dm-"):
        parts = room_id.split("-")
        if len(parts) == 3 and parts[1] and parts[2]:
            return f"dm:{parts[1]}:{parts[2]}"
    if room_id.startswith("dm:"):
        parts = room_id.split(":")
        if len(parts) == 3 and parts[1] and parts[2]:
            return f"dm-{parts[1]}-{parts[2]}"
    return None


# ── Response types ─────────────────────────────────────────────────────────────

@strawberry.type
class ChatRoomResponse:
    room_id: str
    name: str


@strawberry.type
class ChatUploadResponse:
    media_key: str
    upload_url: str
    expires_at_unix_ms: BigInt


@strawberry.type
class ChatDownloadUrlResponse:
    url: str
    expires_at_unix_ms: BigInt


@strawberry.type
class ChatMessage:
    """A single persisted chat message returned by getMessages."""
    room_id: str
    user_id: str
    message_id: str
    text: str
    sent_at: BigInt         # Unix ms
    delivered_at: BigInt    # Unix ms
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
    last_seen_unix_ms: BigInt


@strawberry.type
class RoomParticipant:
    user_id: str
    first_name: str
    last_name: str
    avatar_url: str


@strawberry.type
class UserRoom:
    room_id: str
    room_type: int           # 0=DM 1=GROUP
    name: str
    last_message: str
    last_message_at: BigInt  # Unix ms
    has_unread: bool
    member_ids: typing.List[str]

    @strawberry.field
    def participants(self, info: Info) -> typing.List[RoomParticipant]:
        """Resolve participant profile details (name + avatar) from user_service."""
        from app.clients.user.user_client import user_service_client
        token = _authorization_from_info(info)
        result: typing.List[RoomParticipant] = []
        for uid in self.member_ids:
            try:
                # Use a short timeout so a slow user_service doesn't stall room loading
                u = user_service_client.get_user(uid, token=token)
                result.append(RoomParticipant(
                    user_id=str(u.id),
                    first_name=u.first_name,
                    last_name=u.last_name,
                    avatar_url=getattr(u, "profile_photo_signed_url", "") or "",
                ))
            except Exception:
                result.append(RoomParticipant(
                    user_id=uid,
                    first_name="",
                    last_name="",
                    avatar_url="",
                ))
        return result


# ── Query ──────────────────────────────────────────────────────────────────────

@strawberry.type
class Query:

    @strawberry.field
    def chat_download_url(
        self,
        info: Info,
        user_id: str,
        media_key: str,
    ) -> ChatDownloadUrlResponse:
        """Return a short-lived presigned GET URL to download a chat media file."""
        try:
            log_msg("info", f"GetDownloadUrl user={user_id} key={media_key}")
            token = _authorization_from_info(info)
            resp = chat_service_client.get_download_url(user_id, media_key, token=token)
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
        info: Info,
        room_id: str,
        user_id: str,
        limit: typing.Optional[int] = 50,
        before_unix_ms: typing.Optional[BigInt] = 0,
    ) -> GetMessagesResponse:
        """
        Load paginated message history for a room (newest first).
        Pass before_unix_ms for cursor-based pagination to load older messages.
        """
        try:
            limit_value = 50 if limit is None else limit
            before_value = 0 if before_unix_ms is None else before_unix_ms
            log_msg("info", f"GetMessages room={room_id} user={user_id} limit={limit_value}")
            token = _authorization_from_info(info)
            resp = chat_service_client.get_messages(
                room_id,
                user_id,
                limit_value,
                before_value,
                token=token,
            )

            # Backward compatibility for DM room ID format drift (dm-a-b vs dm:a:b).
            if not resp.messages:
                alternate = _alternate_dm_room_id(room_id)
                if alternate and alternate != room_id:
                    log_msg("info", f"GetMessages fallback room={alternate} user={user_id} limit={limit_value}")
                    alt_resp = chat_service_client.get_messages(
                        alternate,
                        user_id,
                        limit_value,
                        before_value,
                        token=token,
                    )
                    if alt_resp.messages:
                        resp = alt_resp

            if not resp.messages and room_id.startswith("dm-"):
                normalized = _normalize_room_id(room_id)
                if normalized != room_id:
                    normalized_resp = chat_service_client.get_messages(
                        normalized,
                        user_id,
                        limit_value,
                        before_value,
                        token=token,
                    )
                    if normalized_resp.messages:
                        resp = normalized_resp
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
        info: Info,
        user_ids: typing.List[str],
    ) -> typing.List[PresenceInfo]:
        """Batch presence lookup — returns online status and last-seen time."""
        try:
            token = _authorization_from_info(info)
            resp = chat_service_client.get_presence(user_ids, token=token)
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

    @strawberry.field
    def get_user_rooms(
        self,
        info: Info,
        user_id: str,
    ) -> typing.List[UserRoom]:
        """Return all active rooms for a user with last-message metadata and participant profiles."""
        try:
            log_msg("info", f"GetUserRooms user={user_id}")
            token = _authorization_from_info(info)
            resp = chat_service_client.get_user_rooms(user_id, token=token)
            return [
                UserRoom(
                    room_id=r.room_id,
                    room_type=int(r.room_type),
                    name=r.name,
                    last_message=r.last_message,
                    last_message_at=r.last_message_at,
                    has_unread=r.has_unread,
                    member_ids=list(r.member_ids),
                )
                for r in resp.rooms
            ]
        except grpc.RpcError as e:
            log_msg("error", f"GetUserRooms error: {str(e)}")
            return []

# ── Mutation ───────────────────────────────────────────────────────────────────

@strawberry.type
class Mutation:

    @strawberry.mutation
    def create_dm_room(
        self,
        info: Info,
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
            token = _authorization_from_info(info)
            log_msg("info", f"CreateDMRoom by={created_by} members={user_a},{user_b}")
            resp = chat_service_client.create_dm_room(user_a, user_b, created_by, token=token)
            return ChatRoomResponse(room_id=resp.room_id, name=resp.name)
        except grpc.RpcError as e:
            log_msg("error", f"CreateDMRoom error: {str(e)}")
            raise

    @strawberry.mutation
    def create_group_room(
        self,
        info: Info,
        created_by: str,
        name: str,
        member_ids: typing.List[str],
    ) -> ChatRoomResponse:
        """Create a new group chat room. Requires at least 2 member_ids."""
        try:
            token = _authorization_from_info(info)
            log_msg("info", f"CreateGroupRoom name={name} by={created_by}")
            resp = chat_service_client.create_group_room(name, created_by, member_ids, token=token)
            return ChatRoomResponse(room_id=resp.room_id, name=resp.name)
        except grpc.RpcError as e:
            log_msg("error", f"CreateGroupRoom error: {str(e)}")
            raise

    @strawberry.mutation
    def request_chat_upload(
        self,
        info: Info,
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
            token = _authorization_from_info(info)
            log_msg("info", f"RequestUpload user={user_id} room={room_id} file={file_name}")
            resp = chat_service_client.request_upload(
                user_id, room_id, file_name, mime_type, file_size_bytes, token=token
            )
            return ChatUploadResponse(
                media_key=resp.media_key,
                upload_url=resp.upload_url,
                expires_at_unix_ms=resp.expires_at_unix_ms,
            )
        except grpc.RpcError as e:
            log_msg("error", f"RequestUpload error: {str(e)}")
            raise

