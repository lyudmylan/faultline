# Repository instructions for coding agents

## Project

faultline: a small, deliberately unreliable HTTP service — a controlled target for
incident-response, monitoring, and log-analysis tooling. `docs/SPEC.md` is the source of
truth for the API surface, failure semantics, telemetry schema, and behavioral invariants.

## Commands

```
uv sync --dev                               # install dependencies
uv run faultline                            # run the service (127.0.0.1:8000)
uv run ruff format .                        # format
uv run ruff check .                         # lint
uv run pytest                               # tests (coverage >= 90% enforced)
uv run python -m faultline.export_openapi   # regenerate docs/openapi.json
```

Format, lint, and tests must pass locally before pushing.

## Workflow

- Routine changes may be committed directly to `main`; use a branch + PR when a change
  alters the SPEC contract. (Deliberate loosening of the shared github-shipping default.)
- Update `CHANGELOG.md` in the same commit as any behavior change.
- After changing the API surface, regenerate `docs/openapi.json` in the same commit.

## Rules

- The unreliability is the product. The seeded defects (D1: `GET /products/3` → 500,
  D2: `POST /orders` with `product_id: 4` → 500) and every deliberate failure mode are
  contract, not bugs — never "fix" them. Changes to failure semantics go through
  `docs/SPEC.md` first. This overrides the shared `repo-review` lens: reviews here check
  that failures stay deterministic, documented, and observable, not that they disappear.
- Every behavior stays observable: structured JSON logs and Prometheus metrics must match
  the SPEC telemetry schema.
- No real credentials or production data anywhere; this is a local test target.
