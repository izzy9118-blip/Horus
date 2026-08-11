#!/usr/bin/env python3
"""Deterministic calendar normalization for Horus acquisition planning.

The language tooth cannot depend on an LLM guessing a local calendar date.  Horus
normalizes dates in code before any first-party archive search is allowed to count.
"""
from __future__ import annotations

import datetime as dt


class CalendarError(ValueError):
    pass


def _parse_iso_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise CalendarError(f"invalid Gregorian ISO date: {value!r}") from exc


def gregorian_to_solar_hijri(value: str) -> str:
    """Convert Gregorian YYYY-MM-DD to Solar Hijri YYYY-MM-DD.

    Integer algorithm derived from the standard 2820/33-year arithmetic conversion
    used by widely deployed Jalali implementations.  The function is deliberately
    small and dependency-free so the conversion used in an acquisition receipt is
    reproducible from the pinned Horus commit.
    """
    date = _parse_iso_date(value)
    gy, gm, gd = date.year, date.month, date.day
    gdm = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)
    gy2 = gy + 1 if gm > 2 else gy
    days = (
        355666
        + 365 * gy
        + (gy2 + 3) // 4
        - (gy2 + 99) // 100
        + (gy2 + 399) // 400
        + gd
        + gdm[gm - 1]
    )
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + days % 31
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + (days - 186) % 30
    return f"{jy:04d}-{jm:02d}-{jd:02d}"


def normalize_date(value: str, calendar: str) -> str:
    _parse_iso_date(value)
    if calendar == "gregorian":
        return value
    if calendar == "solar_hijri":
        return gregorian_to_solar_hijri(value)
    raise CalendarError(f"unsupported calendar: {calendar!r}")
