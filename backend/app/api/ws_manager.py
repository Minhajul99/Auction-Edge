"""
WebSocket connection manager for real-time auction updates.

Single in-memory manager — fine for a single-process dev/demo deployment.
If you ever scale to multiple backend instances, this would need to move
to a shared pub/sub (e.g. Redis) so a bid handled by instance A can notify
clients connected to instance B.
"""

import uuid
from typing import Dict, Set

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        # auction_id -> set of connected websockets watching that auction
        self._connections: Dict[uuid.UUID, Set[WebSocket]] = {}

    async def connect(self, auction_id: uuid.UUID, websocket: WebSocket):
        await websocket.accept()
        self._connections.setdefault(auction_id, set()).add(websocket)

    def disconnect(self, auction_id: uuid.UUID, websocket: WebSocket):
        conns = self._connections.get(auction_id)
        if conns:
            conns.discard(websocket)
            if not conns:
                del self._connections[auction_id]

    async def broadcast(self, auction_id: uuid.UUID, message: dict):
        """Send a JSON message to every client currently watching this auction."""
        conns = self._connections.get(auction_id)
        if not conns:
            return
        dead = set()
        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            conns.discard(ws)


# Single shared instance, imported wherever a broadcast needs to happen.
manager = ConnectionManager()
