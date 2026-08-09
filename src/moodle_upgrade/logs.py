from __future__ import annotations

from collections import Counter
from pathlib import Path


def analyze_text(text: str, patterns: dict[str, list[str]]) -> dict:
    findings = {}
    for severity, needles in patterns.items():
        counts = Counter()
        for needle in needles:
            count = text.count(needle)
            if count:
                counts[needle] = count
        findings[severity] = dict(counts)
    return findings


def analyze_files(files: list[str], patterns: dict[str, list[str]], max_bytes_per_file: int = 2_000_000) -> dict:
    result = {"files": [], "totals": {}}
    aggregate = Counter()
    for file_name in files:
        p = Path(file_name)
        if not p.exists() or not p.is_file():
            result["files"].append({"path": file_name, "readable": False, "findings": {}})
            continue
        size = p.stat().st_size
        with p.open("rb") as fh:
            if size > max_bytes_per_file:
                fh.seek(-max_bytes_per_file, 2)
            raw = fh.read(max_bytes_per_file)
        text = raw.decode("utf-8", errors="replace")
        findings = analyze_text(text, patterns)
        result["files"].append({"path": file_name, "readable": True, "findings": findings})
        for severity, mapping in findings.items():
            aggregate[severity] += sum(mapping.values())
    result["totals"] = dict(aggregate)
    return result
