import logging
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse

from livescores.state import MatchDiff, MatchState

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket, state: MatchState) -> None:
        await ws.accept()
        self._connections.add(ws)
        await ws.send_json({
            "type": "full_state",
            "data": state.get_all_serialized(),
        })

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard(ws)

    async def broadcast(self, diff: MatchDiff) -> None:
        message = {"type": "match_update", "data": diff.to_dict()}
        dead: set[WebSocket] = set()
        for ws in self._connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)
        self._connections -= dead


ws_manager = ConnectionManager()


def create_router(state: MatchState) -> APIRouter:
    router = APIRouter()

    @router.get("/")
    async def dashboard():
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return JSONResponse({"status": "ok", "message": "Dashboard not built yet"})

    @router.get("/api/matches")
    async def get_matches():
        return state.get_all_serialized()

    @router.get("/api/matches/{match_id}")
    async def get_match(match_id: str):
        match = state.get(match_id)
        if match is None:
            return JSONResponse({"error": "Match not found"}, status_code=404)
        return match.model_dump(mode="json")

    @router.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws_manager.connect(ws, state)
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            ws_manager.disconnect(ws)

    return router
