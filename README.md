# faultline

A small, deliberately unreliable HTTP service. faultline is a controlled
target for incident-response, monitoring, and log-analysis tooling: every
failure mode is reproducible on demand, and everything the service does is
observable through structured JSON logs and Prometheus metrics.

The full contract — API surface, failure semantics, telemetry schema, and
behavioral invariants — lives in [docs/SPEC.md](docs/SPEC.md).

## Quickstart

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```sh
uv run faultline
```

The service binds to `127.0.0.1:8000` by default (`HOST`, `PORT`, and
`FAULTLINE_LOG_DIR` override; see the spec). Then, in another terminal:

```sh
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/products
curl http://127.0.0.1:8000/products/3
curl -X POST http://127.0.0.1:8000/chaos/enable -H 'content-type: application/json' -d '{"failure_rate": 0.5}'
curl http://127.0.0.1:8000/metrics
```

`/products/3` is one of the two seeded defects (D1: division by zero on a
zero-stock row) — expect a 500 and a stack trace in the logs. Interactive
API docs are at `/docs`.

## What's inside

- **Business API** — a tiny in-memory shop (`/products`, `/orders`) with two
  documented, data-dependent defects (D1, D2).
- **Simulation API** — deterministic triggers under `/simulate`: arbitrary
  status codes, unhandled exceptions, slow responses, hangs, flaky 502s,
  process crashes, memory ballast, CPU burn.
- **Chaos mode** — `POST /chaos/enable` degrades business endpoints with
  configurable failure rate, error status, and extra latency, while
  `/health` and `/metrics` stay green.
- **Telemetry** — one JSON object per log line (stdout + rotating
  `app.log`), request correlation via `X-Request-ID`, Prometheus metrics
  at `/metrics`.

## Development

```sh
uv run pytest
uv run ruff format --check .
uv run ruff check .
uv run python -m faultline.export_openapi
```

`docs/openapi.json` is the committed API contract; regenerate it in the
same PR as any surface change (a drift test enforces this).
