"""Entry point: `uv run faultline`."""

import uvicorn

from faultline import config


def main() -> None:
    uvicorn.run(
        "faultline.app:app",
        host=config.host(),
        port=config.port(),
        log_config=None,
        access_log=False,
    )


if __name__ == "__main__":
    main()
