from __future__ import annotations

from dataclasses import dataclass, asdict
from time import perf_counter
from urllib import request, error
from urllib.parse import urljoin


@dataclass
class EndpointResult:
    id: str
    url: str
    expected_status: int
    status: int | None
    elapsed_ms: int
    ok: bool
    error: str | None = None

    def to_dict(self):
        return asdict(self)


def check_endpoint(base_url: str, spec: dict) -> EndpointResult:
    path = spec.get("path", "/")
    url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    method = spec.get("method", "GET").upper()
    expected = int(spec.get("expected_status", 200))
    timeout = float(spec.get("timeout_seconds", 15))
    req = request.Request(url, method=method, headers={"User-Agent": "moodle-upgrade-kit/0.1"})
    start = perf_counter()
    status = None
    err = None
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            status = int(resp.status)
    except error.HTTPError as exc:
        status = int(exc.code)
        err = f"HTTPError: {exc.code}"
    except Exception as exc:  # bounded error string only
        err = f"{type(exc).__name__}: {exc}"
    elapsed = int((perf_counter() - start) * 1000)
    return EndpointResult(
        id=str(spec.get("id", path)),
        url=url,
        expected_status=expected,
        status=status,
        elapsed_ms=elapsed,
        ok=(status == expected),
        error=err,
    )


def run_endpoint_checks(config: dict) -> list[dict]:
    base_url = config["moodle"]["base_url"]
    return [check_endpoint(base_url, spec).to_dict() for spec in config.get("endpoints", [])]
