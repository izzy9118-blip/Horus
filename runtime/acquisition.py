#!/usr/bin/env python3
"""Deterministic pre-search protocol and acquisition-receipt validation for Horus.

This module does not judge evidence and does not decide what a source means. It
makes the procedure that precedes a T1 gap machine-visible. In particular,
SEARCHED_NOT_FOUND is not allowed to stand on a few ad-hoc web queries when a
first-party T1 request is in force: the minimum first-party search ladder must
have been both attempted and successfully reachable.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

try:
    from .calendars import normalize_date
    from .source_registry import resolve_principal
except ImportError:
    from calendars import normalize_date
    from source_registry import resolve_principal

PROTOCOL = "HORUS-ACQUISITION-1.0"
REQUIRED_T1_STEPS = (
    "DIRECT_FIRST_PARTY_ARCHIVE",
    "DIRECT_FIRST_PARTY_SITE_SEARCH",
    "ALTERNATE_FIRST_PARTY_CHANNEL",
    "FIRST_PARTY_DOMAIN_RECOVERY",
)
ATTEMPT_RESULTS = {
    "FOUND",
    "NO_MATCH",
    "ACCESS_BLOCKED",
    "ENDPOINT_UNAVAILABLE",
    "INDEX_ERROR",
    "TIMEOUT",
    "SOURCE_DISCOVERED_NOT_ACQUIRED",
}
REACHABLE_RESULTS = {"FOUND", "NO_MATCH"}


class AcquisitionProtocolError(ValueError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _needs_original_t1(query: dict[str, Any]) -> bool:
    for requirement in query.get("source_requirements", []):
        if not isinstance(requirement, dict):
            continue
        tiers = requirement.get("acceptable_tiers", [])
        if requirement.get("original_language_required") is True and (not tiers or "T1" in tiers):
            return True
    return False


def _date_scope(query: dict[str, Any]) -> list[str]:
    scope = query.get("time_scope") or {}
    dates: list[str] = []
    for key in ("start", "end"):
        value = scope.get(key)
        if isinstance(value, str) and value and value not in dates:
            dates.append(value)
    return dates


def build_plan(query: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(query, dict):
        raise AcquisitionProtocolError("query must be an object")
    information = query.get("information_needed")
    if not isinstance(information, list) or not information or not all(isinstance(x, str) and x.strip() for x in information):
        raise AcquisitionProtocolError("query information_needed must be a non-empty string list")
    principal_scope = query.get("principal_scope") or []
    original_t1 = _needs_original_t1(query)
    if original_t1 and not principal_scope:
        raise AcquisitionProtocolError("original-language T1 acquisition requires explicit principal_scope")

    profiles: list[dict[str, str]] = []
    date_normalizations: list[dict[str, str]] = []
    resolved: list[tuple[dict[str, Any], str, str]] = []
    for principal in principal_scope:
        profile, path, digest = resolve_principal(principal)
        resolved.append((profile, path, digest))
        profiles.append({
            "principal_id": profile["principal_id"],
            "profile_path": path,
            "profile_sha256": digest,
        })
        for canonical_date in _date_scope(query):
            local_calendars = [c["id"] for c in profile.get("calendars", []) if c.get("role") == "local"]
            if not local_calendars:
                local_calendars = ["gregorian"]
            for calendar in local_calendars:
                date_normalizations.append({
                    "principal_id": profile["principal_id"],
                    "canonical_date": canonical_date,
                    "timezone": profile["timezone"],
                    "calendar": calendar,
                    "local_date": normalize_date(canonical_date, calendar),
                })

    requirements: list[dict[str, Any]] = []
    if original_t1:
        for need in information:
            for profile, _, _ in resolved:
                requirements.append({
                    "information_need": need,
                    "principal_id": profile["principal_id"],
                    "target_tier": "T1",
                    "original_language_required": True,
                    "required_steps": list(REQUIRED_T1_STEPS),
                })

    plan = {
        "protocol": PROTOCOL,
        "query_id": query.get("query_id"),
        "principal_profiles": profiles,
        "date_normalizations": date_normalizations,
        "requirements": requirements,
    }
    plan["plan_sha256"] = hashlib.sha256(_canonical(plan)).hexdigest()
    return plan


def _validate_attempt(attempt: dict[str, Any]) -> None:
    required = (
        "attempt_id", "information_need", "principal_id", "channel_id", "channel_class",
        "search_method", "language", "query", "result", "attempted_at",
    )
    for field in required:
        if attempt.get(field) in (None, ""):
            raise AcquisitionProtocolError(f"search attempt missing {field}")
    if attempt["result"] not in ATTEMPT_RESULTS:
        raise AcquisitionProtocolError(f"invalid search attempt result: {attempt['result']}")
    if attempt["search_method"] not in set(REQUIRED_T1_STEPS) | {"SECONDARY_DISCOVERY"}:
        raise AcquisitionProtocolError(f"invalid search method: {attempt['search_method']}")


def build_receipt(query: dict[str, Any], attempts: list[dict[str, Any]], mode: str = "LIVE") -> dict[str, Any]:
    if mode not in {"LIVE", "FIXTURE"}:
        raise AcquisitionProtocolError("acquisition runtime mode must be LIVE or FIXTURE")
    plan = build_plan(query)
    if not isinstance(attempts, list):
        raise AcquisitionProtocolError("search attempts must be a list")
    ids: set[str] = set()
    for attempt in attempts:
        if not isinstance(attempt, dict):
            raise AcquisitionProtocolError("each search attempt must be an object")
        _validate_attempt(attempt)
        if attempt["attempt_id"] in ids:
            raise AcquisitionProtocolError(f"duplicate attempt_id: {attempt['attempt_id']}")
        ids.add(attempt["attempt_id"])

    requirements: list[dict[str, Any]] = []
    for requirement in plan["requirements"]:
        matches = [
            a for a in attempts
            if a["information_need"] == requirement["information_need"]
            and a["principal_id"] == requirement["principal_id"]
        ]
        completed = sorted({a["search_method"] for a in matches if a["search_method"] in REQUIRED_T1_STEPS})
        required_steps = requirement["required_steps"]
        attempted = set(required_steps) <= set(completed)
        reachable = {
            step for step in required_steps
            if any(a["search_method"] == step and a["result"] in REACHABLE_RESULTS for a in matches)
        }
        satisfied = set(required_steps) <= reachable
        requirements.append({
            **requirement,
            "completed_steps": completed,
            "minimum_protocol_attempted": attempted,
            "minimum_protocol_satisfied": satisfied,
        })

    return {
        "protocol": PROTOCOL,
        "plan_sha256": plan["plan_sha256"],
        "principal_profiles": plan["principal_profiles"],
        "date_normalizations": plan["date_normalizations"],
        "search_attempts": attempts,
        "requirements": requirements,
        "runtime": {
            "engine": "HORUS_CANONICAL_ACQUISITION_ENGINE",
            "engine_path": "runtime/gather.py",
            "mode": mode,
        },
    }


def validate_receipt(query: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(receipt, dict):
        raise AcquisitionProtocolError("acquisition receipt must be an object")
    if receipt.get("protocol") != PROTOCOL:
        raise AcquisitionProtocolError(f"acquisition protocol must be {PROTOCOL}")
    rebuilt = build_receipt(query, receipt.get("search_attempts", []), receipt.get("runtime", {}).get("mode", ""))
    for field in ("plan_sha256", "principal_profiles", "date_normalizations", "requirements"):
        if receipt.get(field) != rebuilt[field]:
            raise AcquisitionProtocolError(f"acquisition receipt {field} does not match the deterministic plan")
    runtime = receipt.get("runtime") or {}
    if runtime.get("engine") != "HORUS_CANONICAL_ACQUISITION_ENGINE" or runtime.get("engine_path") != "runtime/gather.py":
        raise AcquisitionProtocolError("acquisition receipt was not produced through the canonical Horus engine")
    return receipt


def requirement_for(receipt: dict[str, Any], information_need: str, principal_id: str | None = None) -> list[dict[str, Any]]:
    values = []
    for requirement in receipt.get("requirements", []):
        if requirement.get("information_need") != information_need:
            continue
        if principal_id is not None and requirement.get("principal_id") != principal_id:
            continue
        values.append(requirement)
    return values


def searched_not_found_allowed(receipt: dict[str, Any], information_need: str) -> bool:
    """Return whether a negative search result is procedurally admissible.

    Original-language T1 has the stronger constitutional ladder and therefore
    requires every generated T1 requirement to be satisfied. Other tiers still
    require an executed, reachable search attempt, but they do not inherit the T1
    four-step ladder merely because they share the same response taxonomy.
    """
    requirements = requirement_for(receipt, information_need)
    if requirements:
        return all(r.get("minimum_protocol_satisfied") is True for r in requirements)
    return any(
        attempt.get("information_need") == information_need
        and attempt.get("result") in REACHABLE_RESULTS
        for attempt in receipt.get("search_attempts", [])
    )
