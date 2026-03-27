from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from livescores.state import MatchState
from livescores.web.routes import create_router

STATIC_DIR = Path(__file__).parent / "static"


def create_app(state: MatchState | None = None, start_polling: bool = True) -> FastAPI:
    if state is None:
        state = MatchState()

    app = FastAPI(title="Live Scores")
    app.state.match_state = state
    app.state.start_polling = start_polling

    router = create_router(state)
    app.include_router(router)

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    return app
