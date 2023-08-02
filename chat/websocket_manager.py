from typing import Dict
from fastapi import WebSocket
from fastapi import WebSocket, WebSocketDisconnect
from redis_config import get_redis

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str):
        self.active_connections.pop(user_id, None)

    async def send_message(self, message: str, user_id: str):
        ws = self.active_connections.get(user_id)
        if ws:
            await ws.send_text(message)

manager = ConnectionManager()

async def handle_websocket(websocket: WebSocket, user_id: str):
    await manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_text()
            # Get the global Redis connection and use it
            async with get_redis() as r:
                # Store message in Redis
                await r.lpush(f"chat:{user_id}", data)
            await manager.send_message(f"Message text was: {data}", user_id)
    except WebSocketDisconnect:
        manager.disconnect(user_id)
