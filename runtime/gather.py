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
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from .acquisition import (
        AcquisitionProtocolError,
        _needs_original_t1,
        _resolved_profiles,
        build_receipt,
        registered_channel,
        searched_not_found_allowed,
        url_matches_channel,
        validate_receipt,
    )
except ImportError:
    from acquisition import (
        AcquisitionProtocolError,
        _needs_original_t1,
        _resolved_profiles,
        build_receipt,
        registered_channel,
        searched_not_found_allowed,
        url_matches_channel,
        validate_receipt,
    )

ROOT = Path(__file__).resolve().parents[1]
LIVE_DIR = ROOT / "acquisition" / "live"
QUERY_ID_RE = re.compile(r"^(MHQ|MHAQ)-[A-Z0-9_-]+$")


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
    attempt_by_id = {a["attempt_id"]: a for a in receipt.get("search_attempts", [])}
    source_ids = {s.get("source_ref") for s in response.get("sources_searched", [])}
    for missing in response.get("unfilled_requests", []):
        state = missing.get("evidence_state")
        need = missing.get("information_need", "")
        refs = missing.get("searched_attempt_refs", [])
        if not isinstance(refs, list) or not set(refs) <= attempt_ids:
            raise GatherError(f"unfilled request {need!r} cites acquisition attempts not in the canonical receipt")
        if any(attempt_by_id[ref].get("information_need") != need for ref in refs):
            raise GatherError(f"unfilled request {need!r} cites an acquisition attempt for a different need")
        searched_refs = missing.get("searched_source_refs", [])
        if not isinstance(searched_refs, list) or not set(searched_refs) <= source_ids:
            raise GatherError(f"unfilled request {need!r} cites sources absent from sources_searched")
        if missing.get("absence_claim") is not False:
            raise GatherError(f"unfilled request {need!r} must state absence_claim false")
        if not isinstance(missing.get("reason"), str) or not missing["reason"].strip():
            raise GatherError(f"unfilled request {need!r} is missing its reason")
        if state == "NOT_SEARCHED" and refs:
            raise GatherError(f"NOT_SEARCHED request {need!r} may not cite executed search attempts")
        if state == "SEARCHED_NOT_FOUND" and not searched_not_found_allowed(receipt, need):
            raise GatherError(
                f"SEARCHED_NOT_FOUND is forbidden for {need!r}: the deterministic first-party acquisition protocol was not satisfied"
            )


def _source_map(values: Any, label: str) -> dict[str, dict[str, Any]]:
    if not isinstance(values, list) or not all(isinstance(item, dict) for item in values):
        raise GatherError(f"{label} must be an array of source objects")
    result: dict[str, dict[str, Any]] = {}
    for source in values:
        ref = source.get("source_ref")
        if not isinstance(ref, str) or not ref:
            raise GatherError(f"{label} contains a source without source_ref")
        if ref in result:
            raise GatherError(f"{label} contains duplicate source_ref {ref!r}")
        result[ref] = source
    return result


