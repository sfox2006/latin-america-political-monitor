from __future__ import annotations

import html
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode, urljoin

import requests
from bs4 import BeautifulSoup

from .config import Settings
from .models import Headline
from .relations import classify, load_entities, place_terms, term_pool_for_market
from .sources import INTERNATIONAL_PUBLICATIONS, LATIN_AMERICAN_PUBLICATIONS, match_publication, publisher_name
from .window import CoverageWindow

LOGGER = logging.getLogger(__name__)
GDELT_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"

# The DOC API searches machine-translated English and rejects encoded queries
# around 250 characters. Stay under the length the live API accepted.
MAX_ENCODED_QUERY_LENGTH = 240
# Windows shorter than this were rejected ("Timespan is too short") when they
# ended near the present. Further caps are split by boolean query instead.
MIN_QUERY_TIMESPAN = timedelta(minutes=60)
TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid", "igshid", "ref_src"}


def _or_group(values: list[str] | tuple[str, ...], prefix: str = "") -> str:
    terms = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        escaped = value.replace('"', "")
        rendered = f'"{escaped}"' if " " in escaped else escaped
        terms.append(f"{prefix}{rendered}")
    if not terms:
        raise ValueError("Cannot build an empty OR group")
    return "(" + " OR ".join(terms) + ")"


def _encoded_query_length(query: str) -> int:
    encoded = urlencode({"query": query})
    return len(encoded) - len("query=")


def _pack_terms(values: list[str] | tuple[str, ...], companions: list[str], limit: int) -> list[list[str]] | None:
    """Pack values into OR groups that stay within the encoded query limit."""
    batches: list[list[str]] = []
    current: list[str] = []
    for value in values:
        trial = current + [value]
        query = " ".join([_or_group(trial), *companions])
        if _encoded_query_length(query) > limit and current:
            batches.append(current)
            current = [value]
            if _encoded_query_length(" ".join([_or_group(current), *companions])) > limit:
                return None
        elif _encoded_query_length(query) > limit:
            return None
        else:
            current = trial
    if current:
        if _encoded_query_length(" ".join([_or_group(current), *companions])) > limit:
            return None
        batches.append(current)
    return batches


def _term_cost(term: str) -> int:
    return _encoded_query_length(_or_group([term]))


