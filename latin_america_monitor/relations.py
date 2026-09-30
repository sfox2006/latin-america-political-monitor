"""Headline filter for Latin American international relations.

Countries, leaders, aliases, and terms live in ``entities.yml``. This module
only matches them. Law-signing phrases are masked before matching. Sports
headlines are dropped after that match. A leader override, a strong term in
``override_ir``, or a diplomatic word keeps the headline.
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
_PERSON_GAP = r"(?:(?!(?:y|e|and|et|con|vs|contra|com|with|del|de)\b)[\w.'-]+\s+){0,2}"
_RANGE_BEFORE = re.compile(r"(?:\ba las|\blas|\bat|\bdesde|\bhasta|\bfrom|\bde|\bdel|\bentre|\bbetween)\s*$")
_BARE_NUMBER = re.compile(r"(?<![\d/.,:-])(\d{1,2})(?![\d/%-]|[.,:]\d)")


def entities_path() -> Path:
    return Path(__file__).with_name("entities.yml")


def gdelt_path() -> Path:
    return Path(__file__).with_name("gdelt.yml")


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
    surface: str


@dataclass(frozen=True)
class _SportsRule:
    enabled: bool
    exceptions: tuple[re.Pattern[str], ...]
    bodies: tuple[re.Pattern[str], ...]
    hard: tuple[re.Pattern[str], ...]
    versus: tuple[re.Pattern[str], ...]
    soft: tuple[re.Pattern[str], ...]
    override: tuple[re.Pattern[str], ...]
    body_excludes: frozenset[str]
    leader_override: bool
    cues: tuple[str, ...]
    weak_post: frozenset[str]
    namesake_starts: bool
    score_enabled: bool
    score_pattern: re.Pattern[str] | None
    score_verbs: tuple[re.Pattern[str], ...]
    score_block: tuple[re.Pattern[str], ...]
    score_units: tuple[re.Pattern[str], ...]
    policy_strong: tuple[re.Pattern[str], ...]
    policy_ambiguous: tuple[re.Pattern[str], ...]
    cue_patterns: tuple[re.Pattern[str], ...]
    team_names: tuple[re.Pattern[str], ...]
    bare_score: bool


@dataclass(frozen=True)
class EntityIndex:
    countries: tuple[Country, ...]
    leaders: tuple[Leader, ...]
    country_by_id: dict[str, Country]
    latam: frozenset[str]
    institutions: frozenset[str]
    masks: tuple[re.Pattern[str], ...]
    aliases: tuple[_Alias, ...]
    regional: tuple[tuple[re.Pattern[str], bool], ...]
    ir_strong: tuple[tuple[str, re.Pattern[str]], ...]
    ir_weak: tuple[tuple[str, re.Pattern[str]], ...]
    sports: _SportsRule
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

    for phrase in (
        _strings(raw.get("global_stoplist_phrases"))
        + _strings(raw.get("out_of_entity_names"))
        + _strings(raw.get("law_signing_stoplist"))
    ):
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
    country_ids = {entry["id"] for entry in foreign["countries"]}
    institutions = {
        (entry.get("group") or entry["id"])
        for entry in foreign["institutions"]
        if (entry.get("group") or entry["id"]) not in country_ids
    }
    blocs = list(raw.get("latam_blocs") or [])
    for entry in blocs:
        latam.add(entry.get("group", entry["id"]))
    for entry in foreign["countries"] + foreign["institutions"] + blocs:
        group = entry.get("group", entry["id"])
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
            add_many(person_aliases, implied, "foreign_leader", set(), person_case)
            if person.get("implies_country") and person_aliases:
                add_alias(person_aliases[0], group, "foreign_leader", False, person_aliases[0] in person_case, None)
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

    def compile_terms(values: object) -> tuple[re.Pattern[str], ...]:
        return tuple(_alias_pattern(term, case_sensitive=False) for term in _strings(values))

    sports_raw = raw.get("sports_rule") or {}
    hard_lists = sports_raw.get("hard") or {}
    versus_lists = sports_raw.get("versus") or {}
    soft_lists = sports_raw.get("soft") or {}
    leader_raw = sports_raw.get("leader_override") or {}
    cues = [_fold(cue, lower=True) for cue in _strings(leader_raw.get("sports_person_cues"))]
    score_raw = sports_raw.get("scoreline") or {}
    policy_raw = sports_raw.get("policy_override") or {}
    seen_teams: set[str] = set()
    team_names: list[re.Pattern[str]] = []

    def add_team(alias: str, weak: set[str]) -> None:
        alias = re.sub(r"\s*\(weak\)$", "", alias)
        if alias in weak:
            return
        key = _fold(alias, lower=True)
        if key in seen_teams:
            return
        seen_teams.add(key)
        team_names.append(_alias_pattern(alias, case_sensitive=False))

    for entry in raw["countries"]:
        weak = set(entry.get("weak_aliases") or [])
        for alias in _strings(entry.get("aliases")) + _strings(entry.get("demonyms")):
            add_team(alias, weak)
    for entry in foreign["countries"]:
        weak = set(entry.get("weak_aliases") or [])
        for alias in _strings(entry.get("aliases")):
            add_team(alias, weak)
    sports = _SportsRule(
        enabled=bool(sports_raw.get("enabled")),
        exceptions=compile_terms(sports_raw.get("exceptions")),
        bodies=compile_terms(sports_raw.get("sports_bodies")),
        hard=compile_terms([term for language in ("es", "pt", "en", "fr", "pageants") for term in hard_lists.get(language, [])]),
        versus=compile_terms([term for language in ("es", "pt", "en", "fr") for term in versus_lists.get(language, [])]),
        soft=compile_terms([term for language in ("es", "pt", "en", "fr") for term in soft_lists.get(language, [])]),
        override=compile_terms(sports_raw.get("override_ir")),
        body_excludes=frozenset(pattern.pattern for pattern in compile_terms(sports_raw.get("body_excludes"))),
        leader_override=bool(leader_raw.get("enabled")),
        cues=tuple(cues),
        weak_post=frozenset(_fold(cue, lower=True) for cue in _strings(leader_raw.get("weak_post_cues"))),
        namesake_starts=bool(leader_raw.get("namesake_starts_sports")),
        score_enabled=bool(score_raw.get("enabled")),
        score_pattern=re.compile(score_raw["pattern"]) if score_raw.get("enabled") else None,
        score_verbs=compile_terms(score_raw.get("result_verbs")),
        score_block=compile_terms(score_raw.get("block_terms")),
        score_units=compile_terms(score_raw.get("unit_after")),
        policy_strong=compile_terms(policy_raw.get("strong")),
        policy_ambiguous=compile_terms(policy_raw.get("ambiguous")),
        cue_patterns=tuple(
            re.compile(r"(?<!\w)" + re.escape(cue).replace(r"\ ", r"\s+") + r"(?!\w)")
            for cue in cues
        ),
        team_names=tuple(team_names),
        bare_score=bool((sports_raw.get("bare_score") or {}).get("enabled")),
    )
    gdelt_raw = yaml.safe_load(gdelt_path().read_text(encoding="utf-8"))
    gdelt = gdelt_raw["gdelt"] if isinstance(gdelt_raw, dict) and "gdelt" in gdelt_raw else gdelt_raw
    return EntityIndex(
        countries=tuple(countries),
        leaders=tuple(leaders),
        country_by_id={country.id: country for country in countries},
        latam=frozenset(latam),
        institutions=frozenset(institutions),
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


def _sports_person(text: str, surface: str, rule: _SportsRule) -> str | None:
    """``pre`` / ``post`` when a cue marks a namesake. ``post_weak`` is not a leader and does not start sports."""
    if not rule.cues or not surface:
        return None
    cue = "(?:" + "|".join(re.escape(item).replace(r"\ ", r"\s+") for item in rule.cues) + ")"
    alias = re.escape(_fold(surface, lower=True)).replace(r"\ ", r"\s+")
    if re.search(rf"(?<!\w){cue}\s+{_PERSON_GAP}{alias}(?!\w)", text):
        return "pre"
    found = re.search(
        rf"(?<!\w){alias}(?!\w)[\s,()-]+(?:(?!(?:y|e|and|et|con|vs|contra|com|with)\b)\w+\s+){{0,2}}({cue})(?!\w)",
        text,
    )
    if not found:
        return None
    return "post_weak" if found.group(1) in rule.weak_post else "post"


def _scoreline(text: str, index: EntityIndex) -> bool:
    """A football result counts as one soft term and is not a date, range, time, unit, or vote."""
    rule = index.sports
    if not rule.score_enabled or rule.score_pattern is None:
        return False
    if any(pattern.search(text) for pattern in rule.score_block):
        return False
    verb = any(pattern.search(text) for pattern in rule.score_verbs)
    names = [alias for alias in index.aliases if alias.kind in {"name", "demonym"}]
    for match in rule.score_pattern.finditer(text):
        separator = match.group(2)
        if separator in {"a", "to"} and match.group(0).count(" ") != 2:
            continue
        following = re.match(r"\s*(\w+)", text[match.end():])
        if following and any(pattern.fullmatch(following.group(1)) for pattern in rule.score_units):
            continue
        if _RANGE_BEFORE.search(text[:match.start()]):
            continue
        if int(match.group(1)) > 19 or int(match.group(3)) > 19:
            continue
        if separator == ":" and not verb:
            continue
        if verb:
            return True
        before = text[:match.start()].rstrip(" :,-(")
        after = text[match.end():].lstrip(" ,)-")
        window = before[-30:]
        for alias in names:
            beside = any(found.end() == len(before) for found in alias.pattern.finditer(window))
            if beside or alias.pattern.match(after):
                return True
    return False


def _policy_hits(text: str, patterns: tuple[re.Pattern[str], ...], body: bool, excludes: frozenset[str]) -> bool:
    blocked = excludes if body else frozenset()
    return any(pattern.search(text) and pattern.pattern not in blocked for pattern in patterns)


def _bare_score(text: str, index: EntityIndex) -> bool:
    """``Brasil 2 Argentina 1``: a dashless score between two country names.

    A strong policy word, or an ambiguous one with no player or coach cue, suppresses it.
    Vote, court, and unit words suppress it too.
    """
    rule = index.sports
    if not rule.bare_score:
        return False
    body = any(pattern.search(text) for pattern in rule.bodies)
    if _policy_hits(text, rule.policy_strong, body, rule.body_excludes):
        return False
    if any(pattern.search(text) for pattern in rule.score_block):
        return False
    cue = any(pattern.search(text) for pattern in rule.cue_patterns)
    if _policy_hits(text, rule.policy_ambiguous, body, rule.body_excludes) and not cue:
        return False
    numbers = [match for match in _BARE_NUMBER.finditer(text) if int(match.group(1)) <= 19]
    for left, right in zip(numbers, numbers[1:]):
        before = text[:left.start()].rstrip(" :,-(")
        middle = text[left.end():right.start()].strip(" ,")
        window = before[-30:]
        if not any(found.end() == len(before) for pattern in rule.team_names for found in pattern.finditer(window)):
            continue
        if not any(pattern.fullmatch(middle) for pattern in rule.team_names):
            continue
        following = re.match(r"\s*(\w+)", text[right.end():])
        if following and any(pattern.fullmatch(following.group(1)) for pattern in rule.score_units):
            continue
        return True
    return False


def _policy_rescue(text: str, signals: int, body: bool, rule: _SportsRule) -> bool:
    """Strong policy words rescue any soft-only sports reading. Ambiguous words rescue one signal and no cue."""
    if _policy_hits(text, rule.policy_strong, body, rule.body_excludes):
        return True
    if signals <= 1 and not any(pattern.search(text) for pattern in rule.cue_patterns):
        return _policy_hits(text, rule.policy_ambiguous, body, rule.body_excludes)
    return False


def _leader_override(headline: str, hits: list[_Hit], index: EntityIndex) -> bool:
    """Keep a sports headline that names two countries' leaders, or a leader and a foreign side.

    A namesake next to a cue (``entrenador``, ``gol de``) does not count as that leader.
    """
    rule = index.sports
    if not rule.leader_override:
        return False
    text = _fold(headline, lower=True)
    leaders = [
        hit for hit in hits
        if not hit.weak and hit.kind in {"leader", "foreign_leader"} and _sports_person(text, hit.surface, rule) is None
    ]
    if len({hit.group for hit in leaders}) >= 2:
        return True
    latam_leaders = {hit.group for hit in leaders if hit.kind == "leader" and hit.group in index.latam}
    if latam_leaders and any(
        not hit.weak and hit.kind in {"foreign", "foreign_leader"} and hit.group not in index.latam
        for hit in hits
    ):
        return True
    if any(hit.kind == "foreign_leader" and hit.group not in index.latam for hit in leaders):
        return any(not hit.weak and hit.group in index.latam for hit in hits)
    return False


def _sports_drop(headline: str, hits: list[_Hit], index: EntityIndex) -> bool:
    """Drop a fixture or pageant unless a soft-only policy rescue, a leader override, or a strong IR term applies.

    Soft terms count once per distinct pattern. A scoreline is one soft term. Hard terms,
    a bare score, and a namesake cue are never rescued by ``policy_override``.
    ``Cumbre Sudamericana`` and the other entries in ``exceptions`` are blanked first.
    """
    rule = index.sports
    if not rule.enabled:
        return False
    text = _fold(headline, lower=True)
    for pattern in rule.exceptions:
        text = pattern.sub(" ", text)
    hard = any(pattern.search(text) for pattern in rule.hard)
    soft_hits = len({pattern.pattern for pattern in rule.soft if pattern.search(text)})
    versus = any(pattern.search(text) for pattern in rule.versus)
    scored = _scoreline(text, index)
    if scored:
        soft_hits += 1
    bare = _bare_score(text, index)
    folded = _fold(headline, lower=True)
    namesake = rule.namesake_starts and any(
        not hit.weak and hit.kind in {"leader", "foreign_leader"} and _sports_person(folded, hit.surface, rule) in {"pre", "post"}
        for hit in hits
    )
    name_only = bool(hits) and all(hit.kind in {"name", "demonym"} for hit in hits)
    groups = {hit.group for hit in hits}
    is_sport = hard or bare or namesake or soft_hits >= 2 or ((versus or scored) and name_only and len(groups) >= 2) or (versus and soft_hits >= 1)
    if not is_sport:
        return False
    body = any(pattern.search(text) for pattern in rule.bodies)
    if not (hard or bare or namesake) and _policy_rescue(text, soft_hits + (1 if versus else 0), body, rule):
        return False
    if _leader_override(headline, hits, index):
        return False
    for pattern in rule.override:
        if pattern.search(text) and not (body and pattern.pattern in rule.body_excludes):
            return False
    return True


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
        _Hit(alias.group, alias.weak, alias.kind, match.start(), match.end(), match.group(0))
        for match in pattern.finditer(text)
    ]


def classify(title: str) -> Classification | None:
    """Tier 1 pairs a Latin American country or leader with a different one.

    Tier 2 is exactly one Latin American country plus a strong international-relations
    term (or two weak terms on a country name). Sports fixtures and domestic
    headlines are dropped.
    """
    if not title or not title.strip():
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
    if tier is None or _sports_drop(title, hits, index):
        return None
    country_hits = [hit for hit in admitted if hit.group in index.country_by_id]
    if country_hits:
        country = index.country_by_id[min(country_hits, key=lambda hit: (hit.start, hit.group)).group]
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