def _same_source(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return all(right.get(key) == value for key, value in left.items() if key != "rejection_reason")


def _validate_staged_result(query: dict[str, Any], result: dict[str, Any], receipt: dict[str, Any]) -> None:
    status = result.get("status")
    if status not in {"GATHERED", "PARTIALLY_GATHERED", "NOT_GATHERED"}:
        raise GatherError("staged result has invalid status")

    searched = _source_map(result.get("sources_searched"), "sources_searched")
    used = _source_map(result.get("sources_used"), "sources_used")
    rejected = _source_map(result.get("sources_rejected"), "sources_rejected")
    if not set(used) <= set(searched):
        raise GatherError("sources_used must be a subset of sources_searched")
    if not set(rejected) <= set(searched):
        raise GatherError("sources_rejected must be a subset of sources_searched")
    if set(used) & set(rejected):
        raise GatherError("a source may not be both used and rejected")
    for ref, source in used.items():
        if not _same_source(source, searched[ref]):
            raise GatherError(f"used source {ref!r} does not match its searched source record")
    for ref, source in rejected.items():
        if not isinstance(source.get("rejection_reason"), str) or not source["rejection_reason"].strip():
            raise GatherError(f"rejected source {ref!r} is missing rejection_reason")
        if not _same_source(searched[ref], source):
            raise GatherError(f"rejected source {ref!r} does not match its searched source record")

    attempts = receipt.get("search_attempts", [])
    found_by_source: dict[str, list[dict[str, Any]]] = {}
    for attempt in attempts:
        if attempt.get("result") == "FOUND":
            found_by_source.setdefault(attempt["source_ref"], []).append(attempt)
    if not set(searched) <= set(found_by_source):
        missing = sorted(set(searched) - set(found_by_source))
        raise GatherError(f"sources_searched are not grounded in FOUND acquisition attempts: {missing}")

    profiles = _resolved_profiles(query)
    original_t1 = _needs_original_t1(query)
    t1_principal_by_source: dict[str, str] = {}
    t1_principals_by_source_need: dict[tuple[str, str], set[str]] = {}
    for ref, source in searched.items():
        if source.get("source_tier") not in {"T1", "T2", "T3", "T4", "T5"}:
            raise GatherError(f"source {ref!r} has invalid source_tier")
        source_url = source.get("url")
        source_language = source.get("language")
        if not isinstance(source_url, str) or not source_url:
            raise GatherError(f"source {ref!r} must provide its final URL")
        if not isinstance(source_language, str) or not source_language:
            raise GatherError(f"source {ref!r} must provide its language")
        if source.get("source_tier") != "T1":
            continue
        qualifying: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
        for attempt in found_by_source[ref]:
            profile = profiles.get(attempt.get("principal_id"))
            if profile is None or attempt.get("search_method") == "SECONDARY_DISCOVERY":
                continue
            channel = registered_channel(profile, attempt.get("channel_id", ""))
            if channel is None:
                continue
            if (
                attempt.get("channel_class") == channel.get("channel_class")
                and source_language == attempt.get("language")
                and source_language in profile.get("original_languages", [])
                and url_matches_channel(source_url, channel)
            ):
                qualifying.append((profile["principal_id"], profile, channel))
        principals = {item[0] for item in qualifying}
        if original_t1 and len(principals) != 1:
            raise GatherError(
                f"T1 source {ref!r} is not bound to exactly one principal's registered original-language channel"
            )
        if len(principals) == 1:
            t1_principal_by_source[ref] = next(iter(principals))
        for attempt in found_by_source[ref]:
            principal_id = t1_principal_by_source.get(ref)
            if principal_id is not None and attempt.get("principal_id") == principal_id:
                t1_principals_by_source_need.setdefault(
                    (ref, attempt.get("information_need", "")), set()
                ).add(principal_id)

    records = result.get("records_returned")
    unfilled = result.get("unfilled_requests")
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise GatherError("records_returned must be an array of objects")
    if not isinstance(unfilled, list) or not all(isinstance(item, dict) for item in unfilled):
        raise GatherError("unfilled_requests must be an array of objects")
    information_needs = query.get("information_needed", [])
    need_set = set(information_needs)
    returned_needs: set[str] = set()
    record_sources_by_need: dict[str, set[str]] = {}
    qualifying_t1_by_need: dict[str, set[str]] = {}
    for record in records:
        need = record.get("information_need")
        if need not in need_set:
            raise GatherError(f"returned record information_need {need!r} is outside the query")
        refs = record.get("source_refs")
        if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) and ref for ref in refs):
            raise GatherError(f"returned record for {need!r} must cite non-empty source_refs")
        if not set(refs) <= set(used):
            raise GatherError(f"returned record for {need!r} cites a source absent from sources_used")
        for ref in refs:
            if not any(attempt.get("information_need") == need for attempt in found_by_source[ref]):
                raise GatherError(f"returned record for {need!r} cites source {ref!r} acquired for a different need")
        if record.get("tier") == "T1":
            if any(used[ref].get("source_tier") != "T1" for ref in refs):
                raise GatherError(f"T1 record for {need!r} cites a non-T1 source")
            if record.get("language_state") != "ORIGINAL":
                raise GatherError(f"T1 record for {need!r} must have language_state ORIGINAL")
            qualifying_t1_by_need.setdefault(need, set()).update(refs)
        returned_needs.add(need)
        record_sources_by_need.setdefault(need, set()).update(refs)

    unfilled_needs: set[str] = set()
    for missing in unfilled:
        need = missing.get("information_need")
        if need not in need_set:
            raise GatherError(f"unfilled request information_need {need!r} is outside the query")
        if need in unfilled_needs:
            raise GatherError(f"duplicate unfilled request for {need!r}")
        unfilled_needs.add(need)

    if status == "GATHERED":
        if unfilled:
            raise GatherError("GATHERED result may not contain unfilled requests")
        if returned_needs != need_set:
            raise GatherError("GATHERED result must return a record for every information need")
    elif status == "PARTIALLY_GATHERED":
        if not records or not unfilled:
            raise GatherError("PARTIALLY_GATHERED requires both returned records and unfilled requests")
        if returned_needs | unfilled_needs != need_set:
            raise GatherError("PARTIALLY_GATHERED must account for every information need")
    else:
        if records or used:
            raise GatherError("NOT_GATHERED may not return records or use sources")
        if unfilled_needs != need_set:
            raise GatherError("NOT_GATHERED must account for every information need as unfilled")

    referenced_sources = set().union(*record_sources_by_need.values()) if record_sources_by_need else set()
    if set(used) != referenced_sources:
        raise GatherError("every source in sources_used must support at least one returned record")

    if original_t1 and status == "GATHERED":
        for need in information_needs:
            cited = qualifying_t1_by_need.get(need, set())
            for principal_id in profiles:
                if not any(
                    principal_id in t1_principals_by_source_need.get((ref, need), set())
                    for ref in cited
                ):
                    raise GatherError(
                        f"GATHERED original-language T1 result lacks qualifying {principal_id!r} ground for {need!r}"
                    )

    response_view = {**result}
    _validate_unfilled_against_receipt(response_view, receipt)


def build_response(query: dict[str, Any], mode: str = "LIVE") -> dict[str, Any]:
    query_id = query.get("query_id")
    minister = query.get("minister_id")
    if not isinstance(query_id, str) or not QUERY_ID_RE.fullmatch(query_id):
        raise GatherError("query_id must be a safe MHQ-/MHAQ- identifier")
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
        _validate_staged_result(query, result, receipt)

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
