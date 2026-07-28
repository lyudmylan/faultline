# faultline — Service Specification

This document is the contract for the `faultline` service. It owns the API
surface, failure semantics, telemetry schema, and behavioral invariants.
Operational instructions live in `README.md`; decision rationale lives in
`docs/adr/`; delivery status lives in the GitHub tracker, never here.

## 1. Purpose

faultline is a small, deliberately unreliable HTTP service. It exists as a
controlled target for incident-response, monitoring, and log-analysis
tooling: every failure mode is reproducible on demand, and everything the
service does is observable through structured logs and metrics.

## 2. Non-goals

- No authentication, no persistence, no external dependencies at runtime.
- Not a load generator or performance benchmark target.
- Binds to localhost by default; never intended for public exposure.
- The business domain (a tiny store) is scenery for realistic failures, not
  a product.

## 3. Runtime and configuration

Python 3.12+, FastAPI on uvicorn, managed with uv. Started with
`uv run faultline`.

| Variable | Default | Meaning |
| --- | --- | --- |
| `HOST` | `127.0.0.1` | bind address |
| `PORT` | `8000` | bind port |
| `FAULTLINE_LOG_DIR` | `./logs` | directory for the JSON log file |

## 4. API contract

The normative machine-readable contract is `docs/openapi.json`, exported
from the application and drift-gated in CI (section 6). This section defines
semantics the schema cannot express.

### 4.1 Business API — the shop

In-memory store; state resets on restart. **Chaos mode (4.3) applies to
these endpoints only.**

| Endpoint | Behavior |
| --- | --- |
| `GET /products` | list all products |
| `GET /products/{id}` | product detail with derived `units_ordered` and `turnover_score`; 404 if unknown |
| `POST /orders` | body `{product_id, quantity}` (quantity 1–1000); 201 with `total_price`; 404 unknown product; 409 when quantity exceeds stock |
| `GET /orders` | list orders created since start |
| `GET /orders/{id}` | order detail; 404 if unknown |

**Seeded defects** — two deliberate, stable, data-dependent bugs that model
real production defect shapes (most inputs succeed; specific data fails):

| Id | Trigger | Failure |
| --- | --- | --- |
| D1 | `GET /products/3` (seed row with `units_in_stock: 0`) | `ZeroDivisionError` computing `turnover_score` → 500 |
| D2 | `POST /orders` with `product_id: 4` (seed row with `price: null`) | `TypeError` computing `total_price` → 500 |

The defects are documented, not hidden: faultline is a sandbox, not a
puzzle. Tools under test should discover them from telemetry, not source.

### 4.2 Simulation API — deterministic triggers

Grouped under `/simulate`. **Exempt from chaos mode** (they are operator
controls, not business traffic). All are `GET` for curl ergonomics.

| Endpoint | Parameters (bounds, default) | Behavior |
| --- | --- | --- |
| `/simulate/status/{code}` | code 200–599 | responds with that status; 204/304 without a body |
| `/simulate/exception` | `kind` ∈ runtime\|key\|zero\|type\|index (runtime) | raises a genuine unhandled exception of that type → 500 |
| `/simulate/slow` | `seconds` 0–120 (2) | async delay, then 200 |
| `/simulate/hang` | — | never responds; connection held open (client-timeout testing) |
| `/simulate/flaky` | `rate` 0–1 (0.5) | 502 with probability `rate`, else 200 |
| `/simulate/crash` | `delay` 0.1–10 (0.3) | responds 200, then the process exits with code 1 after `delay` seconds |
| `/simulate/memory` | `mb` 1–512 (100) | allocates and holds `mb` MB of incompressible memory; 409 once total held would exceed 2048 MB |
| `/simulate/memory/release` | — | frees all held ballast, reports released MB |
| `/simulate/cpu` | `seconds` 0–60 (5) | burns one CPU core in a worker thread; the service stays responsive |

### 4.3 Chaos mode

Runtime degradation switch for "started failing at 14:32" scenarios.

| Endpoint | Behavior |
| --- | --- |
| `POST /chaos/enable` | body (all optional): `failure_rate` 0–1 (0.3), `error_status` 400–599 (503), `extra_latency_ms` 0–60000 (0) |
| `POST /chaos/disable` | restore normal behavior immediately |
| `GET /chaos` | current state |

Semantics, applied per request to business endpoints only:

1. Add latency drawn uniformly from `[0, extra_latency_ms]`.
2. With probability `failure_rate`, respond `error_status` with the
   degraded-response envelope (4.5) without invoking the endpoint.

