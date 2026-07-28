"""Contract stability: OpenAPI drift gate and README doc-promises (SPEC 6, 7.8)."""

import json
import re
import tomllib
from pathlib import Path

from faultline.app import app

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_openapi_schema_matches_committed_contract():
    committed = json.loads((REPO_ROOT / "docs" / "openapi.json").read_text())
    live = json.loads(json.dumps(app.openapi()))  # normalize tuples etc. through JSON
    assert live == committed, (
        "docs/openapi.json is stale; regenerate with "
        "`uv run python -m faultline.export_openapi` and commit it"
    )


def _readme_shell_blocks() -> list[str]:
    readme = (REPO_ROOT / "README.md").read_text()
    return re.findall(r"```sh\n(.*?)```", readme, flags=re.DOTALL)


def test_readme_quickstart_run_command_matches_entry_point():
    blocks = _readme_shell_blocks()
    assert any("uv run faultline" in block for block in blocks)
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    assert pyproject["project"]["scripts"]["faultline"] == "faultline.__main__:main"


def test_readme_curl_paths_hit_real_routes(client):
    curl_paths = []
    for block in _readme_shell_blocks():
        for line in block.splitlines():
            match = re.search(r"curl .*?http://127\.0\.0\.1:8000(/\S*)", line)
            if match:
                method = "POST" if "-X POST" in line else "GET"
                curl_paths.append((method, match.group(1)))
    assert curl_paths, "README quickstart should demonstrate curl commands"
    for method, path in curl_paths:
        body = {"failure_rate": 0.5} if method == "POST" else None
        response = client.request(method, path, json=body)
        route_missing = response.status_code == 404 and response.json() == {"detail": "Not Found"}
        assert not route_missing, f"README references a nonexistent route: {method} {path}"


def test_readme_dev_commands_reference_real_tools():
    blocks = "\n".join(_readme_shell_blocks())
    assert "uv run pytest" in blocks
    assert "uv run python -m faultline.export_openapi" in blocks


def test_version_is_consistent():
    import faultline

    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    assert faultline.__version__ == pyproject["project"]["version"]
    assert app.version == faultline.__version__
