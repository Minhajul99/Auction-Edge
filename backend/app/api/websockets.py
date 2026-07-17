import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.ws_manager import manager

router = APIRouter(tags=["websockets"])


@router.websocket("/ws/auctions/{auction_id}")
async def auction_updates(websocket: WebSocket, auction_id: uuid.UUID):
    """
    Clients connect here to receive live updates for a specific auction:
    new bids (price + end_time changes) and closure events.
    No auth required — this only pushes public-facing data (same fields
    as AuctionOut), nothing sensitive.
    """
    await manager.connect(auction_id, websocket)
    try:
        while True:
            # We don't expect messages from the client; just keep the
            # connection alive and detect disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(auction_id, websocket)