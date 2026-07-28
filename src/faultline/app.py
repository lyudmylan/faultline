"""Application factory and module-level ASGI app."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

import faultline
from faultline import chaos, shop, simulate, telemetry
from faultline.logging_setup import setup_logging
from faultline.middleware import RequestPipelineMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    logger.info(
        "faultline %s started",
        faultline.__version__,
        extra={"event": "startup", "version": faultline.__version__},
    )
    yield


def create_app() -> FastAPI:
    setup_logging()
    application = FastAPI(
        title="faultline",
        version=faultline.__version__,
        description=(
            "A small, deliberately unreliable HTTP service: a controlled target for "
            "incident-response, monitoring, and log-analysis tooling."
        ),
        lifespan=lifespan,
    )
    application.add_middleware(RequestPipelineMiddleware)
    application.include_router(shop.router)
    application.include_router(simulate.router)
    application.include_router(chaos.router)
    application.include_router(telemetry.router)
    return application


app = create_app()
