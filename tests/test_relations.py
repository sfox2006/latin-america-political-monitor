from datetime import datetime, timedelta, timezone

from pathlib import Path

import pytest
import yaml

from latin_america_monitor.relations import classify, load_entities

_HEADLINES = yaml.safe_load(Path("tests/fixtures/test_headlines.yml").read_text(encoding="utf-8"))


def test_exemplar_headlines_match_the_international_relations_filter():
    matched = {
        "Brasil llama a consultas a su embajador en Argentina tras el 'convicto' de Milei a Lula": (1, "BR"),
        "EE.UU. cancela visas a ciudadanos de Ecuador, Bolivia, Colombia y Peru": (1, "EC"),
        "Kast y el Escudo de las Americas de Trump": (1, "CL"),
        "Nicaragua responde a la UE": (1, "NI"),
        "Colombia apela al FMI": (1, "CO"),
    }
    for headline, (tier, country) in matched.items():
        result = classify(headline)
        assert result is not None, headline
        assert result.tier == tier, headline
        assert result.country_id == country, headline


def test_domestic_exemplar_headlines_are_dropped():
    for headline in (
        "Keiko Fujimori aprueba alza del salario minimo",
        "Aniversario de Tegucigalpa bajo el azote criminal",
        "Caudal de Coca Codo Sinclair",
        "La megacarcel de Abelardo",
    ):
        assert classify(headline) is None, headline


def test_accent_and_case_variants_match():
    lower = classify("ee.uu. cancela visas a ciudadanos de ecuador, bolivia, colombia y perú")
    upper = classify("NICARAGUA RESPONDE A LA UE")
    phrase = classify("Nicaragua responde a la UE")
    mixed = classify("MÉXICO y CHINA firman un tratado")
    assert lower is not None and lower.tier == 1 and lower.country_id == "EC"
    assert upper is not None and upper.tier == 1
    assert phrase is not None and phrase.tier == 1 and phrase.country_id == "NI"
    assert mixed is not None and mixed.tier == 1 and mixed.country_id == "MX"
    # Spanish-press "EU" is the United States. English "EU" is the European Union.
    # Lowercase "ue" is not an abbreviation.
    spanish_eu = classify("EU investiga a Andy López Beltrán por crimen organizado")
    english_eu = classify("Mexico and the EU sign a treaty")
    assert spanish_eu is not None and spanish_eu.tier == 1 and spanish_eu.country_id == "MX"
    assert english_eu is not None and english_eu.tier == 1 and english_eu.country_id == "MX"
    assert classify("nicaragua responde a la ue") is None


def test_portuguese_and_french_headlines_match():
    portuguese = classify("Brasil convoca o embaixador na Argentina depois que Milei chamou Lula de condenado")
    french = classify("Le Brésil rappelle son ambassadeur en Argentine")
    assert portuguese is not None and portuguese.tier == 1 and portuguese.country_id == "BR"
    assert french is not None and french.tier == 1 and french.country_id == "BR"


def test_two_leaders_from_different_countries_are_tier_one():
    result = classify("Milei y Lula conversan por telefono")
    assert result is not None
    assert result.tier == 1
    assert result.country_id == "AR"
    paired = classify("Abelardo y Trump acuerdan visas")
    assert paired is not None and paired.tier == 1 and paired.country_id == "CO"


def test_word_boundary_and_stop_list_traps_are_dropped():
    assert classify("Nuevo Mexico debate su presupuesto estatal") is None
    assert classify("Protestas en New Mexico por una ley local") is None
    assert classify("Los Panama Papers cumplen diez anos") is None
    assert classify("Papeles de Panamá: una década después") is None
    assert classify("Elecciones en Georgia cambian el congreso estatal") is None
    assert classify("Mexico envia ayuda a Georgia") is None
    assert classify("Estados Unidos Mexicanos publican el presupuesto") is None
    assert classify("Guatemalacorp reporta ganancias trimestrales") is None
    assert classify("xxmexico firma un tratado con China") is None
    kept = classify("Mexico firma un tratado con Colombia")
    assert kept is not None and kept.tier == 1
    panama = classify("Panama firma un tratado con China")
    assert panama is not None and panama.country_id == "PA"


def test_domestic_story_that_merely_mentions_the_us_is_dropped():
    assert classify("Trump firma el presupuesto federal de Estados Unidos") is None
    assert classify("El Banco de Mexico interviene y el dolar US$ retrocede") is None
    assert classify("El Senado de Mexico aprueba la reforma judicial") is None
    # Everyday words that collide with short abbreviations.
    assert classify("Lula diz que eu nao vou ceder em temas internos") is None
    assert classify("Mexico anuncia un plan de infraestructura") is None
    assert classify("Le Brésil a eu une réforme interne") is None


def test_same_country_leader_without_an_outside_partner_is_dropped():
    assert classify("Keiko Fujimori aprueba alza del salario minimo") is None
    abroad = classify("Keiko Fujimori viaja a China")
    assert abroad is not None and abroad.tier == 1 and abroad.country_id == "PE"


def test_malvinas_counts_as_the_united_kingdom():
    result = classify("Argentina protesta por las Malvinas")
    assert result is not None and result.tier == 1 and result.country_id == "AR"


