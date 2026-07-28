"""Minimal in-process metrics with Prometheus text exposition."""

import resource
import sys
import time
from collections import defaultdict

START_TIME = time.monotonic()

requests_total: dict[tuple[str, str, int], int] = defaultdict(int)
duration_sum: dict[tuple[str, str], float] = defaultdict(float)
duration_count: dict[tuple[str, str], int] = defaultdict(int)
exceptions_total: dict[str, int] = defaultdict(int)


def observe_request(method: str, path: str, status: int, duration_seconds: float) -> None:
    requests_total[(method, path, status)] += 1
    duration_sum[(method, path)] += duration_seconds
    duration_count[(method, path)] += 1


def observe_exception(exception_type: str) -> None:
    exceptions_total[exception_type] += 1


def uptime_seconds() -> float:
    return time.monotonic() - START_TIME


def max_rss_bytes() -> int:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # ru_maxrss is bytes on macOS, kilobytes on Linux.
    return rss if sys.platform == "darwin" else rss * 1024


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def render(chaos_enabled: bool) -> str:
    lines: list[str] = []

    lines.append("# HELP http_requests_total Total HTTP requests handled.")
    lines.append("# TYPE http_requests_total counter")
    for (method, path, status), count in sorted(requests_total.items()):
        lines.append(
            f'http_requests_total{{method="{_escape(method)}",path="{_escape(path)}",'
            f'status="{status}"}} {count}'
        )

    lines.append("# HELP http_request_duration_seconds Request duration summary.")
    lines.append("# TYPE http_request_duration_seconds summary")
    for (method, path), total in sorted(duration_sum.items()):
        labels = f'method="{_escape(method)}",path="{_escape(path)}"'
        lines.append(f"http_request_duration_seconds_sum{{{labels}}} {total}")
        lines.append(
            f"http_request_duration_seconds_count{{{labels}}} {duration_count[(method, path)]}"
        )

    lines.append("# HELP http_exceptions_total Unhandled exceptions by Python class name.")
    lines.append("# TYPE http_exceptions_total counter")
    for exception_type, count in sorted(exceptions_total.items()):
        lines.append(f'http_exceptions_total{{type="{_escape(exception_type)}"}} {count}')

    lines.append("# HELP faultline_chaos_enabled Whether chaos mode is active.")
    lines.append("# TYPE faultline_chaos_enabled gauge")
    lines.append(f"faultline_chaos_enabled {int(chaos_enabled)}")

    lines.append("# HELP process_uptime_seconds Seconds since process start.")
    lines.append("# TYPE process_uptime_seconds gauge")
    lines.append(f"process_uptime_seconds {uptime_seconds()}")

    lines.append("# HELP process_max_rss_bytes Peak resident set size.")
    lines.append("# TYPE process_max_rss_bytes gauge")
    lines.append(f"process_max_rss_bytes {max_rss_bytes()}")

    return "\n".join(lines) + "\n"
