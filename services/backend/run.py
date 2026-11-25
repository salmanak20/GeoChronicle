"""Run the desktop-owned local API with graceful server shutdown."""

import uvicorn

from app.core.config import settings
from app.main import app


def main() -> None:
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=settings.port,
        log_config=None,
        timeout_graceful_shutdown=4,
    )
    server = uvicorn.Server(config)
    app.state.uvicorn_server = server
    server.run()


if __name__ == "__main__":
    main()
