import json
from pathlib import Path

from jsonschema import Draft202012Validator

from runtime.acquisition import build_plan, build_receipt, searched_not_found_allowed, validate_receipt
from runtime.calendars import gregorian_to_solar_hijri
from runtime.gather import _fallback_unfilled

BASE = Path(__file__).resolve().parents[1]


def query():
    return {
        "record_type": "minister_horus_query",
        "query_id": "MHQ-US-IRAN-20260810",
        "inquiry_id": "us-iran-2026-08-10",
        "minister_id": "xenophon",
        "information_needed": ["Current official positions of the United States and Iran regarding the dispute."],
        "source_requirements": [{
            "requirement": "Hear both principals in their own current words before judgment.",
            "rationale": "The inquiry concerns a live bilateral dispute.",
            "acceptable_tiers": ["T1"],
            "original_language_required": True,
        }],
        "specific_document_requests": [],
        "principal_scope": ["United States", "Iran"],
        "time_scope": {"start": "2026-08-10", "end": "2026-08-10"},
        "disallowed_substitutions": ["Press reporting may not substitute for original-language T1."],
        "reason_for_request": "Ground the live inquiry symmetrically.",
        "source_selection_rule": "HORUS_RETAINS_SOURCE_SELECTION_INDEPENDENCE_EXCEPT_EXPLICIT_DOCUMENT_REQUESTS",
        "source_absence_taxonomy": "HORUS-SOURCE-STATE-1.0",
        "provenance": {"produced_by": "xenophon", "repository_commit": "a" * 40},
    }


def attempts(block_iran_archive=False):
    need = query()["information_needed"][0]
    rows = []
    serial = 1
    definitions = {
        "united-states": [
            ("whitehouse-gov", "PRIMARY", "DIRECT_FIRST_PARTY_ARCHIVE"),
            ("whitehouse-gov", "PRIMARY", "DIRECT_FIRST_PARTY_SITE_SEARCH"),
            ("state-gov", "ALTERNATE_PRIMARY", "ALTERNATE_FIRST_PARTY_CHANNEL"),
            ("whitehouse-gov", "EXTERNAL_RECOVERY", "FIRST_PARTY_DOMAIN_RECOVERY"),
        ],
        "iran": [
            ("president-ir", "PRIMARY", "DIRECT_FIRST_PARTY_ARCHIVE"),
            ("mfa-gov-ir", "ALTERNATE_PRIMARY", "DIRECT_FIRST_PARTY_SITE_SEARCH"),
            ("geneva-mfa-ir", "DIPLOMATIC_PRIMARY", "ALTERNATE_FIRST_PARTY_CHANNEL"),
            ("mfa-gov-ir", "EXTERNAL_RECOVERY", "FIRST_PARTY_DOMAIN_RECOVERY"),
        ],
    }
    for principal, values in definitions.items():
        for channel, klass, method in values:
            result = "NO_MATCH"
            if block_iran_archive and principal == "iran" and method == "DIRECT_FIRST_PARTY_ARCHIVE":
                result = "ACCESS_BLOCKED"
            rows.append({
                "attempt_id": f"ATT-{serial}",
                "information_need": need,
                "principal_id": principal,
                "channel_id": channel,
                "channel_class": klass,
                "search_method": method,
                "language": "fa" if principal == "iran" else "en",
                "canonical_date": "2026-08-10",
                "local_date": "1405-05-19" if principal == "iran" else "2026-08-10",
                "query": "fixture query",
                "url": None,
                "result": result,
                "source_ref": None,
                "detail": None,
                "attempted_at": "2026-08-10T23:30:00Z",
            })
            serial += 1
    return rows


