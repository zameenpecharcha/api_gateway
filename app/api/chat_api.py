import asyncio
import json
import time
import uuid
import grpc

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from grpc import aio as grpc_aio

from app.proto_files.chat import chat_pb2, chat_pb2_grpc

# Target matches ChatServiceClient default — override via CHAT_SERVICE_URL env var
import os
from dotenv import load_dotenv
load_dotenv()

_raw = os.getenv("CHAT_SERVICE_URL", "localhost:50051")
# For Render: use TLS on port 443
if ".onrender.com" in _raw or _raw.endswith(":443"):
    import grpc
    _host = _raw.split(":")[0]
    CHAT_SERVICE_TARGET = f"{_host}:443"
    CHAT_CHANNEL_SECURE = True
else:
    CHAT_SERVICE_TARGET = _raw
    CHAT_CHANNEL_SECURE = False

chat_router = APIRouter()

# EventType constants (must match chat.proto EventType enum values)
_EVENT_TYPE_MESSAGE       = 0
_EVENT_TYPE_TYPING_START  = 1
_EVENT_TYPE_TYPING_STOP   = 2
_EVENT_TYPE_READ_RECEIPT  = 3
_EVENT_TYPE_REACTION      = 4
_EVENT_TYPE_DELETE        = 5
_EVENT_TYPE_PRESENCE      = 6


def _ws_auth_header(websocket: WebSocket) -> str | None:
    # Browser WebSocket cannot set custom headers directly, so accept token via
    # query param/cookie and normalize to gRPC authorization metadata.
    auth = websocket.headers.get("authorization")
    if auth:
        return auth

    token = (
        websocket.query_params.get("token")
        or websocket.cookies.get("token")
        or websocket.cookies.get("access_token")
        or websocket.cookies.get("auth_token")
    )
    if token:
        return token if token.lower().startswith("bearer ") else f"Bearer {token}"

    return None


def _build_client_msg(room_id: str, user_id: str, data: dict) -> chat_pb2.ClientMessage:
    """Convert a browser JSON payload to a ClientMessage proto."""
    sent_at = data.get("sentAt")
    if sent_at is None:
        sent_at = int(time.time() * 1000)

    return chat_pb2.ClientMessage(
        room_id=room_id,
        user_id=user_id,
        message_id=data.get("messageId") or str(uuid.uuid4()),
        text=data.get("text", ""),
        sent_at_unix_ms=sent_at,
        type=data.get("type", 0),
        media_key=data.get("mediaKey", ""),
        media_name=data.get("mediaName", ""),
        media_size_bytes=data.get("mediaSizeBytes", 0),
        media_mime_type=data.get("mediaMimeType", ""),
        event_type=data.get("eventType", 0),
        reply_to_message_id=data.get("replyToMessageId", ""),
        reaction_emoji=data.get("reactionEmoji", ""),
    )


def _server_msg_to_dict(msg) -> dict:
    """Convert a ServerMessage proto to a JSON-serialisable dict."""
    return {
        "roomId":             msg.room_id,
        "userId":             msg.user_id,
        "messageId":          msg.message_id,
        "text":               msg.text,
        "sentAt":             msg.sent_at_unix_ms,
        "deliveredAt":        msg.delivered_at_unix_ms,
        "type":               msg.type,
        "mediaKey":           msg.media_key,
        "mediaName":          msg.media_name,
        "mediaSizeBytes":     msg.media_size_bytes,
        "mediaMimeType":      msg.media_mime_type,
        "mediaUrl":           msg.media_url,
        # new fields
        "replyToMessageId":   msg.reply_to_message_id,
        "reactionEmoji":      msg.reaction_emoji,
        "isDeleted":          getattr(msg, "is_deleted", False),
        "editedAt":           getattr(msg, "edited_at_unix_ms", 0),
        "eventType":          msg.event_type,
        "status":             int(getattr(msg, "status", 0) or 0),
        "isOnline":           getattr(msg, "is_online", False),
        "lastSeenAt":         getattr(msg, "last_seen_unix_ms", 0),
    }