Exempt path prefixes: `/health`, `/metrics`, `/chaos`, `/simulate`,
`/docs`, `/openapi.json`, `/redoc`. Health staying green while business
traffic fails is deliberate — the classic "monitoring says healthy, users
disagree" incident shape. Enable/disable transitions are logged at WARNING
as timeline markers.

### 4.4 Telemetry

`GET /health` → `{"status": "ok", "uptime_seconds": <float>}`.

`GET /metrics` → Prometheus text exposition format:

| Metric | Type | Labels |
| --- | --- | --- |
| `http_requests_total` | counter | `method`, `path` (route template when resolved), `status` |
| `http_request_duration_seconds_sum` / `_count` | summary | `method`, `path` |
| `http_exceptions_total` | counter | `type` (Python exception class name) |
| `faultline_chaos_enabled` | gauge | — |
| `process_uptime_seconds` | gauge | — |
| `process_max_rss_bytes` | gauge | — |

**Logs**: one JSON object per line, to stdout and to a rotating
`app.log` (5 MB × 3 backups) under `FAULTLINE_LOG_DIR`. Base fields:

| Field | Content |
| --- | --- |
| `ts` | ISO-8601 UTC with milliseconds, `Z` suffix |
| `level` | `INFO` / `WARNING` / `ERROR` / `CRITICAL` |
| `logger` | emitting module |
| `message` | human-readable line |
| `request_id` | present on all request-scoped lines |
| `event` | machine key when applicable (see below) |
| `stack` | formatted traceback, on unhandled exceptions only |

`event` values: `startup`, `request` (access line: adds `method`, `path`,
`status`, `duration_ms`, `client`), `unhandled_exception` (adds
`exception_type`), `chaos_enabled`, `chaos_disabled`, `chaos_failure`,
`simulated_exception`, `hang`, `crash`, `memory_ballast`,
`memory_released`, `cpu_burn`, `order_created`.

**Request correlation**: an incoming `X-Request-ID` header is adopted,
otherwise a 12-hex id is generated. Every response carries the header;
every log line for that request carries the field.

### 4.5 Error envelopes

| Case | Status | Body |
| --- | --- | --- |
| Unhandled exception | 500 | `{"error": "internal server error", "exception_type": "<class>", "request_id": "<id>"}` |
| Chaos-injected failure | configured | `{"error": "service temporarily degraded", "request_id": "<id>"}` |
| Domain rejection (unknown id, insufficient stock) | 404 / 409 | FastAPI `{"detail": "<reason>"}` |
| Validation failure | 422 | FastAPI validation shape |

## 5. Behavioral invariants

Each invariant is enforced by at least one test.

- **I1** Every response carries `X-Request-ID`; a provided id is echoed
  verbatim.
- **I2** An unhandled exception produces exactly: one ERROR log line with
  `stack`, one `http_exceptions_total` increment, and the 500 envelope.
- **I3** Chaos mode never alters responses on exempt path prefixes.
- **I4** `POST /chaos/disable` restores normal behavior immediately.
- **I5** `/health` and `/metrics` return 200 whenever the process is alive,
  including under chaos and CPU burn.
- **I6** Held memory ballast never exceeds 2048 MB.
- **I7** `/simulate/crash` logs at CRITICAL before the process exits, and
  the exit code is 1.
- **I8** Every handled request — including chaos-injected failures and
  error responses — produces exactly one `event: request` access line.

## 6. Contract stability

- `docs/openapi.json` is exported from the app
  (`uv run python -m faultline.export_openapi`) and committed. A test fails
  when the live application schema differs from the committed file;
  regeneration belongs in the same PR as the surface change.
- Semantic versioning of the service: MAJOR for breaking API or telemetry
  schema changes, MINOR for additive surface, PATCH for fixes. Each release:
  CHANGELOG entry, `pyproject.toml` version bump, annotated git tag —
  in the same commit.

## 7. Acceptance criteria

v0.1.0 is done when:

1. Every endpoint in section 4 behaves as specified, verified by
   behavior-named pytest suites.
2. D1 and D2 reproduce deterministically and appear in logs (with stacks)
   and in `http_exceptions_total`.
3. Invariants I1–I8 each have a dedicated test.
4. Property-based tests cover parameter bounds (status codes across
   200–599, flaky rate extremes 0 and 1, validation rejection outside
   bounds).
5. Log output is machine-parseable: every line of a test run parses as JSON
   with the base fields of 4.4.
6. Coverage ≥ 90% enforced in CI; ruff format+check, pytest, gitleaks, and
   pip-audit all green.
7. The OpenAPI drift gate passes and `docs/openapi.json` is committed.
8. README quickstart commands are covered by a doc-promise test.
