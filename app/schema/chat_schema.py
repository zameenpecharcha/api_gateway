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
class ConversationDetailGQL:
    conversation_id: str
    type: int
    participants: typing.List[str]
    group_name: str
    group_photo: str
    description: str
    member_count: int
    last_message: str
    last_message_id: str
    last_message_at: BigInt
    created_by: str
    created_at: BigInt


@strawberry.type
class GroupMemberGQL:
    id: str
    conversation_id: str
    user_id: str
    role: str
    joined_at: BigInt
    status: str


@strawberry.type
class GetConversationResponseGQL:
    conversation: typing.Optional[ConversationDetailGQL]
    members: typing.List[GroupMemberGQL]


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
    edited_at: BigInt = 0  # Unix ms; 0 = never edited
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


def _batch_room_participants(
    member_ids_by_room: typing.List[typing.List[str]],
    token: typing.Optional[str],
) -> typing.List[typing.List[RoomParticipant]]:
    """Resolve unique member profiles once, then map back per room."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from app.clients.user.user_client import user_service_client
    from app.utils.s3_utils import generate_presigned_get_url_from_url

    unique_ids = sorted({str(uid) for members in member_ids_by_room for uid in members if uid})
    profiles: typing.Dict[str, RoomParticipant] = {}

    def _one(uid: str) -> typing.Tuple[str, RoomParticipant]:
        try:
            u = user_service_client.get_user(uid, token=token)
            raw_photo = getattr(u, "profile_photo", None) or ""
            if (not raw_photo) and getattr(u, "profile_photo_id", 0):
                try:
                    media = user_service_client.get_media(
                        media_id=int(u.profile_photo_id), token=token
                    )
                    raw_photo = getattr(media, "media_url", None) or ""
                except Exception:
                    raw_photo = ""
            avatar = ""
            if raw_photo:
                try:
                    avatar = generate_presigned_get_url_from_url(raw_photo) or raw_photo
                except Exception:
                    avatar = raw_photo
            return uid, RoomParticipant(
                user_id=str(getattr(u, "id", uid)),
                first_name=getattr(u, "first_name", "") or "",
                last_name=getattr(u, "last_name", "") or "",
                avatar_url=avatar or "",
            )
        except Exception:
            return uid, RoomParticipant(
                user_id=uid,
                first_name="",
                last_name="",
                avatar_url="",
            )

    if unique_ids:
        workers = min(8, len(unique_ids))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_one, uid) for uid in unique_ids]
            for fut in as_completed(futures):
                uid, participant = fut.result()
                profiles[uid] = participant

    out: typing.List[typing.List[RoomParticipant]] = []
    for members in member_ids_by_room:
        out.append([
            profiles.get(str(uid)) or RoomParticipant(
                user_id=str(uid), first_name="", last_name="", avatar_url=""
            )
            for uid in members
        ])
    return out


@strawberry.type
class UserRoom:
    room_id: str
    room_type: int           # 0=DM 1=GROUP
    name: str
    last_message: str
    last_message_at: BigInt  # Unix ms
    has_unread: bool
    member_ids: typing.List[str]
    participants: typing.List[RoomParticipant] = strawberry.field(default_factory=list)


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
                    edited_at=getattr(m, "edited_at_unix_ms", 0) or 0,
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
    def get_conversation(
        self,
        info: Info,
        conversation_id: str,
        user_id: typing.Optional[str] = "",
    ) -> GetConversationResponseGQL:
        """Get single conversation details and members via gRPC."""
        try:
            token = _authorization_from_info(info)
            resp = chat_service_client.get_conversation(conversation_id, user_id=user_id or "", token=token)
            conv_detail = None
            if resp.HasField("conversation"):
                c = resp.conversation
                conv_detail = ConversationDetailGQL(
                    conversation_id=c.conversation_id,
                    type=int(c.type),
                    participants=list(c.participants),
                    group_name=c.group_name,
                    group_photo=c.group_photo,
                    description=c.description,
                    member_count=c.member_count,
                    last_message=c.last_message,
                    last_message_id=c.last_message_id,
                    last_message_at=c.last_message_at,
                    created_by=c.created_by,
                    created_at=c.created_at,
                )
            members = [
                GroupMemberGQL(
                    id=m.id,
                    conversation_id=m.conversation_id,
                    user_id=m.user_id,
                    role=m.role,
                    joined_at=m.joined_at,
                    status=m.status,
                )
                for m in resp.members
            ]
            return GetConversationResponseGQL(conversation=conv_detail, members=members)
        except grpc.RpcError as e:
            log_msg("error", f"GetConversation error: {str(e)}")
            raise

    @strawberry.field
    def search_messages(
        self,
        info: Info,
        conversation_id: str,
        query: str,
        limit: typing.Optional[int] = 50,
    ) -> typing.List[ChatMessage]:
        """Search messages within a conversation via gRPC."""
        try:
            token = _authorization_from_info(info)
            resp = chat_service_client.search_messages(conversation_id, query, limit=limit or 50, token=token)
            return [
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
                    edited_at=getattr(m, "edited_at_unix_ms", 0) or 0,
                    event_type=m.event_type,
                    status=m.status,
                )
                for m in resp.messages
            ]
        except grpc.RpcError as e:
            log_msg("error", f"SearchMessages error: {str(e)}")
            raise

    @strawberry.field
    def get_unread_count(
        self,
        info: Info,
        user_id: str,
        conversation_id: typing.Optional[str] = "",
    ) -> int:
        """Get unread message count for a user via gRPC."""
        try:
            token = _authorization_from_info(info)
            resp = chat_service_client.get_unread_count(user_id, conversation_id=conversation_id or "", token=token)
            return resp.total_unread_count
        except grpc.RpcError as e:
            log_msg("error", f"GetUnreadCount error: {str(e)}")
            return 0

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
            member_lists = [list(r.member_ids) for r in resp.rooms]
            participants_by_room = _batch_room_participants(member_lists, token)
            return [
                UserRoom(
                    room_id=r.room_id,
                    room_type=int(r.room_type),
                    name=r.name,
                    last_message=r.last_message,
                    last_message_at=r.last_message_at,
                    has_unread=r.has_unread,
                    member_ids=list(r.member_ids),
                    participants=participants_by_room[i] if i < len(participants_by_room) else [],
                )
                for i, r in enumerate(resp.rooms)
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
        Create (or return the existing) DM room between two users via gRPC.
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
        group_photo: typing.Optional[str] = "",
        description: typing.Optional[str] = "",
    ) -> ChatRoomResponse:
        """Create a new group chat room via gRPC."""
        try:
            token = _authorization_from_info(info)
            log_msg("info", f"CreateGroupRoom name={name} by={created_by}")
            if group_photo or description:
                resp = chat_service_client.create_group(name, created_by, member_ids, group_photo=group_photo or "", description=description or "", token=token)
                return ChatRoomResponse(room_id=resp.conversation.conversation_id, name=resp.conversation.group_name)
            resp = chat_service_client.create_group_room(name, created_by, member_ids, token=token)
            return ChatRoomResponse(room_id=resp.room_id, name=resp.name)
        except grpc.RpcError as e:
            log_msg("error", f"CreateGroupRoom error: {str(e)}")
            raise

    @strawberry.mutation
    def send_message(
        self,
        info: Info,
        conversation_id: str,
        sender_id: str,
        content: str = "",
        message_type: int = 0,
        media_key: str = "",
        media_name: str = "",
        media_size_bytes: int = 0,
        media_mime_type: str = "",
        reply_to_message_id: str = "",
    ) -> ChatMessage:
        """Send a message via gRPC Unary API."""
        try:
            token = _authorization_from_info(info)
            resp = chat_service_client.send_message(
                conversation_id=conversation_id,
                sender_id=sender_id,
                content=content,
                message_type=message_type,
                media_key=media_key,
                media_name=media_name,
                media_size_bytes=media_size_bytes,
                media_mime_type=media_mime_type,
                reply_to_message_id=reply_to_message_id,
                token=token,
            )
            m = resp.message
            return ChatMessage(
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
                edited_at=getattr(m, "edited_at_unix_ms", 0) or 0,
                event_type=m.event_type,
                status=m.status,
            )
        except grpc.RpcError as e:
            log_msg("error", f"SendMessage error: {str(e)}")
            raise

    @strawberry.mutation
    def delete_message(
        self,
        info: Info,
        message_id: str,
        user_id: str,
        conversation_id: typing.Optional[str] = "",
    ) -> bool:
        """Soft delete a message via gRPC."""
        try:
            token = _authorization_from_info(info)
            resp = chat_service_client.delete_message(message_id, user_id, conversation_id=conversation_id or "", token=token)
            return resp.success
        except grpc.RpcError as e:
            log_msg("error", f"DeleteMessage error: {str(e)}")
            raise

    @strawberry.mutation
    def edit_message(
        self,
        info: Info,
        message_id: str,
        user_id: str,
        new_content: str,
        conversation_id: typing.Optional[str] = "",
    ) -> ChatMessage:
        """Edit a message via gRPC."""
        try:
            token = _authorization_from_info(info)
            resp = chat_service_client.edit_message(message_id, user_id, new_content, conversation_id=conversation_id or "", token=token)
            m = resp.message
            return ChatMessage(
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
                edited_at=getattr(m, "edited_at_unix_ms", 0) or 0,
                event_type=m.event_type,
                status=m.status,
            )
        except grpc.RpcError as e:
            log_msg("error", f"EditMessage error: {str(e)}")
            raise

    @strawberry.mutation
    def mark_message_read(
        self,
        info: Info,
        conversation_id: str,
        user_id: str,
        message_id: typing.Optional[str] = "",
    ) -> bool:
        """Mark message as read via gRPC."""
        try:
            token = _authorization_from_info(info)
            resp = chat_service_client.mark_message_read(conversation_id, user_id, message_id=message_id or "", token=token)
            return resp.success
        except grpc.RpcError as e:
            log_msg("error", f"MarkMessageRead error: {str(e)}")
            raise

    @strawberry.mutation
    def add_group_member(
        self,
        info: Info,
        conversation_id: str,
        user_id: str,
        operator_id: typing.Optional[str] = "",
        role: typing.Optional[str] = "MEMBER",
    ) -> bool:
        """Add member to group via gRPC."""
        try:
            token = _authorization_from_info(info)
            resp = chat_service_client.add_group_member(conversation_id, user_id, operator_id=operator_id or "", role=role or "MEMBER", token=token)
            return resp.success
        except grpc.RpcError as e:
            log_msg("error", f"AddGroupMember error: {str(e)}")
            raise

    @strawberry.mutation
    def remove_group_member(
        self,
        info: Info,
        conversation_id: str,
        user_id: str,
        operator_id: typing.Optional[str] = "",
    ) -> bool:
        """Remove member from group via gRPC."""
        try:
            token = _authorization_from_info(info)
            resp = chat_service_client.remove_group_member(conversation_id, user_id, operator_id=operator_id or "", token=token)
            return resp.success
        except grpc.RpcError as e:
            log_msg("error", f"RemoveGroupMember error: {str(e)}")
            raise

    @strawberry.mutation
    def leave_group(
        self,
        info: Info,
        conversation_id: str,
        user_id: str,
    ) -> bool:
        """Leave group via gRPC."""
        try:
            token = _authorization_from_info(info)
            resp = chat_service_client.leave_group(conversation_id, user_id, token=token)
            return resp.success
        except grpc.RpcError as e:
            log_msg("error", f"LeaveGroup error: {str(e)}")
            raise

    @strawberry.mutation
    def promote_admin(
        self,
        info: Info,
        conversation_id: str,
        user_id: str,
        operator_id: typing.Optional[str] = "",
    ) -> bool:
        """Promote member to admin via gRPC."""
        try:
            token = _authorization_from_info(info)
            resp = chat_service_client.promote_admin(conversation_id, user_id, operator_id=operator_id or "", token=token)
            return resp.success
        except grpc.RpcError as e:
            log_msg("error", f"PromoteAdmin error: {str(e)}")
            raise

    @strawberry.mutation
    def transfer_ownership(
        self,
        info: Info,
        conversation_id: str,
        new_owner_id: str,
        current_owner_id: typing.Optional[str] = "",
    ) -> bool:
        """Transfer group ownership via gRPC."""
        try:
            token = _authorization_from_info(info)
            resp = chat_service_client.transfer_ownership(conversation_id, current_owner_id=current_owner_id or "", new_owner_id=new_owner_id, token=token)
            return resp.success
        except grpc.RpcError as e:
            log_msg("error", f"TransferOwnership error: {str(e)}")
            raise

    @strawberry.mutation
    def delete_group(
        self,
        info: Info,
        conversation_id: str,
        owner_id: str,
    ) -> bool:
        """Delete group via gRPC."""
        try:
            token = _authorization_from_info(info)
            resp = chat_service_client.delete_group(conversation_id, owner_id, token=token)
            return resp.success
        except grpc.RpcError as e:
            log_msg("error", f"DeleteGroup error: {str(e)}")
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
        Get a presigned HTTP PUT URL to upload a file directly to object storage via gRPC.
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


