import json
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger("capitolseeder.websocket")

router = APIRouter(tags=["WebSocket"])

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Remaining: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        if not self.active_connections:
            return
        
        payload = json.dumps(message)
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception as e:
                logger.warning(f"Failed to send to socket: {e}")
                dead_connections.append(connection)
        
        for dead in dead_connections:
            self.disconnect(dead)

manager = ConnectionManager()

@router.websocket("/ws/live-trades")
async def websocket_live_trades_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send an immediate connection ACK with state
        await websocket.send_json({
            "type": "CONNECTED",
            "message": "CAPitAL Live Congressional Data Stream connected."
        })
        while True:
            # Keep socket open and receive any ping/client messages
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket unexpected error: {e}")
        manager.disconnect(websocket)
