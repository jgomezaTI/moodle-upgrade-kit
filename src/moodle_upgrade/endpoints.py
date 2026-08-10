from __future__ import annotations

from dataclasses import dataclass, asdict
import ssl
from time import perf_counter
from urllib import request, error
from urllib.parse import urljoin


@dataclass
class EndpointResult:
    id: str
    url: str
    method: str
    expected_status: int
    status: int | None
    elapsed_ms: int
    executed: bool
    ok: bool
    tls_verified: bool
    final_url: str | None = None
    error: str | None = None

    def to_dict(self):
        return asdict(self)


def check_endpoint(base_url: str, spec: dict, *, allow_insecure_tls: bool = False) -> EndpointResult:
    path = spec.get("path", "/")
    url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    method = spec.get("method", "GET").upper()
    expected = int(spec.get("expected_status", 200))
    timeout = float(spec.get("timeout_seconds", 15))
    verify_tls = bool(spec.get("verify_tls", True))
    if method not in {"GET", "HEAD", "OPTIONS"}:
        return EndpointResult(
            id=str(spec.get("id", path)), url=url, method=method, expected_status=expected,
            status=None, elapsed_ms=0, executed=False, ok=False, tls_verified=verify_tls,
            error=f"Unsafe read-only endpoint method rejected: {method}",
        )
    if not verify_tls and not allow_insecure_tls:
        return EndpointResult(
            id=str(spec.get("id", path)), url=url, method=method, expected_status=expected,
            status=None, elapsed_ms=0, executed=False, ok=False, tls_verified=False,
            error="Disabled TLS verification is not allowed for this environment.",
        )
    req = request.Request(url, method=method, headers={"User-Agent": "moodle-upgrade-kit/0.1"})
    context = ssl.create_default_context()
    if not verify_tls:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    start = perf_counter()
    status = None
    err = None
    final_url = None
    try:
        with request.urlopen(req, timeout=timeout, context=context) as resp:
            status = int(resp.status)
            final_url = str(resp.geturl())
    except error.HTTPError as exc:
        status = int(exc.code)
        err = f"HTTPError: {exc.code}"
        final_url = str(exc.geturl())
    except Exception as exc:  # bounded error string only
        err = f"{type(exc).__name__}: {exc}"[:500]
    elapsed = int((perf_counter() - start) * 1000)
    return EndpointResult(
        id=str(spec.get("id", path)),
        url=url,
        method=method,
        expected_status=expected,
        status=status,
        elapsed_ms=elapsed,
        executed=True,
        ok=(status == expected),
        tls_verified=verify_tls,
        final_url=final_url,
        error=err,
    )


def run_endpoint_checks(config: dict) -> list[dict]:
    base_url = config["moodle"]["base_url"]
    environment = str(config.get("project", {}).get("environment", "")).lower()
    allow_insecure_tls = environment != "production"
    return [check_endpoint(base_url, spec, allow_insecure_tls=allow_insecure_tls).to_dict() for spec in config.get("endpoints", [])]
