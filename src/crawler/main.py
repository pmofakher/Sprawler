"""Entrypoint for running the Sprawler service."""

import uvicorn
from crawler.core.config import settings


def main():
    """Runs the Uvicorn server for Sprawler."""
    uvicorn.run(
        "crawler.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
