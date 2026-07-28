# Changelog

All notable changes to faultline. The format follows
[Keep a Changelog](https://keepachangelog.com/); versioning follows the
semantic-versioning policy in docs/SPEC.md section 6.

## [0.1.0] - 2026-07-28

Initial release.

### Added

- Business API: in-memory shop (`/products`, `/orders`) with derived
  `units_ordered` / `turnover_score` fields and seeded defects D1
  (zero-stock division) and D2 (null-price TypeError).
- Simulation API under `/simulate`: `status/{code}`, `exception`, `slow`,
  `hang`, `flaky`, `crash`, `memory` + `memory/release` (2048 MB cap),
  `cpu`.
- Chaos mode (`/chaos/enable`, `/chaos/disable`, `/chaos`) with
  configurable failure rate, error status, and extra latency; business
  endpoints only, telemetry stays green.
- Telemetry: `/health`, Prometheus `/metrics`, structured JSON logs to
  stdout and rotating `app.log`, `X-Request-ID` correlation.
- Behavioral invariants I1–I8, each with a dedicated test; property-based
  bound tests; OpenAPI drift gate; README doc-promise tests.
- CI: ruff format+check, pytest with coverage ≥ 90%, gitleaks, pip-audit.
