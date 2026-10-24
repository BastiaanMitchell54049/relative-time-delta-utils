"""Core engine for parsing and applying relative time phrases.

Grammar (intentionally narrow, see README):

    <phrase> ::= <ordinal> <weekday>
              | <ordinal> <weekday> "of" <month>
              | <proximity> <weekday>
              | "last day of" <month>

A <phrase> resolves to a single concrete date when applied to a reference date.
All offsets are non-rolling: e.g. "first Monday of January" is January's first
Monday regardless of where the reference date sits.

Design notes
------------
* The parser is hand-written rather than regex-driven so that error messages can
  point at the offending token (regex would make the messages opaque).
* Everything is standard-library only; the suite must run offline.
* Determinism: the engine never consults the wall clock. Every call takes a
  ``base`` datetime so tests can pin the reference.
"""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple


class RelativeTimeError(ValueError):
    """Raised when a phrase is syntactically or semantically invalid."""


@dataclass(frozen=True)
class Weekday:
    """Thin wrapper around ``calendar`` day constants for ergonomic naming."""
    cal_value: int
    name: str


# Ordered Monday-first so that day-of-week math is a simple modulo.
WEEKDAYS: List[Weekday] = [
    Weekday(calendar.MONDAY, "Monday"),
    Weekday(calendar.TUESDAY, "Tuesday"),
    Weekday(calendar.WEDNESDAY, "Wednesday"),
    Weekday(calendar.THURSDAY, "Thursday"),
    Weekday(calendar.FRIDAY, "Friday"),
    Weekday(calendar.SATURDAY, "Saturday"),
    Weekday(calendar.SUNDAY, "Sunday"),
]


@dataclass(frozen=True)
class Month:
    """Named month 1–12; keeps the parser clear of bare ints."""
    number: int
    name: str


MONTHS: List[Month] = [Month(i, calendar.month_name[i]) for i in range(1, 13)]

_ORDINAL_WORDS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5,
}
_PROXIMITY_WORDS = {"last", "next", "previous"}
_ORDINAL_RE = re.compile(r"^(\d+)(?:st|nd|rd|th)$")


def _weekday_by_name(name: str) -> Weekday:
    key = name.lower()
    for wd in WEEKDAYS:
        if wd.name.lower() == key:
            return wd
    raise RelativeTimeError(f"Unknown weekday: {name!r}")


def _month_by_name(name: str) -> Month:
    key = name.lower()
    for m in MONTHS:
        if m.name.lower() == key:
            return m
    raise RelativeTimeError(f"Unknown month: {name!r}")


def _parse_ordinal(token: str) -> int:
    lower = token.lower()
    if lower in _ORDINAL_WORDS:
        return _ORDINAL_WORDS[lower]
    m = _ORDINAL_RE.match(lower)
    if m:
        return int(m.group(1))
    raise RelativeTimeError(f"Invalid ordinal: {token!r}")


def _tokenize(phrase: str) -> List[str]:
    return phrase.strip().split()


def _resolve_ordinal_in_month(
    ordinal: int, weekday: Weekday, month: Month, year: int
) -> date:
    """Return the ``ordinal``-th occurrence of ``weekday`` in ``month``/``year``."""
    if ordinal < 1:
        raise RelativeTimeError(f"Ordinal must be >= 1, got {ordinal}")
    first = date(year, month.number, 1)
    offset = (weekday.cal_value - first.weekday()) % 7
    day = 1 + offset + (ordinal - 1) * 7
    # ``date`` raises ValueError for days beyond the month, which we normalise
    # into our own error type so callers get a single exception family.
    try:
        return date(year, month.number, day)
    except ValueError as exc:
        raise RelativeTimeError(
            f"{ordinal}-th {weekday.name} does not exist in {month.name} {year}"
    ) from exc


def _resolve_ordinal_in_year(
    ordinal: int, weekday: Weekday, year: int
) -> date:
    """Return the ``ordinal``-th ``weekday`` of the entire year (January 1 base)."""
    if ordinal < 1:
        raise RelativeTimeError(f"Ordinal must be >= 1, got {ordinal}")
    first = date(year, 1, 1)
    offset = (weekday.cal_value - first.weekday()) % 7
    day_of_year = 1 + offset + (ordinal - 1) * 7
    try:
        return first + timedelta(days=day_of_year - 1)
    except OverflowError as exc:  # pragma: no cover - defensive only
        raise RelativeTimeError(
            f"{ordinal}-th {weekday.name} does not exist in {year}"
        ) from exc


