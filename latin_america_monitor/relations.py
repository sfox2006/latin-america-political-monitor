"""Headline filter for Latin American international relations.

Countries, leaders, aliases, and international-relations terms live in
``entities.yml``. This module only implements matching.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from .models import Headline

_APOSTROPHES = {"'", "’", "´", "`", "‘"}
# US$ / USD are currency markers, not the United States.
_CURRENCY = re.compile(
    r"(?<![A-Za-z0-9])(?:U\.S\.|US)\s?\$|(?<![A-Za-z0-9])USD(?![A-Za-z0-9])",
    re.IGNORECASE,
)


def entities_path() -> Path:
    return Path(__file__).with_name("entities.yml")


@dataclass(frozen=True)
class Region:
    id: str
    display: str
    order: int


@dataclass(frozen=True)
class Leader:
    name: str
    role: str
    verified: bool
    country_id: str
    gdelt: str | None
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class Country:
    id: str
    display: str
    region_id: str
    market: str | None
    order: int
    query_names: tuple[str, ...]
    leaders: tuple[Leader, ...]


@dataclass(frozen=True)
class Classification:
    tier: int
    region_id: str
    region_display: str
    region_order: int
    country_id: str
    country_display: str
    country_order: int


@dataclass
class Section:
    title: str
    blocks: list[Block] = field(default_factory=list)


@dataclass
class Block:
    title: str
    items: list[Headline]


@dataclass(frozen=True)
class _Pattern:
    folded: re.Pattern[str] | None
    original: re.Pattern[str] | None
    kind: str
    entity_id: str
    country_id: str | None


@dataclass(frozen=True)
class _Hit:
    kind: str
    entity_id: str
    country_id: str | None
    start: int
    end: int


@dataclass(frozen=True)
class EntityIndex:
    regions: dict[str, Region]
    la_countries: tuple[Country, ...]
    foreign_countries: tuple[Country, ...]
    leaders: tuple[Leader, ...]
    gdelt_terms: tuple[str, ...]
    regional_gdelt: tuple[str, ...]
    regional_display: str
    stop_patterns: tuple[re.Pattern[str], ...]
    patterns: tuple[_Pattern, ...]
    country_by_id: dict[str, Country]


def _fold_with_map(text: str) -> tuple[str, list[int]]:
    chars: list[str] = []
    mapping: list[int] = []
    for index, char in enumerate(text):
        if char in _APOSTROPHES:
            chars.append(" ")
            mapping.append(index)
            continue
        for base in unicodedata.normalize("NFKD", char):
            if unicodedata.combining(base):
                continue
            if base.isalpha() or base.isdigit() or base == ".":
                chars.append(base.lower())
            else:
                chars.append(" ")
            mapping.append(index)
    return "".join(chars), mapping


def _fold_key(text: str) -> str:
    folded, _ = _fold_with_map(text)
    return re.sub(r"\s+", " ", folded).strip()


def _phrase_pattern(key: str) -> re.Pattern[str]:
    parts = [re.escape(part) for part in key.split(" ") if part]
    if not parts:
        raise ValueError("empty match phrase")
    body = r"\s+".join(parts)
    return re.compile(rf"(?<![a-z0-9]){body}(?![a-z0-9])")


def _abbrev_pattern(token: str, *, ignore_case: bool) -> re.Pattern[str]:
    letters = [char for char in token if char.isalnum()]
    if len(letters) < 2:
        raise ValueError(f"abbreviation {token!r} is too short")
    body = r"\.?\s?".join(re.escape(char) for char in letters) + r"\.?"
    flags = re.IGNORECASE if ignore_case else 0
    # Do not treat a longer acronym (U.S.A.) as the shorter one (U.S.).
    return re.compile(
        rf"(?<![A-Za-z0-9])(?:{body})(?![A-Za-z0-9])(?!\.\s?[A-Za-z])",
        flags,
    )


def _as_strings(value: object, label: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{label} must be a list of strings")
    return tuple(item.strip() for item in value)


def _abbreviations(value: object, label: str) -> tuple[tuple[str, bool], ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    parsed: list[tuple[str, bool]] = []
    for item in value:
        if isinstance(item, str):
            parsed.append((item.strip(), False))
            continue
        if not isinstance(item, dict) or "text" not in item:
            raise ValueError(f"{label} entries must be strings or {{text, ignore_case}}")
        text = item["text"]
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"{label} text must be a string")
        ignore_case = item.get("ignore_case", False)
        if not isinstance(ignore_case, bool):
            raise ValueError(f"{label} ignore_case must be a boolean")
        parsed.append((text.strip(), ignore_case))
    return tuple(parsed)


def _leader(raw: object, country_id: str) -> Leader:
    if not isinstance(raw, dict):
        raise ValueError(f"leader of {country_id} must be a mapping")
    name = raw.get("name")
    role = raw.get("role")
    verified = raw.get("verified")
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"leader of {country_id} needs a name")
    if not isinstance(role, str) or not role.strip():
        raise ValueError(f"leader {name} needs a role")
    if not isinstance(verified, bool):
        raise ValueError(f"leader {name} needs verified: true or false")
    gdelt = raw.get("gdelt")
    if gdelt is not None and (not isinstance(gdelt, str) or not gdelt.strip()):
        raise ValueError(f"leader {name} has an invalid gdelt token")
    return Leader(
        name=name.strip(),
        role=role.strip(),
        verified=verified,
        country_id=country_id,
        gdelt=gdelt.strip() if isinstance(gdelt, str) else None,
        aliases=_as_strings(raw.get("aliases"), f"{name} aliases"),
    )


def _add_folded(patterns: list[_Pattern], seen: set[tuple[object, ...]], kind: str, entity_id: str, country_id: str | None, text: str) -> None:
    key = _fold_key(text)
    if not key:
        return
    signature = ("folded", kind, country_id, key)
    if signature in seen:
        return
    seen.add(signature)
    patterns.append(_Pattern(_phrase_pattern(key), None, kind, entity_id, country_id))


def _add_abbrev(patterns: list[_Pattern], seen: set[tuple[object, ...]], kind: str, entity_id: str, country_id: str | None, text: str, ignore_case: bool) -> None:
    signature = ("abbrev", kind, country_id, text.upper(), ignore_case)
    if signature in seen:
        return
    seen.add(signature)
    patterns.append(_Pattern(None, _abbrev_pattern(text, ignore_case=ignore_case), kind, entity_id, country_id))


def _build(raw: object) -> EntityIndex:
    if not isinstance(raw, dict):
        raise ValueError("entities.yml must be a mapping")
    regions: dict[str, Region] = {}
    for entry in raw.get("regions", []):
        if not isinstance(entry, dict):
            raise ValueError("region entries must be mappings")
        region = Region(str(entry["id"]), str(entry["display"]), int(entry["order"]))
        if region.id in regions:
            raise ValueError(f"duplicate region {region.id}")
        regions[region.id] = region
    regional = raw.get("regional")
    if not isinstance(regional, dict):
        raise ValueError("regional block is required")
    regional_display = str(regional["display"])
    regional_gdelt = _as_strings(regional.get("gdelt"), "regional gdelt")

    patterns: list[_Pattern] = []
    seen: set[tuple[object, ...]] = set()
    for alias in _as_strings(regional.get("aliases"), "regional aliases"):
        _add_folded(patterns, seen, "la_region", "latin_america", None, alias)

    def consume_country(entry: object, *, foreign: bool) -> Country:
        if not isinstance(entry, dict):
            raise ValueError("country entries must be mappings")
        country_id = entry.get("id")
        display = entry.get("display", country_id if foreign else None)
        if not isinstance(country_id, str) or not country_id.strip():
            raise ValueError("country needs an id")
        if not foreign:
            region_id = entry.get("region")
            market = entry.get("market")
            if not isinstance(region_id, str) or region_id not in regions:
                raise ValueError(f"{country_id} has an unknown region")
            if not isinstance(market, str) or not market.strip():
                raise ValueError(f"{country_id} needs a market")
            if not isinstance(display, str) or not display.strip():
                raise ValueError(f"{country_id} needs a display name")
            order = entry.get("order")
            if not isinstance(order, int):
                raise ValueError(f"{country_id} needs an integer order")
            query_names = _as_strings(entry.get("query_names"), f"{country_id} query_names")
            if not query_names:
                raise ValueError(f"{country_id} needs query_names")
        else:
            region_id = ""
            market = None
            display = country_id
            order = 0
            query_names = ()
        leaders = tuple(_leader(item, country_id) for item in entry.get("leaders", []))
        kind = "foreign_country" if foreign else "la_country"
        leader_kind = "foreign_leader" if foreign else "la_leader"
        for alias in _as_strings(entry.get("aliases"), f"{country_id} aliases"):
            _add_folded(patterns, seen, kind, country_id, None if foreign else country_id, alias)
        for text, ignore_case in _abbreviations(entry.get("abbreviations"), f"{country_id} abbreviations"):
            _add_abbrev(patterns, seen, kind, country_id, None if foreign else country_id, text, ignore_case)
        for leader in leaders:
            for alias in leader.aliases:
                _add_folded(patterns, seen, leader_kind, leader.name, country_id, alias)
        return Country(
            id=country_id,
            display=display.strip() if isinstance(display, str) else country_id,
            region_id=region_id,
            market=market.strip() if isinstance(market, str) else None,
            order=order,
            query_names=query_names,
            leaders=leaders,
        )

    la_countries = tuple(consume_country(entry, foreign=False) for entry in raw.get("latin_america", []))
    foreign_countries = tuple(consume_country(entry, foreign=True) for entry in raw.get("foreign", []))
    ids = [country.id for country in la_countries]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate Latin American country id")
    for entry in raw.get("ir_terms", []):
        if not isinstance(entry, dict):
            raise ValueError("ir_terms entries must be mappings")
        for alias in _as_strings(entry.get("aliases"), "ir alias"):
            _add_folded(patterns, seen, "ir", "ir", None, alias)
        for text, ignore_case in _abbreviations(entry.get("abbreviations"), "ir abbreviations"):
            _add_abbrev(patterns, seen, "ir", "ir", None, text, ignore_case)

    stop_keys = sorted({_fold_key(phrase) for phrase in _as_strings(raw.get("stop_phrases"), "stop_phrases")}, key=len, reverse=True)
    leaders = tuple(leader for country in (*la_countries, *foreign_countries) for leader in country.leaders)
    return EntityIndex(
        regions=regions,
        la_countries=la_countries,
        foreign_countries=foreign_countries,
        leaders=leaders,
        gdelt_terms=_as_strings(raw.get("gdelt_terms"), "gdelt_terms"),
        regional_gdelt=regional_gdelt,
        regional_display=regional_display,
        stop_patterns=tuple(_phrase_pattern(key) for key in stop_keys if key),
        patterns=tuple(patterns),
        country_by_id={country.id: country for country in la_countries},
    )


@lru_cache(maxsize=1)
def load_entities() -> EntityIndex:
    raw = yaml.safe_load(entities_path().read_text(encoding="utf-8"))
    return _build(raw)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def term_pool_for_market(market: str | None) -> list[str]:
    """GDELT OR-terms for one catalogue market.

    ``market=None`` is the international pool: IR vocabulary, foreign leaders,
    and Latin American leader surnames. A regional market additionally hears
    every other Latin American country, but not its own names, so a domestic
    story that only mentions home is not requested.
    """
    index = load_entities()
    terms = list(index.gdelt_terms)
    for country in index.la_countries:
        excluded = market is not None and country.market == market
        if market is not None and not excluded:
            terms.extend(country.query_names)
        if not excluded:
            terms.extend(leader.gdelt for leader in country.leaders if leader.gdelt)
    for country in index.foreign_countries:
        terms.extend(leader.gdelt for leader in country.leaders if leader.gdelt)
    return _dedupe(terms)


def place_terms() -> list[str]:
    """Latin American place names required on international-wire queries."""
    index = load_entities()
    terms: list[str] = []
    for country in index.la_countries:
        terms.extend(country.query_names)
    terms.extend(index.regional_gdelt)
    return _dedupe(terms)


def _resolve_overlaps(hits: list[_Hit]) -> list[_Hit]:
    chosen: list[_Hit] = []
    for hit in sorted(hits, key=lambda item: (-(item.end - item.start), item.start)):
        if any(hit.start < other.end and other.start < hit.end for other in chosen):
            continue
        chosen.append(hit)
    return sorted(chosen, key=lambda item: item.start)


def _match(title: str) -> list[_Hit]:
    index = load_entities()
    masked = _CURRENCY.sub(lambda match: " " * len(match.group(0)), title)
    folded, mapping = _fold_with_map(masked)
    if not mapping:
        return []
    folded_chars = list(folded)
    original_chars = list(masked)
    for pattern in index.stop_patterns:
        for match in pattern.finditer("".join(folded_chars)):
            for index_ in range(match.start(), match.end()):
                folded_chars[index_] = " "
                original_chars[mapping[index_]] = " "
    folded_text = "".join(folded_chars)
    original_text = "".join(original_chars)
    hits: list[_Hit] = []
    for pattern in index.patterns:
        if pattern.folded is not None:
            for match in pattern.folded.finditer(folded_text):
                start = mapping[match.start()]
                end = mapping[match.end() - 1] + 1
                hits.append(_Hit(pattern.kind, pattern.entity_id, pattern.country_id, start, end))
        if pattern.original is not None:
            for match in pattern.original.finditer(original_text):
                hits.append(_Hit(pattern.kind, pattern.entity_id, pattern.country_id, match.start(), match.end()))
    return _resolve_overlaps(hits)


def classify(title: str) -> Classification | None:
    """Tier 1 pairs a Latin American country or leader with a different one.

    Tier 2 is one Latin American entity plus an international-relations term.
    Anything else, including a domestic story, is dropped.
    """
    hits = _match(title)
    if not hits:
        return None
    la_ids: list[str] = []
    has_region = False
    has_foreign = False
    has_ir = False
    for hit in hits:
        if hit.kind in {"la_country", "la_leader"} and hit.country_id:
            if hit.country_id not in la_ids:
                la_ids.append(hit.country_id)
        elif hit.kind == "la_region":
            has_region = True
        elif hit.kind in {"foreign_country", "foreign_leader"}:
            has_foreign = True
        elif hit.kind == "ir":
            has_ir = True
    if not la_ids and not has_region:
        return None
    if len(la_ids) >= 2 or (la_ids or has_region) and has_foreign:
        tier = 1
    elif has_ir:
        tier = 2
    else:
        return None
    index = load_entities()
    if la_ids:
        country = index.country_by_id[la_ids[0]]
        region = index.regions[country.region_id]
        return Classification(
            tier=tier,
            region_id=region.id,
            region_display=region.display,
            region_order=region.order,
            country_id=country.id,
            country_display=country.display,
            country_order=country.order,
        )
    region = index.regions["americas"]
    return Classification(
        tier=tier,
        region_id=region.id,
        region_display=region.display,
        region_order=region.order,
        country_id="latin_america",
        country_display=index.regional_display,
        country_order=0,
    )


def group_headlines(headlines: list[Headline]) -> list[Section]:
    """Region, then country. Tier 1 headlines precede Tier 2 inside a country."""
    grouped: dict[tuple[int, str], dict[tuple[int, str], list[tuple[Classification, Headline]]]] = {}
    region_titles: dict[str, str] = {}
    country_titles: dict[str, str] = {}
    for item in headlines:
        result = classify(item.title)
        if result is None:
            continue
        region_titles[result.region_id] = result.region_display
        country_titles[result.country_id] = result.country_display
        countries = grouped.setdefault((result.region_order, result.region_id), {})
        countries.setdefault((result.country_order, result.country_id), []).append((result, item))
    sections: list[Section] = []
    for (_, region_id), countries in sorted(grouped.items()):
        region_title = region_titles[region_id]
        blocks: list[Block] = []
        for (_, country_id), rows in sorted(countries.items()):
            rows.sort(key=lambda pair: (pair[0].tier, -pair[1].seen_at.timestamp(), pair[1].publisher.casefold(), pair[1].title.casefold()))
            title = country_titles[country_id]
            blocks.append(Block(title="" if title == region_title else title, items=[row[1] for row in rows]))
        sections.append(Section(title=region_title, blocks=blocks))
    return sections