def non_t1_query():
    return {
        "record_type": "minister_horus_adversarial_query",
        "query_id": "MHAQ-NONT1",
        "inquiry_id": "INQ-1",
        "minister_id": "xenophon",
        "information_needed": ["Was effective operational command unchanged after the appointment?"],
        "source_requirements": [{
            "proposition_id": "P-1",
            "requirement": "Find operational evidence bearing on effective command.",
            "rationale": "The proposition concerns field command rather than the signed instrument alone.",
            "acceptable_tiers": ["T2", "T4"],
            "original_language_required": False,
        }],
        "principal_scope": ["Ukraine"],
        "time_scope": {"start": "2026-07-22", "end": "2026-08-10"},
        "source_selection_rule": "HORUS_RETAINS_SOURCE_SELECTION_INDEPENDENCE_EXCEPT_EXPLICIT_DOCUMENT_REQUESTS",
        "source_absence_taxonomy": "HORUS-SOURCE-STATE-1.0",
        "provenance": {"produced_by": "xenophon", "repository_commit": "a" * 40},
    }


def test_august_10_2026_is_19_mordad_1405():
    assert gregorian_to_solar_hijri("2026-08-10") == "1405-05-19"


def test_plan_carries_principal_local_dates():
    plan = build_plan(query())
    iran = [x for x in plan["date_normalizations"] if x["principal_id"] == "iran"]
    us = [x for x in plan["date_normalizations"] if x["principal_id"] == "united-states"]
    assert iran == [{
        "principal_id": "iran",
        "canonical_date": "2026-08-10",
        "timezone": "Asia/Tehran",
        "calendar": "solar_hijri",
        "local_date": "1405-05-19",
    }]
    assert us == [{
        "principal_id": "united-states",
        "canonical_date": "2026-08-10",
        "timezone": "America/New_York",
        "calendar": "gregorian",
        "local_date": "2026-08-10",
    }]


def test_complete_reachable_ladder_allows_searched_not_found():
    receipt = build_receipt(query(), attempts(), mode="FIXTURE")
    validate_receipt(query(), receipt)
    need = query()["information_needed"][0]
    assert searched_not_found_allowed(receipt, need) is True


def test_blocked_primary_archive_prevents_searched_not_found():
    receipt = build_receipt(query(), attempts(block_iran_archive=True), mode="FIXTURE")
    need = query()["information_needed"][0]
    assert searched_not_found_allowed(receipt, need) is False
    missing = _fallback_unfilled(query(), receipt)
    assert missing[0]["evidence_state"] == "SOURCE_ACQUIRED_INCOMPLETE"
    assert missing[0]["absence_claim"] is False


def test_non_t1_search_does_not_inherit_four_step_t1_ladder():
    q = non_t1_query()
    need = q["information_needed"][0]
    receipt = build_receipt(q, [{
        "attempt_id": "ATT-NONT1-1",
        "information_need": need,
        "principal_id": "ukraine",
        "channel_id": "president-gov-ua",
        "channel_class": "PRIMARY",
        "search_method": "DIRECT_FIRST_PARTY_SITE_SEARCH",
        "language": "uk",
        "canonical_date": "2026-08-10",
        "local_date": "2026-08-10",
        "query": "fixture operational command search",
        "url": None,
        "result": "NO_MATCH",
        "source_ref": None,
        "detail": None,
        "attempted_at": "2026-08-10T23:30:00Z",
    }], mode="FIXTURE")
    assert receipt["requirements"] == []
    assert searched_not_found_allowed(receipt, need) is True
    assert _fallback_unfilled(q, receipt)[0]["evidence_state"] == "SEARCHED_NOT_FOUND"


def test_profile_and_receipt_contracts_validate():
    profile_schema = json.loads((BASE / "contracts/principal-source-profile.schema.json").read_text(encoding="utf-8"))
    receipt_schema = json.loads((BASE / "contracts/acquisition-receipt.schema.json").read_text(encoding="utf-8"))
    for path in sorted((BASE / "registry/principals").glob("*.json")):
        Draft202012Validator(profile_schema).validate(json.loads(path.read_text(encoding="utf-8")))
    Draft202012Validator(receipt_schema).validate(build_receipt(query(), attempts(), mode="FIXTURE"))