def test_leaders_are_loaded_from_entities_yml_not_hard_coded():
    relations = open("latin_america_monitor/relations.py", encoding="utf-8").read()
    collector = open("latin_america_monitor/collector.py", encoding="utf-8").read()
    for name in ("Sheinbaum", "Fujimori", "Milei", "Kast", "Espriella"):
        assert name not in relations
        assert name not in collector
    leaders = {leader.name: leader for leader in load_entities().leaders}
    keiko = leaders["Keiko Sofía Fujimori Higuchi"]
    assert keiko.verified is True and keiko.status == "VERIFIED" and keiko.country_id == "PE"
    sheinbaum = leaders["Claudia Sheinbaum Pardo"]
    assert sheinbaum.verified is True and sheinbaum.since_verified is False
    assert leaders["José Antonio Kast Rist"].status == "VERIFIED"
    assert leaders["Delcy Rodríguez Gómez"].status == "VERIFIED"
    assert leaders["Abelardo de la Espriella"].status == "VERIFIED"
    assert leaders["Javier Gerardo Milei"].verified is True
    assert leaders["Luiz Inácio Lula da Silva"].verified is True
    assert leaders["Donald J. Trump"].verified is True
    assert leaders["Marco Rubio"].verified is True
    assert any(leader.status == "PARTIAL" for leader in leaders.values())
    assert all(leader.status != "UNVERIFIED" for leader in leaders.values())


def test_latam_blocs_are_read_or_bloc_headlines_drop():
    """Fails if latam_blocs is missing from entities.yml or the loader skips it."""
    index = load_entities()
    missing = {"MERCOSUR", "CELAC", "CAN", "PACIFIC_ALLIANCE", "ALBA"} - index.latam
    assert not missing, f"latam_blocs not loaded: {sorted(missing)}"
    result = classify("Mercosur rechaza aranceles de Trump")
    assert result is not None and result.tier == 1
    assert classify("La UE y Mercosur firman acuerdo") is not None
    assert classify("CELAC y la UE celebran cumbre") is not None
    assert classify("Comunidad Andina rechaza aranceles de EE.UU.") is not None


def test_pan_regional_headline_is_kept_without_a_specific_country():
    result = classify("Estados Unidos lanza una ofensiva contra políticos de América Latina")
    assert result is not None and result.tier == 1
    assert result.country_id == "latin_america"
    assert result.region_display == "AMÉRICA LATINA"


def _labelled_cases():
    cases = []
    for item in _HEADLINES["should_match"] + _HEADLINES["should_drop"]:
        cases.append(pytest.param(item["headline"], item["expected"], id=item["id"]))
    return cases


@pytest.mark.parametrize(("headline", "expected"), _labelled_cases())
def test_labelled_headlines(headline, expected):
    result = classify(headline)
    got = result.tier if result else "drop"
    assert got == expected


def test_borderline_headlines_are_kept_in_the_fixture_without_an_assertion():
    rows = _HEADLINES["borderline"]
    assert len(rows) >= 15
    assert {row["id"] for row in rows} >= {"T01", "T07", "T13", "T15", "T18", "T20", "T23", "T35", "T37", "T40", "T43", "T47", "T50", "T54", "T56"}
    assert all(row.get("question_for_sam") for row in rows)


def test_legislative_signing_sports_and_pageants():
    assert classify("Lula sanciona ley de salario minimo") is None
    assert classify("Sheinbaum sanciona reforma judicial") is None
    assert classify("Argentina derrota a la inflacion") is None
    assert classify("Chile vs Argentina: final de la Copa") is None
    assert classify("Brasil derrota a Argentina en las eliminatorias") is None
    assert classify("Miss Colombia visita Venezuela") is None
    assert classify("Conmebol sanciona a Argentina") is None
    sanctions = classify("Brasil anuncia sanciones contra el sector exportador")
    assert sanctions is not None and sanctions.tier == 2
    for headline in (
        "Argentina reclama a Brasil por partido de Mercosur",
        "Seleccion de Colombia visita la Casa Blanca; Petro y Trump hablan",
        "Brasil gana a Argentina; Lula y Milei se cruzan en redes",
        "Partido Comunista de Cuba rechaza sanciones de EEUU",
        "Trump sanciona a Petro",
        "EEUU sanciona a funcionarios venezolanos",
        "El partido de Lula y Trump acuerdan aranceles",
        "Milei y Lula se enfrentan en la final de la Copa",
        "Lula y Trump asisten a un partido durante visita de Estado",
        "Copa: Trump y Sheinbaum se reunen antes del Mundial",
        "Partido de Petro rompe con Milei",
        "Venezuela acusa a Colombia de espionaje en el Campeonato",
        "Colombia y Venezuela empatan 1-1 en negociacion de frontera",
        "Cumbre Sudamericana: Brasil y Argentina firman un comunicado",
        "Union Sudamericana respalda el dialogo entre Brasil y Argentina",
    ):
        assert classify(headline) is not None, headline
    for headline in (
        "Amistoso Uruguay-Paraguay termina 1-1",
        "El entrenador Lula Da Silva dirige a Brasil ante Argentina",
        "Gol de Trump en Argentina vs Chile",
        "Brasil 2 Argentina 1",
        "Paraguay y Uruguay: acuerdo por fichaje de delantero",
        # Labelled known gap S101: hard term Copa is not rescued.
        "Argentina y Chile sellan acuerdo de gas en la final de la Copa",
    ):
        assert classify(headline) is None, headline
    # Owner judgment, currently dropped. Listed on the pull request, not reclassified here.
    assert classify("Brasil vence a Argentina en la Copa; Milei critica al arbitro") is None
    assert classify("Maduro celebra triunfo de Venezuela sobre Colombia en eliminatorias") is None
