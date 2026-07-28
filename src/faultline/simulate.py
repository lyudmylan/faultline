"""Deterministic failure triggers. Operator controls — exempt from chaos mode."""

import asyncio
import logging
import os
import random
import threading
import time

from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/simulate", tags=["simulate"])

MEMORY_CAP_MB = 2048

_ballast: list[bytes] = []


def held_mb() -> int:
    return sum(len(chunk) for chunk in _ballast) // (1024 * 1024)


EXCEPTION_KINDS = {
    "runtime": RuntimeError,
    "key": KeyError,
    "zero": ZeroDivisionError,
    "type": TypeError,
    "index": IndexError,
}


@router.get("/status/{code}")
def simulate_status(code: int = Path(ge=200, le=599)) -> Response:
    if code in (204, 304):
        return Response(status_code=code)
    return JSONResponse({"status": code}, status_code=code)


@router.get("/exception")
def simulate_exception(
    kind: str = Query(default="runtime", pattern="^(runtime|key|zero|type|index)$"),
) -> None:
    logger.info(
        "raising simulated %s exception", kind, extra={"event": "simulated_exception", "kind": kind}
    )
    if kind == "zero":
        _ = 1 / 0
    elif kind == "key":
        _ = {}["missing"]
    elif kind == "type":
        _ = "1" + 1  # type: ignore[operator]
    elif kind == "index":
        _ = [][0]
    raise RuntimeError("simulated runtime failure")


@router.get("/slow")
async def simulate_slow(seconds: float = Query(default=2, ge=0, le=120)) -> dict:
    await asyncio.sleep(seconds)
    return {"delayed_seconds": seconds}


@router.get("/hang")
async def simulate_hang() -> None:
    logger.warning("hanging connection, will never respond", extra={"event": "hang"})
    await asyncio.Event().wait()


@router.get("/flaky")
def simulate_flaky(rate: float = Query(default=0.5, ge=0, le=1)) -> Response:
    if random.random() < rate:
        return JSONResponse({"error": "flaky failure"}, status_code=502)
    return JSONResponse({"status": "ok"})


@router.get("/crash")
async def simulate_crash(delay: float = Query(default=0.3, ge=0.1, le=10)) -> dict:
    async def _die() -> None:
        await asyncio.sleep(delay)
        logger.critical(
            "crashing now: exiting with code 1", extra={"event": "crash", "delay": delay}
        )
        logging.shutdown()
        os._exit(1)

    asyncio.get_running_loop().create_task(_die())
    return {"crashing_in_seconds": delay}


@router.get("/memory")
def simulate_memory(mb: int = Query(default=100, ge=1, le=512)) -> dict:
    if held_mb() + mb > MEMORY_CAP_MB:
        raise HTTPException(
            status_code=409,
            detail=f"refusing allocation: {held_mb()} MB held, cap is {MEMORY_CAP_MB} MB",
        )
    _ballast.append(os.urandom(mb * 1024 * 1024))
    logger.info(
        "allocated %d MB of ballast",
        mb,
        extra={"event": "memory_ballast", "mb": mb, "held_mb": held_mb()},
    )
    return {"allocated_mb": mb, "held_mb": held_mb()}


@router.get("/memory/release")
def simulate_memory_release() -> dict:
    released = held_mb()
    _ballast.clear()
    logger.info(
        "released %d MB of ballast",
        released,
        extra={"event": "memory_released", "released_mb": released},
    )
    return {"released_mb": released, "held_mb": 0}


@router.get("/cpu")
def simulate_cpu(seconds: float = Query(default=5, ge=0, le=60)) -> dict:
    deadline = time.monotonic() + seconds

    def _burn() -> None:
        while time.monotonic() < deadline:
            pass

    threading.Thread(target=_burn, name="cpu-burn", daemon=True).start()
    logger.info(
        "burning one core for %.1f seconds",
        seconds,
        extra={"event": "cpu_burn", "seconds": seconds},
    )
    return {"burning_seconds": seconds}
