import asyncio
import logging
from pathlib import Path

import uvicorn

from livescores.config import load_config
from livescores.polling.engine import PollingEngine
from livescores.sources.espn import ESPNSource
from livescores.sources.sofascore import SofaScoreSource
from livescores.state import MatchState
from livescores.web.app import create_app
from livescores.web.routes import ws_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

CONFIG_PATH = Path("config.toml")


def main() -> None:
    config = load_config(CONFIG_PATH)
    state = MatchState()

    sources = [ESPNSource(), SofaScoreSource()]

    async def broadcast(diff):
        await ws_manager.broadcast(diff)

    engine = PollingEngine(
        state=state,
        sources=sources,
        broadcast_fn=broadcast,
        config=config,
    )

    app = create_app(state=state, start_polling=True)

    @app.on_event("startup")
    async def startup():
        logger.info("Starting polling engine")
        asyncio.create_task(engine.run())

    @app.on_event("shutdown")
    async def shutdown():
        logger.info("Stopping polling engine")
        await engine.stop()

    logger.info("Starting server on %s:%d", config.server.host, config.server.port)
    uvicorn.run(app, host=config.server.host, port=config.server.port)


if __name__ == "__main__":
    main()
