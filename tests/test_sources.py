import re
from pathlib import Path

from latin_america_monitor.collector import (
    MAX_ENCODED_QUERY_LENGTH,
    _encoded_query_length,
    _top_level_groups,
    build_queries,
)
from latin_america_monitor.relations import place_terms, term_pool_for_market
from latin_america_monitor.sources import (
    INTERNATIONAL_PUBLICATIONS,
    LATIN_AMERICAN_PUBLICATIONS,
    PUBLICATIONS,
    match_publication,
    publisher_name,
)


def _terms(group: str) -> list[str]:
    return [part.strip().strip('"') for part in group[1:-1].split(" OR ") if part.strip()]


def test_source_catalogue_is_broad():
    assert len(PUBLICATIONS) == 145
    assert len(LATIN_AMERICAN_PUBLICATIONS) == 112
    assert len(INTERNATIONAL_PUBLICATIONS) == 33
    assert len({publication.market for publication in LATIN_AMERICAN_PUBLICATIONS}) == 22
    assert len({publication.domain for publication in PUBLICATIONS}) == len(PUBLICATIONS)
    domains = {publication.domain for publication in PUBLICATIONS}
    assert "mppre.gob.ve" not in domains
    assert "albertonews.com" not in domains
    assert "reutersconnect.com" not in domains


def test_matches_subdomains():
    publication = match_publication("politica.elpais.com.uy")
    assert publication is not None
    assert publication.name == "El País"
    assert publication.market == "Uruguay"


def test_matches_g1_including_www():
    publication = match_publication("g1.globo.com")
    assert publication is not None
    assert publication.name == "G1"
    assert publication.domain == "g1.globo.com"
    assert publication.market == "Brazil"
    assert publication.scope == "latin_america"
    www = match_publication("www.g1.globo.com")
    assert www is not None
    assert www.name == "G1"
    assert match_publication("oglobo.globo.com").name == "O Globo"
    assert match_publication("valor.globo.com").name == "Valor Econômico"


def test_added_outlets_match_on_their_own_domains():
    assert match_publication("cnnespanol.cnn.com").name == "CNN Español"
    assert match_publication("edition.cnn.com").name == "CNN"
    assert match_publication("www.elnuevoherald.com").name == "El Nuevo Herald"
    assert match_publication("elheraldo.co").name == "El Heraldo (Colombia)"
    assert match_publication("elheraldo.co").market == "Colombia"
    assert match_publication("www.elheraldo.hn").name == "El Heraldo"
    assert match_publication("www.elheraldo.hn").market == "Honduras"
    assert match_publication("folha.uol.com.br").name == "Folha de S.Paulo"
    assert match_publication("economia.uol.com.br").name == "UOL"
    assert match_publication("www.afp.com").name == "AFP"
    assert match_publication("en.mercopress.com").name == "MercoPress"
    assert match_publication("mppre.gob.ve") is None
    assert match_publication("dialogo-americas.com").name == "Diálogo Américas"
    assert match_publication("derechadiario.com.ar").name == "La Derecha Diario"
    assert match_publication("revistafactum.com").name == "Revista Factum"
    assert match_publication("republica.com").name == "República GT"
    bbc = match_publication("www.bbc.com")
    assert bbc is not None and bbc.name == "BBC News"
    assert publisher_name(bbc, "https://www.bbc.com/mundo/articles/abc") == "BBC Mundo"
    assert publisher_name(bbc, "https://www.bbc.com/news/world") == "BBC News"


def test_queries_cover_both_scopes():
    queries = build_queries(8)
    labels = {label for _, label in queries}
    assert labels == {"Latin American press", "international press"}
    assert any("domain:reuters.com" in query for query, _ in queries)
    assert any("domain:clarin.com" in query for query, _ in queries)


def test_queries_fit_the_index_limit_and_cover_every_domain():
    queries = build_queries()
    # 5.1s is the delay floor. Base queries stay under 80 minutes so cap-splits
    # and retries can still finish inside the 150-minute workflow.
    assert 1 <= len(queries) <= 750
    assert len(queries) * 5.1 < 80 * 60
    assert all(_encoded_query_length(query) <= MAX_ENCODED_QUERY_LENGTH for query, _ in queries)
    blob = "\n".join(query for query, _ in queries)
    for publication in PUBLICATIONS:
        assert re.search(rf"domain:{re.escape(publication.domain)}(?:\)|\s)", blob)

    la_terms: dict[str, set[str]] = {}
    intl_places: dict[str, set[str]] = {}
    intl_terms: dict[str, set[str]] = {}
    for query, label in queries:
        groups = _top_level_groups(query)
        domains = [term.removeprefix("domain:") for term in _terms(groups[0])]
        if label == "international press":
            assert len(groups) == 3
            for domain in domains:
                intl_places.setdefault(domain, set()).update(_terms(groups[1]))
                intl_terms.setdefault(domain, set()).update(_terms(groups[2]))
        else:
            assert len(groups) == 2
            for domain in domains:
                la_terms.setdefault(domain, set()).update(_terms(groups[1]))

    places = set(place_terms())
    international_terms = set(term_pool_for_market(None))
    pan_regional = [publication for publication in LATIN_AMERICAN_PUBLICATIONS if publication.market == "Latin America"]
    country_press = [publication for publication in LATIN_AMERICAN_PUBLICATIONS if publication.market != "Latin America"]
    for publication in INTERNATIONAL_PUBLICATIONS + pan_regional:
        assert intl_places[publication.domain] == places
        assert intl_terms[publication.domain] == international_terms
        assert "sanctions" in intl_terms[publication.domain]
        assert "United States" in intl_terms[publication.domain]
    for publication in country_press:
        assert la_terms[publication.domain] == set(term_pool_for_market(publication.market))

    # A domestic story that only names the outlet's own country is not requested.
    assert "Argentina" not in la_terms["clarin.com"]
    assert "Milei" not in la_terms["clarin.com"]
    assert "Brazil" in la_terms["clarin.com"] or "Brasil" in la_terms["clarin.com"]
    assert "Lula" in la_terms["clarin.com"]
    assert "Argentina" in intl_places["reuters.com"]
    assert "Milei" in intl_terms["reuters.com"]


def test_weekday_workflow_runs_monday_through_friday():
    workflow = Path(".github/workflows/weekday-monitor.yml").read_text(encoding="utf-8")
    assert 'cron: "0 11 * * 1-5"' in workflow
    assert "timeout-minutes: 150" in workflow
    assert "python main.py --scheduled" in workflow
