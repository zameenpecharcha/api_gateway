from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import grpc
from grpc import aio as grpaio
from app.proto_files.chat import chat_pb2, chat_pb2_grpc


chat_router = APIRouter()


@chat_router.websocket("/ws/chat/{room_id}/{user_id}")
async def chat_ws(websocket: WebSocket, room_id: str, user_id: str):
    await websocket.accept()

    channel = grpaio.insecure_channel("localhost:50060")
    stub = chat_pb2_grpc.ChatServiceStub(channel)
    call = stub.Chat()

    # Send initial register message
    await call.write(chat_pb2.ClientMessage(room_id=room_id, user_id=user_id))

    async def ws_to_grpc():
        try:
            while True:
                text = await websocket.receive_text()
                await call.write(chat_pb2.ClientMessage(room_id=room_id, user_id=user_id, text=text))
        except WebSocketDisconnect:
            pass
        finally:
            await call.done_writing()

    async def grpc_to_ws():
        try:
            async for msg in call:
                await websocket.send_json({
                    "roomId": msg.room_id,
                    "userId": msg.user_id,
                    "messageId": msg.message_id,
                    "text": msg.text,
                    "sentAt": msg.sent_at_unix_ms,
                    "deliveredAt": msg.delivered_at_unix_ms,
                })
        except Exception:
            pass

    sender = asyncio.create_task(ws_to_grpc())
    receiver = asyncio.create_task(grpc_to_ws())
    try:
        await asyncio.gather(sender, receiver)
    finally:
        sender.cancel()
        receiver.cancel()
        await channel.close()