def _sorted_terms(terms: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for term in terms:
        if term and term not in seen:
            seen.add(term)
            unique.append(term)
    return sorted(unique, key=lambda term: (_term_cost(term), term))


def _group_cost(terms: list[str]) -> int:
    return _encoded_query_length(_or_group(terms))


def _pack_by_cost(terms: list[str], budget: int) -> list[list[str]] | None:
    batches: list[list[str]] = []
    current: list[str] = []
    for term in terms:
        trial = current + [term]
        if _group_cost(trial) <= budget:
            current = trial
            continue
        if not current:
            return None
        batches.append(current)
        current = [term]
        if _group_cost(current) > budget:
            return None
    if current:
        batches.append(current)
    return batches


def _pack_terms_for_prefix(prefix: str, terms: list[str], limit: int) -> list[list[str]] | None:
    batches: list[list[str]] = []
    current: list[str] = []
    for term in terms:
        trial = current + [term]
        if _encoded_query_length(f"{prefix} {_or_group(trial)}") <= limit:
            current = trial
            continue
        if not current:
            return None
        batches.append(current)
        current = [term]
        if _encoded_query_length(f"{prefix} {_or_group(current)}") > limit:
            return None
    if current:
        batches.append(current)
    return batches


def _pack_cross(domain_group: str, places: list[str], terms: list[str], limit: int) -> list[str] | None:
    """AND place batches with term batches, choosing the split with the fewest queries.

    A full cartesian product is required so every place is paired with every term.
    The split that minimises that product is the one that fits the workflow clock.
    """
    if not places or not terms or _encoded_query_length(domain_group) >= limit:
        return None
    floor = max(_group_cost([place]) for place in places)
    best: list[str] | None = None
    budget = floor
    while budget < limit:
        place_batches = _pack_by_cost(places, budget)
        if place_batches:
            queries: list[str] = []
            fits = True
            for place_batch in place_batches:
                prefix = f"{domain_group} {_or_group(place_batch)}"
                term_batches = _pack_terms_for_prefix(prefix, terms, limit)
                if not term_batches:
                    fits = False
                    break
                queries.extend(f"{prefix} {_or_group(term_batch)}" for term_batch in term_batches)
            if fits and (best is None or len(queries) < len(best)):
                best = queries
        budget += 12
    if best is not None:
        return best
    queries = []
    for place in places:
        prefix = f"{domain_group} {_or_group([place])}"
        term_batches = _pack_terms_for_prefix(prefix, terms, limit)
        if not term_batches:
            return None
        queries.extend(f"{prefix} {_or_group(term_batch)}" for term_batch in term_batches)
    return queries


def _cover_domains(domains: list[str], dimensions: list[list[str]], batch_size: int, limit: int) -> list[str]:
    """Grow domain batches only while the average query count does not get worse."""
    ordered = sorted(set(domains), key=len)
    queries: list[str] = []
    index = 0
    while index < len(ordered):
        batch = [ordered[index]]
        covered = _cover_batch(batch, dimensions, limit)
        if not covered:
            raise ValueError(f"Query for {batch[0]} cannot fit within the news-index length limit")
        score = len(covered) / len(batch)
        nxt = index + 1
        while nxt < len(ordered) and (nxt - index) < batch_size:
            trial = ordered[index:nxt + 1]
            trial_covered = _cover_batch(trial, dimensions, limit)
            if trial_covered is None:
                break
            trial_score = len(trial_covered) / len(trial)
            if trial_score > score + 1e-9:
                break
            batch = trial
            covered = trial_covered
            score = trial_score
            nxt += 1
        for query in covered:
            if _encoded_query_length(query) > limit:
                raise ValueError("Packed query exceeded the news-index length limit")
        queries.extend(covered)
        index += len(batch)
    return queries


def _cover_batch(domains: list[str], dimensions: list[list[str]], limit: int) -> list[str] | None:
    domain_group = _or_group(domains, "domain:")
    if len(dimensions) == 1:
        batches = _pack_terms(dimensions[0], [domain_group], limit)
        if not batches:
            return None
        return [f"{domain_group} {_or_group(batch)}" for batch in batches]
    if len(dimensions) == 2:
        return _pack_cross(domain_group, dimensions[0], dimensions[1], limit)
    raise ValueError("unsupported query shape")


def build_queries(batch_size: int = 8, max_encoded_length: int = MAX_ENCODED_QUERY_LENGTH) -> list[tuple[str, str]]:
    """Return (query, label) pairs that stay inside the DOC API length limit.

    Regional outlets are ``domain AND (other countries OR foreign/IR terms)``, so a
    story that only mentions the outlet's own country is not requested. International
    wires are ``domain AND Latin American place AND (foreign/IR terms)``. Batch size
    is a ceiling; length and the resulting query count may force smaller batches.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    if max_encoded_length < 1:
        raise ValueError("max_encoded_length must be positive")
    known_markets = {country.market for country in load_entities().countries}
    by_market: dict[str, list[str]] = {}
    # Pan-regional desks have no home country to exclude. The three-clause
    # international shape keeps domestic stories out of the index request.
    pan_regional: list[str] = []
    for publication in LATIN_AMERICAN_PUBLICATIONS:
        if publication.market == "Latin America":
            if publication.domain not in pan_regional:
                pan_regional.append(publication.domain)
            continue
        if publication.market not in known_markets:
            raise ValueError(f"No entities.yml market for {publication.name} ({publication.market})")
        domains = by_market.setdefault(publication.market, [])
        if publication.domain not in domains:
            domains.append(publication.domain)
    queries: list[tuple[str, str]] = []
    for market, domains in by_market.items():
        pool = _sorted_terms(term_pool_for_market(market))
        for query in _cover_domains(domains, [pool], batch_size, max_encoded_length):
            queries.append((query, "Latin American press"))
    international_domains = [publication.domain for publication in INTERNATIONAL_PUBLICATIONS]
    for domain in pan_regional:
        if domain not in international_domains:
            international_domains.append(domain)
    for query in _cover_domains(
        international_domains,
        [_sorted_terms(place_terms()), _sorted_terms(term_pool_for_market(None))],
        batch_size,
        max_encoded_length,
    ):
        queries.append((query, "international press"))
    return queries


def _parse_gdelt_date(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _canonical_url(value: str) -> str:
    parsed = urlparse(value.strip())
    query = urlencode(sorted(
        (key, item) for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_PARAMS
    ))
    return urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower().removeprefix("www."),
        parsed.path,
        parsed.params,
        query,
        "",
    ))


class CollectionError(RuntimeError):
    """Coverage is incomplete; do not publish a successful briefing."""


class RateLimited(Exception):
    """The news index asked the client to slow down."""


def split_capped_window(window: CoverageWindow) -> tuple[CoverageWindow, CoverageWindow] | None:
    """Split a capped window into two covering halves, each at least the API minimum.

    Returns None when the window is already at the minimum duration. Halves overlap
    when that is the only way to keep both of them long enough; the union always
    covers the parent.
    """
    if window.end - window.start <= MIN_QUERY_TIMESPAN:
        return None
    midpoint = window.start + (window.end - window.start) / 2
    midpoint = midpoint.replace(microsecond=0)
    left_end = max(midpoint, window.start + MIN_QUERY_TIMESPAN)
    right_start = min(midpoint, window.end - MIN_QUERY_TIMESPAN)
    left = CoverageWindow(window.start, left_end, window.hours, window.label)
    right = CoverageWindow(right_start, window.end, window.hours, window.label)
    if left.start != window.start or right.end != window.end or left.end < right.start:
        raise CollectionError("Capped-window split would leave a coverage gap")
    if (left.end - left.start) >= (window.end - window.start) or (right.end - right.start) >= (window.end - window.start):
        raise CollectionError("Capped-window split did not shrink the query")
    if (left.end - left.start) < MIN_QUERY_TIMESPAN or (right.end - right.start) < MIN_QUERY_TIMESPAN:
        raise CollectionError("Capped-window split is shorter than the news index allows")
    return left, right


def _top_level_groups(query: str) -> list[str]:
    groups: list[str] = []
    depth = 0
    start: int | None = None
    for index, char in enumerate(query):
        if char == "(":
            if depth == 0:
                start = index
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0 and start is not None:
                groups.append(query[start:index + 1])
                start = None
    return groups


def split_query(query: str) -> tuple[str, str] | None:
    """Split the widest OR group so the union of the halves equals the original query."""
    groups = _top_level_groups(query)
    ranked = sorted(range(len(groups)), key=lambda index: groups[index].count(" OR "), reverse=True)
    for index in ranked:
        inner = groups[index][1:-1]
        parts = [part.strip() for part in inner.split(" OR ") if part.strip()]
        if len(parts) < 2:
            continue
        midpoint = len(parts) // 2
        left_groups = groups.copy()
        right_groups = groups.copy()
        left_groups[index] = "(" + " OR ".join(parts[:midpoint]) + ")"
        right_groups[index] = "(" + " OR ".join(parts[midpoint:]) + ")"
        return " ".join(left_groups), " ".join(right_groups)
    return None


def _articles_from_response(response: requests.Response) -> list[dict]:
    raw_text = getattr(response, "text", "")
    text = raw_text if isinstance(raw_text, str) else ""
    lowered = text.lower()
    if response.status_code == 429 or "limit requests to one every" in lowered:
        raise RateLimited(text[:200] or f"HTTP {response.status_code}")
    if "too short or too long" in lowered:
        raise CollectionError("News query was rejected as too short or too long")
    if "timespan is too short" in lowered:
        raise CollectionError("News index rejected the query duration as too short")
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError as exc:
        raise ValueError("Unexpected news-index response") from exc
    if not isinstance(payload, dict) or (payload and "articles" not in payload):
        raise ValueError("Unexpected news-index response")
    articles = payload.get("articles", [])
    if not isinstance(articles, list):
        raise ValueError("Invalid article list")
    return articles


def _request_json(session: requests.Session, query: str, window: CoverageWindow, settings: Settings) -> list[dict]:
    params = {
        "query": query,
        "mode": "artlist",
        "maxrecords": settings.max_records,
        "format": "json",
        "sort": "datedesc",
        "startdatetime": window.start.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S"),
        "enddatetime": window.end.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S"),
    }
    rate_limits = 0
    other_errors = 0
    last_error: Exception | None = None
    while rate_limits < 6 and other_errors < 3:
        try:
            time.sleep(settings.request_delay)
            response = session.get(GDELT_ENDPOINT, params=params, timeout=settings.request_timeout)
            articles = _articles_from_response(response)
            if len(articles) >= settings.max_records:
                split = split_capped_window(window)
                if split is not None:
                    left, right = split
                    LOGGER.info("Result cap reached; splitting %s to %s at %s", window.start, window.end, left.end)
                    return _request_json(session, query, left, settings) + _request_json(session, query, right, settings)
                parts = split_query(query)
                if parts is not None:
                    LOGGER.info("Result cap reached at minimum duration; splitting the boolean query")
                    return _request_json(session, parts[0], window, settings) + _request_json(session, parts[1], window, settings)
                raise CollectionError("Result cap reached and the query cannot be split further; coverage incomplete")
            return articles
        except CollectionError:
            raise
        except RateLimited as exc:
            rate_limits += 1
            last_error = exc
            try:
                retry_after = float(response.headers.get("Retry-After", "0") or 0)
            except (TypeError, ValueError):
                retry_after = 0
            wait = max(settings.request_delay, retry_after, float(2 ** rate_limits))
            LOGGER.warning("GDELT rate limit reached; waiting %.2f seconds", wait)
            time.sleep(wait)
        except (requests.RequestException, ValueError) as exc:
            other_errors += 1
            last_error = exc
            if other_errors < 3:
                time.sleep(max(settings.request_delay, 2 ** other_errors))
    LOGGER.error("GDELT query failed: %s", last_error)
    raise CollectionError(f"News query failed after retries: {last_error}")


def collect(window: CoverageWindow, settings: Settings) -> list[Headline]:
    session = requests.Session()
    session.headers.update({"User-Agent": settings.user_agent, "Accept": "application/json"})
    # Keyed only by canonical URL. The same event from two publishers must both remain.
    articles: dict[str, Headline] = {}
    queries = build_queries(settings.source_batch_size)
    LOGGER.info("Running %d source/place queries for a %d-hour window", len(queries), window.hours)

    for index, (query, label) in enumerate(queries, 1):
        rows = _request_json(session, query, window, settings)
        LOGGER.info("Query %d/%d (%s): %d results", index, len(queries), label, len(rows))
        for row in rows:
            url = str(row.get("url", "")).strip()
            title = html.unescape(str(row.get("title", "")).strip())
            raw_seen = str(row.get("seendate", "") or "")
            seen_at = _parse_gdelt_date(raw_seen)
            publication = match_publication(str(row.get("domain", "") or urlparse(url).netloc))
            if publication and url and title and raw_seen and seen_at is None:
                raise CollectionError(f"Unparseable index time for {url}")
            if not url or not title or not seen_at or not publication:
                continue
            if not (window.start <= seen_at <= window.end):
                continue
            key = _canonical_url(url)
            articles.setdefault(key, Headline(
                title=re.sub(r"\s+", " ", title),
                publisher=publisher_name(publication, url),
                url=url,
                seen_at=seen_at,
                market=publication.market,
                scope=publication.scope,
                domain=publication.domain,
                language=str(row.get("language", "") or ""),
            ))

    headlines = sorted(articles.values(), key=lambda item: (item.seen_at, item.publisher, item.title), reverse=True)
    if settings.enrich_headlines and headlines:
        _enrich_from_original_pages(headlines, settings)
        headlines = _dedupe_headlines(headlines)
    # The index query is a recall net. The headline, not the article body, decides scope.
    return [item for item in headlines if classify(item.title) is not None]


def _dedupe_headlines(headlines: list[Headline]) -> list[Headline]:
    """Collapse identical canonical URLs after enrichment. Distinct publishers stay."""
    kept: dict[str, Headline] = {}
    for item in headlines:
        kept.setdefault(_canonical_url(item.url), item)
    return sorted(kept.values(), key=lambda item: (item.seen_at, item.publisher, item.title), reverse=True)


def _same_publisher_article(headline: Headline, url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if match_publication(parsed.hostname or "") != match_publication(headline.domain):
        return False
    return parsed.path not in {"", "/"}


def _extract_page_metadata(headline: Headline, settings: Settings) -> tuple[str, str] | None:
    try:
        response = requests.get(headline.url, timeout=(8, settings.request_timeout), headers={"User-Agent": settings.user_agent})
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        title_tag = soup.select_one('meta[property="og:title"]') or soup.select_one('meta[name="twitter:title"]')
        canonical = soup.select_one('link[rel="canonical"]')
        title = title_tag.get("content", "").strip() if title_tag else ""
        url = urljoin(response.url, canonical.get("href", "").strip()) if canonical else response.url
        if not _same_publisher_article(headline, url):
            url = headline.url
        return title or headline.title, url or headline.url
    except requests.RequestException:
        return None


def _enrich_from_original_pages(headlines: list[Headline], settings: Settings) -> None:
    LOGGER.info("Refreshing titles/canonical links from %d original pages", len(headlines))
    with ThreadPoolExecutor(max_workers=settings.enrich_workers) as pool:
        futures = {pool.submit(_extract_page_metadata, item, settings): item for item in headlines}
        for future in as_completed(futures):
            result = future.result()
            if result:
                futures[future].title, futures[future].url = result
