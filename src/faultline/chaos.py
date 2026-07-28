"""Chaos mode: runtime degradation applied to business endpoints."""

import logging
from dataclasses import dataclass

from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

EXEMPT_PREFIXES = (
    "/health",
    "/metrics",
    "/chaos",
    "/simulate",
    "/docs",
    "/openapi.json",
    "/redoc",
)


@dataclass
class ChaosState:
    enabled: bool = False
    failure_rate: float = 0.3
    error_status: int = 503
    extra_latency_ms: int = 0


state = ChaosState()


def is_exempt(path: str) -> bool:
    return path.startswith(EXEMPT_PREFIXES)


class ChaosSettings(BaseModel):
    failure_rate: float = Field(default=0.3, ge=0, le=1)
    error_status: int = Field(default=503, ge=400, le=599)
    extra_latency_ms: int = Field(default=0, ge=0, le=60_000)


router = APIRouter(tags=["chaos"])


def _snapshot() -> dict:
    return {
        "enabled": state.enabled,
        "failure_rate": state.failure_rate,
        "error_status": state.error_status,
        "extra_latency_ms": state.extra_latency_ms,
    }


@router.post("/chaos/enable")
def enable_chaos(settings: ChaosSettings | None = None) -> dict:
    settings = settings or ChaosSettings()
    state.enabled = True
    state.failure_rate = settings.failure_rate
    state.error_status = settings.error_status
    state.extra_latency_ms = settings.extra_latency_ms
    logger.warning(
        "chaos mode enabled",
        extra={"event": "chaos_enabled", **_snapshot()},
    )
    return _snapshot()


@router.post("/chaos/disable")
def disable_chaos() -> dict:
    state.enabled = False
    logger.warning("chaos mode disabled", extra={"event": "chaos_disabled"})
    return _snapshot()


@router.get("/chaos")
def chaos_status() -> dict:
    return _snapshot()
