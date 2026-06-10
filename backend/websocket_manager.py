"""
WebSocket Connection Manager
Tracks all active browser WebSocket connections and broadcasts
real-time updates when MQTT messages arrive.
"""
import json
import asyncio
from fastapi import WebSocket
from typing import Any


class WebSocketManager:
    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self._connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self._connections:
            self._connections.remove(websocket)

    async def broadcast(self, data: dict[str, Any]):
        """Send JSON data to all connected browsers."""
        if not self._connections:
            return
        payload = json.dumps(data)
        dead = []
        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    @property
    def active_count(self) -> int:
        return len(self._connections)


# Singleton — imported by mqtt_handler and app.py
ws_manager = WebSocketManager()