@chat_router.websocket("/ws/chat/{room_id}/{user_id}")
async def chat_ws(websocket: WebSocket, room_id: str, user_id: str):
    """
    WebSocket bridge → gRPC bidirectional stream (ChatService.Chat).

    Connect:
        ws://<host>/api/v1/ws/chat/<room_id>/<user_id>

    Client → send JSON  (all fields optional unless noted):
        Text message:
            {"text": "hello"}
        Media message (after uploadChatFile mutation):
            {"type":1, "mediaKey":"rooms/...", "mediaName":"photo.jpg",
             "mediaSizeBytes":204800, "mediaMimeType":"image/jpeg"}
        Reply to a message:
            {"text": "agreed", "replyToMessageId": "<uuid>"}
        Typing indicator:
            {"eventType": 1}   (1=TYPING_START  2=TYPING_STOP)
        Read receipt:
            {"eventType": 3, "messageId": "<uuid>"}
        Emoji reaction:
            {"eventType": 4, "messageId": "<uuid>", "reactionEmoji": "👍"}
        Delete message:
            {"eventType": 5, "messageId": "<uuid>", "sentAt": <unix_ms>}

    Server → receive JSON with all fields including:
        eventType, replyToMessageId, reactionEmoji, isDeleted,
        status, isOnline, lastSeenAt
    """
    from app.utils.log_utils import log_msg
    log_msg("info", f"WebSocket connecting: room={room_id} user={user_id} target={CHAT_SERVICE_TARGET}")
    await websocket.accept()

    auth_header = _ws_auth_header(websocket)
    if not auth_header:
        log_msg("error", f"WebSocket rejected: missing auth token for user={user_id}")
        await websocket.send_json({"error": "missing authorization token"})
        await websocket.close(code=1008)
        return

    if CHAT_CHANNEL_SECURE:
        channel = grpc_aio.secure_channel(CHAT_SERVICE_TARGET, grpc.ssl_channel_credentials())
    else:
        channel = grpc_aio.insecure_channel(CHAT_SERVICE_TARGET)
    stub = chat_pb2_grpc.ChatServiceStub(channel)
    call = stub.Chat(metadata=[("authorization", auth_header)])

    # Register in the hub (first frame: room_id + user_id only, no content)
    try:
        await call.write(
            chat_pb2.ClientMessage(
                room_id=room_id,
                user_id=user_id,
                message_id=str(uuid.uuid4()),
                sent_at_unix_ms=int(time.time() * 1000),
            )
        )
    except Exception as e:
        log_msg("error", f"gRPC Chat connection failed to target={CHAT_SERVICE_TARGET} err={str(e)}")
        await websocket.send_json({"error": f"chat connection failed: {str(e)}"})
        await websocket.close(code=1008)
        await channel.close()
        return

    async def ws_to_grpc():
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    data = {"text": raw}

                await call.write(_build_client_msg(room_id, user_id, data))
        except WebSocketDisconnect:
            log_msg("info", f"ws_to_grpc: WebSocket disconnected for user={user_id}")
        except Exception as e:
            log_msg("error", f"ws_to_grpc task failed: {str(e)}")
        finally:
            log_msg("info", f"ws_to_grpc: done_writing for user={user_id}")
            await call.done_writing()

    async def grpc_to_ws():
        try:
            async for msg in call:
                await websocket.send_json(_server_msg_to_dict(msg))
            log_msg("info", f"grpc_to_ws: stream finished normally for user={user_id}")
        except Exception as e:
            log_msg("error", f"grpc_to_ws task failed: {str(e)}")

    sender = asyncio.create_task(ws_to_grpc())
    receiver = asyncio.create_task(grpc_to_ws())
    try:
        await asyncio.gather(sender, receiver)
    except Exception as e:
        log_msg("error", f"asyncio.gather failed in chat_ws: {str(e)}")
    finally:
        log_msg("info", f"Cleaning up WebSocket connection for user={user_id}")
        sender.cancel()
        receiver.cancel()
        await channel.close()
