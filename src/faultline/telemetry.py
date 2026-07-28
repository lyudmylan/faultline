"""Health and metrics endpoints — always green while the process is alive."""

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from faultline import chaos, metrics

router = APIRouter(tags=["telemetry"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "uptime_seconds": metrics.uptime_seconds()}


@router.get("/metrics", response_class=PlainTextResponse)
def metrics_endpoint() -> str:
    return metrics.render(chaos_enabled=chaos.state.enabled)
