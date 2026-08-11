#!/usr/bin/env python3
"""Canonical Horus acquisition boundary.

Input: one validated MHQ/MHAQ JSON object on stdin.
Output: one provenance-bearing Horus response JSON object on stdout.

A tool-capable host may stage two JSON files under acquisition/live/ before this
command runs:
  <query_id>.attempts.json  - the raw acquisition-attempt trace
  <query_id>.result.json    - documentary records/sources produced by those attempts

The canonical Horus engine, not the host, computes the acquisition receipt and
source-state floor.  If no host material is staged, Horus fails closed as
NOT_SEARCHED.  It never fabricates a successful search merely to let a minister run.
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from .acquisition import (
        AcquisitionProtocolError,
        build_receipt,
        searched_not_found_allowed,
        validate_receipt,
    )
except ImportError:
    from acquisition import (
        AcquisitionProtocolError,
        build_receipt,
        searched_not_found_allowed,
        validate_receipt,
    )

ROOT = Path(__file__).resolve().parents[1]
LIVE_DIR = ROOT / "acquisition" / "live"


class GatherError(ValueError):
    pass


def _json_object(text: str, label: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GatherError(f"{label} is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise GatherError(f"{label} must be one JSON object")
    return value


def _repo_commit() -> str:
    process = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        raise GatherError("cannot determine pinned Horus repository commit")
    commit = process.stdout.strip()
    if len(commit) != 40:
        raise GatherError("invalid Horus repository commit")
    return commit


def _load_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GatherError(f"invalid acquisition attempt file {path}: {exc}") from exc
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise GatherError(f"acquisition attempt file {path} must contain a JSON array of objects")
    return value


def _load_result(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return _json_object(path.read_text(encoding="utf-8"), f"staged Horus result {path}")


def _attempt_refs(receipt: dict[str, Any], information_need: str) -> list[str]:
    return [
        attempt["attempt_id"]
        for attempt in receipt.get("search_attempts", [])
        if attempt.get("information_need") == information_need
    ]


def _source_refs(receipt: dict[str, Any], information_need: str) -> list[str]:
    refs = []
    for attempt in receipt.get("search_attempts", []):
        if attempt.get("information_need") != information_need:
            continue
        ref = attempt.get("source_ref")
        if isinstance(ref, str) and ref and ref not in refs:
            refs.append(ref)
    return refs


def _fallback_unfilled(query: dict[str, Any], receipt: dict[str, Any]) -> list[dict[str, Any]]:
    values = []
    for need in query.get("information_needed", []):
        attempt_refs = _attempt_refs(receipt, need)
        searched_refs = _source_refs(receipt, need)
        if not attempt_refs:
            state = "NOT_SEARCHED"
            reason = "The canonical Horus acquisition engine received no executed search attempts for this information need."
        elif searched_not_found_allowed(receipt, need):
            state = "SEARCHED_NOT_FOUND"
            reason = "The required first-party acquisition ladder was reachable and completed, but no qualifying record was acquired."
        else:
            state = "SOURCE_ACQUIRED_INCOMPLETE"
            reason = "Acquisition was attempted, but the required first-party ladder was blocked, incomplete, or otherwise not sufficient for SEARCHED_NOT_FOUND."
        values.append({
            "information_need": need,
            "reason": reason,
            "evidence_state": state,
            "searched_source_refs": searched_refs,
            "searched_attempt_refs": attempt_refs,
            "absence_claim": False,
        })
    return values


def _validate_unfilled_against_receipt(response: dict[str, Any], receipt: dict[str, Any]) -> None:
    attempt_ids = {a["attempt_id"] for a in receipt.get("search_attempts", [])}
    for missing in response.get("unfilled_requests", []):
        state = missing.get("evidence_state")
        need = missing.get("information_need", "")
        refs = missing.get("searched_attempt_refs", [])
        if not isinstance(refs, list) or not set(refs) <= attempt_ids:
            raise GatherError(f"unfilled request {need!r} cites acquisition attempts not in the canonical receipt")
        if state == "NOT_SEARCHED" and refs:
            raise GatherError(f"NOT_SEARCHED request {need!r} may not cite executed search attempts")
        if state == "SEARCHED_NOT_FOUND" and not searched_not_found_allowed(receipt, need):
            raise GatherError(
                f"SEARCHED_NOT_FOUND is forbidden for {need!r}: the deterministic first-party acquisition protocol was not satisfied"
            )


def build_response(query: dict[str, Any], mode: str = "LIVE") -> dict[str, Any]:
    query_id = query.get("query_id")
    minister = query.get("minister_id")
    if not isinstance(query_id, str) or not query_id:
        raise GatherError("query_id is required")
    if not isinstance(minister, str) or not minister:
        raise GatherError("minister_id is required")

    attempts = _load_list(LIVE_DIR / f"{query_id}.attempts.json")
    receipt = build_receipt(query, attempts, mode=mode)
    validate_receipt(query, receipt)
    staged = _load_result(LIVE_DIR / f"{query_id}.result.json")

    if staged is None:
        result = {
            "status": "NOT_GATHERED",
            "sources_searched": [],
            "sources_used": [],
            "sources_rejected": [],
            "records_returned": [],
            "unfilled_requests": _fallback_unfilled(query, receipt),
        }
    else:
        allowed = {"status", "sources_searched", "sources_used", "sources_rejected", "records_returned", "unfilled_requests"}
        extra = set(staged) - allowed
        if extra:
            raise GatherError(f"staged result contains fields owned by the canonical engine: {sorted(extra)}")
        result = staged

    response = {
        "record_type": "horus_query_response",
        "query_id": query_id,
        "requesting_minister": minister,
        "request_as_received": query,
        "status": result.get("status"),
        "source_absence_taxonomy": "HORUS-SOURCE-STATE-1.0",
        "acquisition": receipt,
        "sources_searched": result.get("sources_searched", []),
        "sources_used": result.get("sources_used", []),
        "sources_rejected": result.get("sources_rejected", []),
        "records_returned": result.get("records_returned", []),
        "unfilled_requests": result.get("unfilled_requests", []),
        "provenance": {
            "horus_repository_commit": _repo_commit(),
            "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "query_log_path": "queries.log",
        },
        "completeness": "PENDING_PROBE",
    }
    _validate_unfilled_against_receipt(response, receipt)
    return response


def main() -> int:
    try:
        query = _json_object(sys.stdin.read(), "Horus query")
        mode = "FIXTURE" if "PYTEST_CURRENT_TEST" in __import__("os").environ else "LIVE"
        response = build_response(query, mode=mode)
        sys.stdout.write(json.dumps(response, ensure_ascii=False, sort_keys=True) + "\n")
        return 0
    except (GatherError, AcquisitionProtocolError) as exc:
        sys.stderr.write(f"HORUS ACQUISITION ERROR: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
