from __future__ import annotations


def compare_endpoint_sets(before: list[dict], after: list[dict]) -> dict:
    b = {x.get("id"): x for x in before}
    a = {x.get("id"): x for x in after}
    ids = sorted(set(b) | set(a))
    changes = []
    critical_regressions = []
    for check_id in ids:
        pre = b.get(check_id)
        post = a.get(check_id)
        change = {"id": check_id, "before": pre, "after": post}
        changes.append(change)
        if pre and pre.get("ok") and (not post or not post.get("ok")):
            critical_regressions.append(check_id)
    return {
        "ok": not critical_regressions,
        "critical_regressions": critical_regressions,
        "changes": changes,
    }
