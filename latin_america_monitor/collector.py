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
from .models import Headline, Publication
from .sources import INTERNATIONAL_PUBLICATIONS, LATIN_AMERICAN_PUBLICATIONS, match_publication
from .window import CoverageWindow

LOGGER = logging.getLogger(__name__)
GDELT_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"

POLITICAL_TERMS = (
    "politics", "political", "government", "congress", "senate", "president", "minister",
    "election", "parliament", "democracy", "diplomatic", "sanctions", "política", "gobierno",
    "congreso", "elección", "elecciones", "presidente", "ministro", "asamblea", "governo",
    "congresso", "eleição", "eleições", "presidente", "ministro", "democracia",
)

LATIN_AMERICA_PLACES = (
    "Latin America", "South America", "Central America", "Argentina", "Bolivia", "Brazil", "Brasil",
    "Chile", "Colombia", "Costa Rica", "Cuba", "Dominican Republic", "Ecuador", "El Salvador",
    "Guatemala", "Haiti", "Honduras", "Mexico", "México", "Nicaragua", "Panama", "Panamá",
    "Paraguay", "Peru", "Perú", "Puerto Rico", "Uruguay", "Venezuela",
)


def _chunks(values: list[Publication] | tuple[str, ...], size: int):
    for index in range(0, len(values), size):
        yield values[index:index + size]


def _or_group(values: list[str] | tuple[str, ...], prefix: str = "") -> str:
    terms = []
    for value in values:
        escaped = value.replace('"', "")
        rendered = f'"{escaped}"' if " " in escaped else escaped
        terms.append(f"{prefix}{rendered}")
    return "(" + " OR ".join(terms) + ")"


def build_queries(batch_size: int = 8) -> list[tuple[str, str]]:
    """Return (query, label) pairs for local and international publications."""
    politics = _or_group(POLITICAL_TERMS)
    queries: list[tuple[str, str]] = []
    # Both groups must mention the region; a publisher's location is not article relevance.
    place_groups = list(_chunks(LATIN_AMERICA_PLACES, 7))
    for publications, label in ((LATIN_AMERICAN_PUBLICATIONS, "Latin American press"), (INTERNATIONAL_PUBLICATIONS, "international press")):
        for batch in _chunks(publications, batch_size):
            domains = _or_group([p.domain for p in batch], "domain:")
            for places in place_groups:
                queries.append((f"{domains} {_or_group(places)} {politics}", label))
    return queries


def _parse_gdelt_date(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _canonical_url(value: str) -> str:
    parsed = urlparse(value.strip())
    query = urlencode([(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
                       if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}])
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower().removeprefix("www."), parsed.path, parsed.params, query, ""))


class CollectionError(RuntimeError):
    """Coverage is incomplete; do not publish a successful briefing."""


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
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            time.sleep(settings.request_delay)
            response = session.get(GDELT_ENDPOINT, params=params, timeout=settings.request_timeout)
            if response.status_code == 429:
                wait = max(settings.request_delay, float(response.headers.get("Retry-After", "0") or 0))
                LOGGER.warning("GDELT rate limit reached; waiting %.2f seconds", wait)
                last_error = CollectionError("HTTP 429: news index rate limited")
                time.sleep(wait)
                continue
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or (payload and "articles" not in payload):
                raise ValueError("Unexpected news-index response")
            articles = payload.get("articles", [])
            if not isinstance(articles, list):
                raise ValueError("Invalid article list")
            if len(articles) >= settings.max_records:
                if window.end - window.start <= timedelta(minutes=15):
                    raise CollectionError("Result cap reached at minimum 15-minute window; coverage incomplete")
                midpoint = window.start + (window.end - window.start) / 2
                midpoint = midpoint.replace(microsecond=0)
                left = CoverageWindow(window.start, midpoint, window.hours, window.label)
                right = CoverageWindow(midpoint, window.end, window.hours, window.label)
                return _request_json(session, query, left, settings) + _request_json(session, query, right, settings)
            return articles
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(max(settings.request_delay, 2 ** attempt))
    LOGGER.error("GDELT query failed after 3 attempts: %s", last_error)
    raise CollectionError(f"News query failed after 3 attempts: {last_error}")


def collect(window: CoverageWindow, settings: Settings) -> list[Headline]:
    session = requests.Session()
    session.headers.update({"User-Agent": settings.user_agent, "Accept": "application/json"})
    articles: dict[str, Headline] = {}
    queries = build_queries(settings.source_batch_size)
    LOGGER.info("Running %d source/place queries for a %d-hour window", len(queries), window.hours)

    for index, (query, label) in enumerate(queries, 1):
        rows = _request_json(session, query, window, settings)
        LOGGER.info("Query %d/%d (%s): %d results", index, len(queries), label, len(rows))
        for row in rows:
            url = row.get("url", "").strip()
            title = html.unescape(row.get("title", "").strip())
            seen_at = _parse_gdelt_date(row.get("seendate", ""))
            publication = match_publication(row.get("domain", "") or urlparse(url).netloc)
            if not url or not title or not seen_at or not publication:
                continue
            if not (window.start <= seen_at <= window.end):
                continue
            key = _canonical_url(url)
            articles.setdefault(key, Headline(
                title=re.sub(r"\s+", " ", title),
                publisher=publication.name,
                url=url,
                seen_at=seen_at,
                market=publication.market,
                scope=publication.scope,
                domain=publication.domain,
                language=row.get("language", ""),
            ))

    headlines = sorted(articles.values(), key=lambda item: (item.seen_at, item.publisher, item.title), reverse=True)
    if settings.enrich_headlines and headlines:
        _enrich_from_original_pages(headlines, settings)
    return headlines


def _extract_page_metadata(headline: Headline, settings: Settings) -> tuple[str, str] | None:
    try:
        response = requests.get(headline.url, timeout=(8, settings.request_timeout), headers={"User-Agent": settings.user_agent})
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        title_tag = soup.select_one('meta[property="og:title"]') or soup.select_one('meta[name="twitter:title"]')
        canonical = soup.select_one('link[rel="canonical"]')
        title = title_tag.get("content", "").strip() if title_tag else ""
        url = urljoin(response.url, canonical.get("href", "").strip()) if canonical else response.url
        if urlparse(url).scheme not in {"http", "https"} or match_publication(urlparse(url).hostname or "") != match_publication(headline.domain):
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
