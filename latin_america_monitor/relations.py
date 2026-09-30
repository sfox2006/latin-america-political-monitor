"""Headline filter for Latin American international relations.

Countries, leaders, aliases, and terms live in ``entities.yml``. This module
only matches them. Behaviour follows that file's tier rules, with two
tightening rules the labelled set does not cover: sports headlines are
dropped, and the legislative verb ``sanciona`` is not a sanctions term.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from .models import Headline

# Enough function words to tell Spanish-press "EU" (Estados Unidos) from English "EU".
_ENGLISH_WORDS = {"the", "of", "to", "and", "in", "for", "with", "on", "that", "its", "threatens", "over", "after", "as", "will", "says"}
_FRENCH_WORDS = {"le", "la", "les", "des", "du", "est", "pour", "avec", "sur"}
_PORTUGUESE_WORDS = {"não", "nao", "do", "da", "dos", "das", "para", "com", "uma", "é", "está", "pelo", "pela", "sobre", "brasil", "chanceler", "foi"}
_SPANISH_WORDS = {"el", "los", "las", "del", "por", "una"}
_CURRENCY = re.compile(r"(?<!\w)(?:US|U\.S\.)\s?\$|(?<!\w)USD(?!\w)", re.IGNORECASE)


def entities_path() -> Path:
    return Path(__file__).with_name("entities.yml")


@dataclass(frozen=True)
class Leader:
    name: str
    role: str
    status: str
    since_verified: bool | None
    country_id: str
    aliases: tuple[str, ...]

    @property
    def verified(self) -> bool:
        return self.status == "VERIFIED"


@dataclass(frozen=True)
class Country:
    id: str
    display: str
    region_display: str
    region_order: int
    market: str
    order: int
    english_name: str


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
class _Alias:
    pattern: re.Pattern[str]
    group: str
    weak: bool
    kind: str
    languages: frozenset[str] | None
    case_sensitive: bool


@dataclass(frozen=True)
class _Hit:
    group: str
    weak: bool
    kind: str
    start: int
    end: int


@dataclass(frozen=True)
class EntityIndex:
    countries: tuple[Country, ...]
    leaders: tuple[Leader, ...]
    country_by_id: dict[str, Country]
    latam: frozenset[str]
    masks: tuple[re.Pattern[str], ...]
    aliases: tuple[_Alias, ...]
    regional: tuple[tuple[re.Pattern[str], bool], ...]
    ir_strong: tuple[tuple[str, re.Pattern[str]], ...]
    ir_weak: tuple[tuple[str, re.Pattern[str]], ...]
    sports: tuple[re.Pattern[str], ...]
    not_ir_tokens: frozenset[str]
    gdelt_terms: tuple[str, ...]
    gdelt_leaders: dict[str, tuple[str, ...]]
    gdelt_regional: tuple[str, ...]
    regional_display: str


def _fold(text: str, *, lower: bool) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return text.casefold() if lower else text


def _alias_pattern(alias: str, *, case_sensitive: bool) -> re.Pattern[str]:
    folded = _fold(alias, lower=not case_sensitive)
    trailing_wild = folded.endswith("*")
    folded = folded.rstrip("*")
    body = re.escape(folded).replace(r"\ ", r"\s+").replace(r"\*", r"\w*")
    body = body.replace(r"\(", "(").replace(r"\)", ")").replace(r"\|", "|").replace(r"\?", "?")
    tail = r"\w*" if trailing_wild else r"(?!\w)"
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.compile(rf"(?<!\w){body}{tail}", flags)


def _strings(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        items: list[str] = []
        for entry in value.values():
            items.extend(_strings(entry))
        return items
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item.strip()]
    return []


def _language(headline: str) -> str:
    words = set(re.findall(r"\w+", headline.lower()))
    if len(words & _ENGLISH_WORDS) >= 2:
        return "en"
    if len(words & _FRENCH_WORDS) >= 2:
        return "fr"
    if len(words & _PORTUGUESE_WORDS) >= 2 and not (words & _SPANISH_WORDS):
        return "pt"
    return "es"


def _mostly_uppercase(headline: str) -> bool:
    letters = [char for char in headline if char.isalpha()]
    if not letters:
        return False
    return sum(char.isupper() for char in letters) / len(letters) > 0.70


def _build(raw: dict) -> EntityIndex:
    region_order = {name: index + 1 for index, name in enumerate(raw["regions"])}
    country_order = {code: index for name, codes in raw["regions"].items() for index, code in enumerate(codes)}
    countries: list[Country] = []
    latam: set[str] = set()
    masks: list[tuple[int, re.Pattern[str]]] = []
    aliases: list[_Alias] = []
    leaders: list[Leader] = []

    def add_mask(phrase: str) -> None:
        masks.append((len(_fold(phrase, lower=True)), _alias_pattern(phrase, case_sensitive=False)))

    for phrase in _strings(raw.get("global_stoplist_phrases")) + _strings(raw.get("out_of_entity_names")):
        add_mask(phrase)

    def add_alias(alias: str, group: str, kind: str, weak: bool, case_sensitive: bool, languages: frozenset[str] | None) -> None:
        aliases.append(_Alias(_alias_pattern(alias, case_sensitive=case_sensitive), group, weak, kind, languages, case_sensitive))

    def add_many(values: object, group: str, kind: str, weak_set: set[str], case_set: set[str], languages: dict | None = None) -> None:
        for alias in _strings(values):
            alias = re.sub(r"\s*\(weak\)$", "", alias)
            only = None
            if languages and alias in languages:
                only = frozenset(languages[alias])
            add_alias(alias, group, kind, alias in weak_set, alias in case_set, only)

    for entry in raw["countries"]:
        code = entry["code"]
        latam.add(code)
        region = entry["region"]
        english = entry["aliases"]["en"][0]
        countries.append(Country(
            id=code,
            display=entry["name"].upper(),
            region_display=region.upper(),
            region_order=region_order[region],
            market=english,
            order=country_order[code],
            english_name=english,
        ))
        for phrase in entry.get("stoplist_phrases") or []:
            add_mask(phrase)
        weak = set(entry.get("weak_aliases") or [])
        case_set = set(entry.get("case_sensitive_aliases") or [])
        add_many(entry.get("aliases"), code, "name", weak, case_set)
        add_many(entry.get("demonyms"), code, "demonym", weak, case_set)
        add_many(entry.get("metonyms"), code, "metonym", weak, case_set)

    for code, roles in raw["leaders"].items():
        for role, people in roles.items():
            for person in people or []:
                since = person.get("since_verified")
                leaders.append(Leader(
                    name=person["name"],
                    role=person.get("title") or role,
                    status=person.get("status") or "UNVERIFIED",
                    since_verified=since if isinstance(since, bool) else None,
                    country_id=code,
                    aliases=tuple(_strings(person.get("aliases")) + _strings(person.get("weak_aliases"))),
                ))
                if person.get("status") == "UNVERIFIED":
                    continue
                weak = set(person.get("weak_aliases") or [])
                case_set = set(person.get("case_sensitive_aliases") or [])
                add_many(_strings(person.get("aliases")) + list(weak), code, "leader", weak, case_set)

    foreign = raw["foreign_entities"]
    for entry in foreign["countries"] + foreign["institutions"]:
        group = entry.get("group") or entry["id"]
        for phrase in entry.get("stoplist_phrases") or []:
            add_mask(phrase)
        weak = set(entry.get("weak_aliases") or [])
        case_set = set(entry.get("case_sensitive_aliases") or [])
        add_many(entry.get("aliases"), group, "foreign", weak, case_set, entry.get("lang_only_aliases"))
        for person in entry.get("people") or []:
            if person.get("status") == "UNVERIFIED":
                continue
            implied = person.get("implies_country") or group
            person_case = set(person.get("case_sensitive_aliases") or [])
            person_aliases = _strings(person.get("aliases"))
            add_many(person_aliases, implied, "foreign", set(), person_case)
            if person.get("implies_country") and person_aliases:
                add_alias(person_aliases[0], group, "foreign", False, person_aliases[0] in person_case, None)
            leaders.append(Leader(
                name=person["name"],
                role=person.get("title") or entry["id"],
                status=person.get("status") or "UNVERIFIED",
                since_verified=person.get("since_verified") if isinstance(person.get("since_verified"), bool) else None,
                country_id=implied,
                aliases=tuple(person_aliases),
            ))
        if entry["id"] == "USMCA":
            for alias in _strings(entry.get("aliases")):
                for extra in ("MX", "US", "CA"):
                    add_alias(alias, extra, "foreign", False, True, None)

    for dispute in raw["disputes"]:
        for term in dispute["terms"]:
            for group in dispute["implies"]:
                add_alias(term, group, "dispute", bool(dispute["weak"]), False, None)

    regional_case = set(raw["regional_terms"].get("case_sensitive") or [])
    regional: list[tuple[re.Pattern[str], bool]] = []
    for language in ("es", "pt", "en", "fr"):
        for alias in raw["regional_terms"][language]:
            sensitive = alias in regional_case
            regional.append((_alias_pattern(alias, case_sensitive=sensitive), sensitive))

    ir_strong: list[tuple[str, re.Pattern[str]]] = []
    ir_weak: list[tuple[str, re.Pattern[str]]] = []
    for language in ("es", "pt", "en", "fr"):
        terms = raw["ir_terms"][language]
        ir_strong.extend((term, _alias_pattern(term, case_sensitive=False)) for term in terms["strong"])
        ir_weak.extend((term, _alias_pattern(term, case_sensitive=False)) for term in terms["weak"])

    sports = tuple(
        _alias_pattern(term, case_sensitive=False)
        for language in raw["out_of_scope_hint_terms"].values()
        for term in language
    )
    gdelt = raw["gdelt"]
    return EntityIndex(
        countries=tuple(countries),
        leaders=tuple(leaders),
        country_by_id={country.id: country for country in countries},
        latam=frozenset(latam),
        masks=tuple(pattern for _, pattern in sorted(masks, key=lambda item: -item[0])),
        aliases=tuple(aliases),
        regional=tuple(regional),
        ir_strong=tuple(ir_strong),
        ir_weak=tuple(ir_weak),
        sports=sports,
        not_ir_tokens=frozenset(_fold(token, lower=True) for token in gdelt.get("not_ir_tokens", [])),
        gdelt_terms=tuple(gdelt["terms"]),
        gdelt_leaders={code: tuple(tokens) for code, tokens in gdelt["leaders"].items()},
        gdelt_regional=tuple(gdelt["regional"]),
        regional_display="AMÉRICA LATINA",
    )


@lru_cache(maxsize=1)
def load_entities() -> EntityIndex:
    raw = yaml.safe_load(entities_path().read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("entities.yml must be a mapping")
    return _build(raw)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


def term_pool_for_market(market: str | None) -> list[str]:
    """GDELT terms for one catalogue market.

    ``None`` is the international pool (IR vocabulary and leader tokens).
    A country market also hears every other Latin American country, but not
    its own name or leaders.
    """
    index = load_entities()
    home = next((country.id for country in index.countries if market and country.market == market), None)
    terms = list(index.gdelt_terms)
    if market is not None:
        for country in index.countries:
            if country.id == home:
                continue
            terms.append(country.english_name)
            terms.extend(index.gdelt_leaders.get(country.id, ()))
    for code, tokens in index.gdelt_leaders.items():
        if code in index.latam and market is not None:
            continue
        if code == home:
            continue
        terms.extend(tokens)
    return _dedupe(terms)


def place_terms() -> list[str]:
    """Latin American place names required on international-wire queries."""
    index = load_entities()
    return _dedupe([country.english_name for country in index.countries] + list(index.gdelt_regional))


def _blank_currency(headline: str) -> str:
    return _CURRENCY.sub(lambda match: " " * len(match.group(0)), headline)


def _sports(headline: str) -> bool:
    folded = _fold(headline, lower=True)
    return any(pattern.search(folded) for pattern in load_entities().sports)


def _resolve(hits: list[_Hit]) -> list[_Hit]:
    """Keep the longest span when two aliases overlap, so a longer official name wins."""
    kept: list[_Hit] = []
    for hit in sorted(hits, key=lambda item: (-(item.end - item.start), item.start, item.group)):
        shorter = (hit.end - hit.start)
        if any(hit.start < other.end and other.start < hit.end and shorter < (other.end - other.start) for other in kept):
            continue
        kept.append(hit)
    return kept


def _search_alias(alias: _Alias, text: str, language: str, uppercase: bool) -> list[_Hit]:
    if alias.languages and language not in alias.languages:
        return []
    pattern = alias.pattern
    if alias.case_sensitive and uppercase:
        pattern = re.compile(pattern.pattern, pattern.flags | re.IGNORECASE)
    return [
        _Hit(alias.group, alias.weak, alias.kind, match.start(), match.end())
        for match in pattern.finditer(text)
    ]


def classify(title: str) -> Classification | None:
    """Tier 1 pairs a Latin American country or leader with a different one.

    Tier 2 is exactly one Latin American country plus a strong international-relations
    term (or two weak terms on a country name). Sports fixtures and domestic
    headlines are dropped.
    """
    if not title or not title.strip() or _sports(title):
        return None
    index = load_entities()
    language = _language(title)
    uppercase = _mostly_uppercase(title)
    text = _fold(_blank_currency(title), lower=False)
    for pattern in index.masks:
        text = pattern.sub(lambda match: " " * len(match.group(0)), text)
    hits = _resolve([
        hit
        for alias in index.aliases
        for hit in _search_alias(alias, text, language, uppercase)
    ])
    strong_groups = {hit.group for hit in hits if not hit.weak}
    admitted = [hit for hit in hits if not hit.weak or (strong_groups - {hit.group})]
    groups = {hit.group for hit in admitted}
    latam = {group for group in groups if group in index.latam}
    other = groups - latam
    folded = _fold(text, lower=True)
    strong_ir = []
    for term, pattern in index.ir_strong:
        if any(_fold(match.group(0), lower=True) not in index.not_ir_tokens for match in pattern.finditer(folded)):
            strong_ir.append(term)
    weak_surfaces: set[str] = set()
    for _, pattern in index.ir_weak:
        weak_surfaces.update(_fold(match.group(0), lower=True) for match in pattern.finditer(folded))
    regional = any(
        (re.compile(pattern.pattern, pattern.flags | re.IGNORECASE) if uppercase and sensitive else pattern).search(text)
        for pattern, sensitive in index.regional
    )
    tier: int | None = None
    if latam == {"PR"} and other and other <= {"US"}:
        tier = 2 if strong_ir else None
    elif latam and (other or len(latam) >= 2):
        tier = 1
    elif regional and other and not latam:
        tier = 1
    elif len(latam) == 1 and not other:
        named = any(hit.kind == "name" and not hit.weak and hit.group in latam for hit in admitted)
        if strong_ir or (named and len(weak_surfaces) >= 2):
            tier = 2
    if tier is None:
        return None
    latam_hits = [hit for hit in admitted if hit.group in index.latam]
    if latam_hits:
        country = index.country_by_id[min(latam_hits, key=lambda hit: (hit.start, hit.group)).group]
        return Classification(
            tier=tier,
            region_id=country.region_display,
            region_display=country.region_display,
            region_order=country.region_order,
            country_id=country.id,
            country_display=country.display,
            country_order=country.order,
        )
    return Classification(
        tier=tier,
        region_id="latin_america",
        region_display=index.regional_display,
        region_order=0,
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
