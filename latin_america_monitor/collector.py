from __future__ import annotations

import html
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse

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
    for batch in _chunks(LATIN_AMERICAN_PUBLICATIONS, batch_size):
        domains = _or_group([p.domain for p in batch], "domain:")
        queries.append((f"{domains} {politics}", "Latin American press"))

    # International coverage is split by both publisher and place to avoid API result truncation.
    place_groups = list(_chunks(LATIN_AMERICA_PLACES, 7))
    for batch in _chunks(INTERNATIONAL_PUBLICATIONS, batch_size):
        domains = _or_group([p.domain for p in batch], "domain:")
        for places in place_groups:
            queries.append((f"{domains} {_or_group(places)} {politics}", "international press"))
    return queries


def _parse_gdelt_date(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _canonical_url(value: str) -> str:
    parsed = urlparse(value.strip())
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower().removeprefix("www."), parsed.path.rstrip("/"), "", "", ""))


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
            response = session.get(GDELT_ENDPOINT, params=params, timeout=settings.request_timeout)
            if response.status_code == 429:
                wait = max(settings.request_delay, float(response.headers.get("Retry-After", "0") or 0))
                LOGGER.warning("GDELT rate limit reached; waiting %.2f seconds", wait)
                time.sleep(wait)
                continue
            response.raise_for_status()
            payload = response.json()
            articles = payload.get("articles", [])
            if len(articles) >= settings.max_records:
                LOGGER.warning("Query reached the %d-result API cap and may be incomplete", settings.max_records)
            return articles
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(max(settings.request_delay, 2 ** attempt))
    LOGGER.error("GDELT query failed after 3 attempts: %s", last_error)
    return []


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
            published = _parse_gdelt_date(row.get("seendate", ""))
            publication = match_publication(row.get("domain", "") or urlparse(url).netloc)
            if not url or not title or not published or not publication:
                continue
            if not (window.start <= published <= window.end):
                continue
            key = _canonical_url(url)
            articles.setdefault(key, Headline(
                title=re.sub(r"\s+", " ", title),
                publisher=publication.name,
                url=url,
                published=published,
                market=publication.market,
                scope=publication.scope,
                domain=publication.domain,
                language=row.get("language", ""),
            ))
        time.sleep(settings.request_delay)

    headlines = sorted(articles.values(), key=lambda item: (item.published, item.publisher, item.title), reverse=True)
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
        url = canonical.get("href", "").strip() if canonical else response.url
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