def _resolve_proximity_weekday(
    base: date, proximity: str, weekday: Weekday
) -> date:
    """Resolve 'last/next/previous <weekday>' relative to ``base``.

    'last'   -> most recent strict past occurrence
    'next'   -> nearest strict future occurrence
    'previous' -> synonym for 'last'
    """
    diff = (weekday.cal_value - base.weekday()) % 7
    if proximity in ("last", "previous"):
        # 0 -> 7 days back so 'last Monday' on a Monday is the previous week.
        return base - timedelta(days=diff if diff != 0 else 7)
    # next
    return base + timedelta(days=diff if diff != 0 else 7)


def _resolve_last_day_of_month(month: Month, year: int) -> date:
    last_day = calendar.monthrange(year, month.number)[1]
    return date(year, month.number, last_day)


@dataclass
class RelativeTimeDelta:
    """Parse a relative-time phrase and apply it to arbitrary reference dates.

    The phrase is parsed once at construction; ``apply`` then re-targets the
    resolved rule against any base date, which is cheaper than re-parsing and
    makes the object reusable in pipelines.
    """

    phrase: str
    # Parsed decomposition (exactly one branch is populated):
    _ordinal_in_month: Optional[Tuple[int, Weekday, Month]] = None
    _ordinal_in_year: Optional[Tuple[int, Weekday]] = None
    _proximity: Optional[Tuple[str, Weekday]] = None
    _last_day_of_month: Optional[Month] = None

    def __init__(self, phrase: str) -> None:
        self.phrase = phrase
        tokens = _tokenize(phrase)
        if not tokens:
            raise RelativeTimeError("Empty phrase")
        self._ordinal_in_month = None
        self._ordinal_in_year = None
        self._proximity = None
        self._last_day_of_month = None
        self._dispatch(tokens)

    # -- parsing -----------------------------------------------------------
    def _dispatch(self, tokens: List[str]) -> None:
        lower0 = tokens[0].lower()
        if lower0 == "last" and len(tokens) == 4 and tokens[2].lower() == "of":
            self._last_day_of_month = _month_by_name(tokens[3])
            return
        if lower0 in _PROXIMITY_WORDS and len(tokens) == 2:
            self._proximity = (lower0, _weekday_by_name(tokens[1]))
            return
        if lower0 in _ORDINAL_WORDS or _ORDINAL_RE.match(lower0):
            if len(tokens) == 2:
                ordinal = _parse_ordinal(tokens[0])
                weekday = _weekday_by_name(tokens[1])
                self._ordinal_in_year = (ordinal, weekday)
                return
            if len(tokens) == 4 and tokens[2].lower() == "of":
                ordinal = _parse_ordinal(tokens[0])
                weekday = _weekday_by_name(tokens[1])
                month = _month_by_name(tokens[3])
                self._ordinal_in_month = (ordinal, weekday, month)
                return
        raise RelativeTimeError(f"Unrecognised phrase: {self.phrase!r}")

    # -- application -------------------------------------------------------
    def apply(self, base: datetime) -> datetime:
        """Return the concrete datetime referred to by this phrase.

        Time-of-day is preserved from ``base``; only the calendar date shifts.
        """
        base_date = base.date()
        if self._ordinal_in_month is not None:
            ordinal, weekday, month = self._ordinal_in_month
            year = base_date.year
            result = _resolve_ordinal_in_month(ordinal, weekday, month, year)
        elif self._ordinal_in_year is not None:
            ordinal, weekday = self._ordinal_in_year
            result = _resolve_ordinal_in_year(ordinal, weekday, base_date.year)
        elif self._proximity is not None:
            proximity, weekday = self._proximity
            result = _resolve_proximity_weekday(base_date, proximity, weekday)
        elif self._last_day_of_month is not None:
            result = _resolve_last_day_of_month(self._last_day_of_month, base_date.year)
        else:  # pragma: no cover - dispatch prevents this
            raise RelativeTimeError("Uninitialised rule")
        return datetime.combine(result, base.time(), tzinfo=base.tzinfo)
