import json
from pathlib import Path

from jsonschema import Draft202012Validator

BASE = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((BASE / "contracts/horus-query-response.schema.json").read_text(encoding="utf-8"))


def source():
    return {
        "source_ref": "SRC-1",
        "document_identity": "Official register",
        "url": None,
        "issuer": "Issuing body",
        "date": "2026-08-08",
        "language": "English",
        "source_tier": "T1",
        "retrieval_date": "2026-08-08",
        "repository_path": "files/example.md",
        "sha256": None,
        "relevant_locator": "entry range",
    }


def response():
    s = source()
    return {
        "record_type": "horus_query_response",
        "query_id": "MHQ-TEST-1",
        "requesting_minister": "xenophon",
        "request_as_received": {},
        "status": "GATHERED",
        "source_absence_taxonomy": "HORUS-SOURCE-STATE-1.0",
        "sources_searched": [s],
        "sources_used": [s],
        "sources_rejected": [],
        "records_returned": [{
            "information_need": "Was an appointment recorded?",
            "finding": "The register records no appointment in scope.",
            "evidence_state": "DOCUMENTED_ABSENCE",
            "source_refs": ["SRC-1"],
            "absence_scope": "complete official register for July 2026",
            "absence_basis": "no appointment entry occurs in the complete register",
            "tier": "T1",
            "language": "English",
            "language_state": "ORIGINAL",
        }],
        "unfilled_requests": [],
        "provenance": {"horus_repository_commit": "a" * 40, "generated_at": "2026-08-08T12:00:00Z"},
        "completeness": "PENDING_PROBE",
    }


def test_schema_is_v1_2_0():
    assert SCHEMA["$id"] == "urn:horus:query-response:1.2.0"


def test_documented_absence_requires_positive_fields():
    Draft202012Validator(SCHEMA).validate(response())
    item = response()
    del item["records_returned"][0]["absence_basis"]
    assert list(Draft202012Validator(SCHEMA).iter_errors(item))


def test_unresolved_state_cannot_assert_absence():
    item = response()
    item["status"] = "NOT_GATHERED"
    item["sources_used"] = []
    item["records_returned"] = []
    item["unfilled_requests"] = [{
        "information_need": "Was an appointment recorded?",
        "reason": "No qualifying record found",
        "evidence_state": "SEARCHED_NOT_FOUND",
        "searched_source_refs": ["SRC-1"],
        "absence_claim": True,
    }]
    assert list(Draft202012Validator(SCHEMA).iter_errors(item))


def test_predecessor_contract_is_preserved():
    old = json.loads((BASE / "contracts/horus-query-response.schema.v1.1.0.json").read_text(encoding="utf-8"))
    assert old["$id"] == "urn:horus:query-response:1.1.0"
