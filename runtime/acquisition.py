#!/usr/bin/env python3
"""Deterministic pre-search protocol and acquisition-receipt validation for Horus.

This module does not judge evidence and does not decide what a source means. It
makes the procedure that precedes a T1 gap machine-visible. In particular,
SEARCHED_NOT_FOUND is not allowed to stand on a few ad-hoc web queries when a
first-party T1 request is in force: the minimum first-party search ladder must
have been both attempted and successfully reachable.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from typing import Any
from urllib.parse import urlparse

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
ATTEMPT_ID_RE = re.compile(r"^ATT-[A-Z0-9_-]+$")


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
    if not isinstance(scope, dict):
        raise AcquisitionProtocolError("query time_scope must be an object")
    start = scope.get("start")
    end = scope.get("end")
    if start in (None, "") and end in (None, ""):
        return []
    if not isinstance(start, str) or not isinstance(end, str) or not start or not end:
        raise AcquisitionProtocolError("query time_scope must provide both start and end dates")
    try:
        first = dt.date.fromisoformat(start)
        last = dt.date.fromisoformat(end)
    except ValueError as exc:
        raise AcquisitionProtocolError("query time_scope dates must use valid YYYY-MM-DD values") from exc
    if first > last:
        raise AcquisitionProtocolError("query time_scope start must not be after end")
    return [(first + dt.timedelta(days=offset)).isoformat() for offset in range((last - first).days + 1)]


def _url_host(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise AcquisitionProtocolError(f"acquisition URL must be an absolute HTTP(S) URL: {url!r}")
    return parsed.hostname.casefold().rstrip(".")


def _channel_hosts(channel: dict[str, Any]) -> set[str]:
    hosts = {_url_host(channel["base_url"])}
    for host in channel.get("allowed_redirect_hosts", []):
        if not isinstance(host, str) or not host.strip():
            raise AcquisitionProtocolError(f"invalid allowed_redirect_hosts entry for channel {channel.get('channel_id')!r}")
        normalized = host.casefold().strip().rstrip(".")
        if "://" in normalized or "/" in normalized:
            raise AcquisitionProtocolError(
                f"allowed redirect host for channel {channel.get('channel_id')!r} must be a hostname"
            )
        hosts.add(normalized)
    return hosts


def url_matches_channel(url: str, channel: dict[str, Any]) -> bool:
    host = _url_host(url)
    return any(host == allowed or host.endswith("." + allowed) for allowed in _channel_hosts(channel))


def registered_channel(profile: dict[str, Any], channel_id: str) -> dict[str, Any] | None:
    return next((c for c in profile.get("channels", []) if c.get("channel_id") == channel_id), None)


def expected_date_pairs(plan: dict[str, Any]) -> dict[str, set[tuple[str, str]]]:
    values: dict[str, set[tuple[str, str]]] = {}
    for item in plan.get("date_normalizations", []):
        values.setdefault(item["principal_id"], set()).add((item["canonical_date"], item["local_date"]))
    return values


def _resolved_profiles(query: dict[str, Any]) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    for principal in query.get("principal_scope") or []:
        profile, _, _ = resolve_principal(principal)
        profiles[profile["principal_id"]] = profile
    return profiles


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
    if not ATTEMPT_ID_RE.fullmatch(str(attempt["attempt_id"])):
        raise AcquisitionProtocolError(f"invalid search attempt id: {attempt['attempt_id']!r}")
    if attempt["result"] not in ATTEMPT_RESULTS:
        raise AcquisitionProtocolError(f"invalid search attempt result: {attempt['result']}")
    if attempt["search_method"] not in set(REQUIRED_T1_STEPS) | {"SECONDARY_DISCOVERY"}:
        raise AcquisitionProtocolError(f"invalid search method: {attempt['search_method']}")
    if not isinstance(attempt.get("url"), str) or not attempt["url"].strip():
        raise AcquisitionProtocolError("search attempt missing url")
    _url_host(attempt["url"])
    if not isinstance(attempt.get("detail"), str) or not attempt["detail"].strip():
        raise AcquisitionProtocolError("search attempt missing detail")
    if attempt["result"] == "FOUND":
        if not isinstance(attempt.get("source_ref"), str) or not attempt["source_ref"].strip():
            raise AcquisitionProtocolError("FOUND search attempt must identify source_ref")
    elif attempt.get("source_ref") not in (None, ""):
        raise AcquisitionProtocolError("only a FOUND search attempt may identify source_ref")
    try:
        dt.datetime.fromisoformat(str(attempt["attempted_at"]).replace("Z", "+00:00"))
    except ValueError as exc:
        raise AcquisitionProtocolError("search attempt attempted_at must be a valid ISO date-time") from exc


def _validate_attempt_against_registry(
    attempt: dict[str, Any],
    profiles: dict[str, dict[str, Any]],
    original_t1: bool,
    information_needs: set[str],
    planned_dates: dict[str, set[tuple[str, str]]],
) -> None:
    if attempt["information_need"] not in information_needs:
        raise AcquisitionProtocolError(
            f"search attempt information_need {attempt['information_need']!r} is outside the query"
        )
    if not profiles:
        return
    principal_id = attempt["principal_id"]
    if principal_id not in profiles:
        raise AcquisitionProtocolError(
            f"search attempt principal {principal_id!r} is outside the query's pinned principal scope"
        )
    profile = profiles[principal_id]
    expected = planned_dates.get(principal_id, set())
    pair = (attempt.get("canonical_date"), attempt.get("local_date"))
    if expected and pair not in expected:
        raise AcquisitionProtocolError(
            f"search attempt date pair {pair!r} does not match the deterministic plan for {principal_id!r}"
        )
    if not expected and pair != (None, None):
        raise AcquisitionProtocolError(
            f"search attempt supplied dates for {principal_id!r} although the query has no time scope"
        )
    if attempt["search_method"] == "SECONDARY_DISCOVERY":
        if attempt["channel_class"] != "EXTERNAL_RECOVERY":
            raise AcquisitionProtocolError("SECONDARY_DISCOVERY must use channel_class EXTERNAL_RECOVERY")
        return
    channel = registered_channel(profile, attempt["channel_id"])
    if channel is None:
        raise AcquisitionProtocolError(
            f"search attempt channel {attempt['channel_id']!r} is not registered for principal {principal_id!r}"
        )
    if attempt["search_method"] not in channel.get("supported_methods", []):
        raise AcquisitionProtocolError(
            f"search method {attempt['search_method']!r} is not registered for channel {attempt['channel_id']!r}"
        )
    if attempt["channel_class"] != channel.get("channel_class"):
        raise AcquisitionProtocolError(
            f"search attempt channel_class {attempt['channel_class']!r} does not match registered channel "
            f"{attempt['channel_id']!r} ({channel.get('channel_class')!r})"
        )
    if attempt["language"] not in channel.get("languages", []):
        raise AcquisitionProtocolError(
            f"search attempt for channel {attempt['channel_id']!r} used unregistered language {attempt['language']!r}"
        )
    if original_t1 and attempt["language"] not in profile.get("original_languages", []):
        raise AcquisitionProtocolError(
            f"original-language T1 attempt for {principal_id!r} used unregistered language {attempt['language']!r}"
        )
    if not url_matches_channel(attempt["url"], channel):
        raise AcquisitionProtocolError(
            f"search attempt URL host is not registered for channel {attempt['channel_id']!r}"
        )


def build_receipt(query: dict[str, Any], attempts: list[dict[str, Any]], mode: str = "LIVE") -> dict[str, Any]:
    if mode not in {"LIVE", "FIXTURE"}:
        raise AcquisitionProtocolError("acquisition runtime mode must be LIVE or FIXTURE")
    plan = build_plan(query)
    if not isinstance(attempts, list):
        raise AcquisitionProtocolError("search attempts must be a list")
    profiles = _resolved_profiles(query)
    original_t1 = _needs_original_t1(query)
    information_needs = set(query["information_needed"])
    planned_dates = expected_date_pairs(plan)
    ids: set[str] = set()
    for attempt in attempts:
        if not isinstance(attempt, dict):
            raise AcquisitionProtocolError("each search attempt must be an object")
        _validate_attempt(attempt)
        _validate_attempt_against_registry(
            attempt, profiles, original_t1, information_needs, planned_dates
        )
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
        required_steps = requirement["required_steps"]
        dates = planned_dates.get(requirement["principal_id"], set()) or {(None, None)}
        completed = sorted(
            step for step in required_steps
            if all(any(
                a["search_method"] == step
                and (a.get("canonical_date"), a.get("local_date")) == date_pair
                for a in matches
            ) for date_pair in dates)
        )
        reachable = {
            step for step in required_steps
            if all(any(
                a["search_method"] == step
                and a["result"] in REACHABLE_RESULTS
                and (a.get("canonical_date"), a.get("local_date")) == date_pair
                for a in matches
            ) for date_pair in dates)
        }
        attempted = set(required_steps) <= set(completed)
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
    planned_dates = expected_date_pairs(receipt)
    if planned_dates:
        return all(
            any(
                attempt.get("information_need") == information_need
                and attempt.get("principal_id") == principal_id
                and (attempt.get("canonical_date"), attempt.get("local_date")) == date_pair
                and attempt.get("result") in REACHABLE_RESULTS
                for attempt in receipt.get("search_attempts", [])
            )
            for principal_id, date_pairs in planned_dates.items()
            for date_pair in date_pairs
        )
    return any(
        attempt.get("information_need") == information_need
        and attempt.get("result") in REACHABLE_RESULTS
        for attempt in receipt.get("search_attempts", [])
    )
