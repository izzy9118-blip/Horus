#!/usr/bin/env python3
"""Load pinned principal source profiles for the Horus acquisition engine."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "principals"


class SourceRegistryError(ValueError):
    pass


def _norm(value: str) -> str:
    return " ".join(value.strip().casefold().replace("_", " ").replace("-", " ").split())


def profile_files() -> list[Path]:
    return sorted(REGISTRY.glob("*.json"))


def load_profile(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    try:
        profile = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceRegistryError(f"invalid source profile {path}: {exc}") from exc
    if profile.get("record_type") != "horus_principal_source_profile":
        raise SourceRegistryError(f"invalid source profile record_type: {path}")
    return profile, hashlib.sha256(raw).hexdigest()


def resolve_principal(value: str) -> tuple[dict[str, Any], str, str]:
    target = _norm(value)
    matches: list[tuple[dict[str, Any], str, str]] = []
    for path in profile_files():
        profile, digest = load_profile(path)
        names = [profile.get("principal_id", ""), profile.get("principal_name", "")]
        names.extend(profile.get("aliases", []))
        if target in {_norm(str(name)) for name in names if str(name).strip()}:
            matches.append((profile, str(path.relative_to(ROOT)), digest))
    if not matches:
        raise SourceRegistryError(f"no principal source profile for {value!r}")
    if len(matches) > 1:
        raise SourceRegistryError(f"ambiguous principal source profile for {value!r}")
    return matches[0]
