from datetime import datetime, timedelta, timezone

from latin_america_monitor.relations import classify, load_entities


def test_exemplar_headlines_match_the_international_relations_filter():
    matched = {
        "Brasil llama a consultas a su embajador en Argentina tras el 'convicto' de Milei a Lula": (1, "brazil"),
        "EE.UU. cancela visas a ciudadanos de Ecuador, Bolivia, Colombia y Peru": (1, "ecuador"),
        "Kast y el Escudo de las Americas de Trump": (1, "chile"),
        "Nicaragua responde a la UE": (2, "nicaragua"),
        "Colombia apela al FMI": (2, "colombia"),
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
    phrase = classify("nicaragua responde a la ue")
    mixed = classify("MÉXICO y CHINA firman un tratado")
    assert lower is not None and lower.tier == 1 and lower.country_id == "ecuador"
    assert upper is not None and upper.tier == 2
    assert phrase is not None and phrase.tier == 2
    assert mixed is not None and mixed.tier == 1 and mixed.country_id == "mexico"


def test_portuguese_and_french_headlines_match():
    portuguese = classify("Brasil convoca o embaixador na Argentina depois que Milei chamou Lula de condenado")
    french = classify("Le Brésil rappelle son ambassadeur en Argentine")
    assert portuguese is not None and portuguese.tier == 1 and portuguese.country_id == "brazil"
    assert french is not None and french.tier == 1 and french.country_id == "brazil"


def test_two_leaders_from_different_countries_are_tier_one():
    result = classify("Milei y Lula conversan por telefono")
    assert result is not None
    assert result.tier == 1
    assert result.country_id == "argentina"
    paired = classify("Abelardo y Trump acuerdan visas")
    assert paired is not None and paired.tier == 1 and paired.country_id == "colombia"


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
    assert panama is not None and panama.country_id == "panama"


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
    assert abroad is not None and abroad.tier == 1 and abroad.country_id == "peru"


def test_malvinas_counts_as_the_united_kingdom():
    result = classify("Argentina protesta por las Malvinas")
    assert result is not None and result.tier == 1 and result.country_id == "argentina"


def test_leaders_are_loaded_from_entities_yml_not_hard_coded():
    relations = open("latin_america_monitor/relations.py", encoding="utf-8").read()
    collector = open("latin_america_monitor/collector.py", encoding="utf-8").read()
    for name in ("Sheinbaum", "Fujimori", "Milei", "Kast", "Espriella"):
        assert name not in relations
        assert name not in collector
    leaders = {leader.name: leader for leader in load_entities().leaders}
    assert leaders["Keiko Fujimori"].verified is False
    assert leaders["Keiko Fujimori"].country_id == "peru"
    assert leaders["José Antonio Kast"].verified is False
    assert leaders["Delcy Rodríguez"].verified is False
    assert leaders["Abelardo de la Espriella"].verified is False
    assert leaders["Javier Milei"].verified is True
    assert leaders["Luiz Inácio Lula da Silva"].verified is True
    assert leaders["Donald Trump"].verified is True
    assert leaders["Marco Rubio"].verified is True
    assert any(leader.verified is False for leader in leaders.values())


def test_pan_regional_headline_is_kept_without_a_specific_country():
    result = classify("Estados Unidos lanza una ofensiva contra políticos de América Latina")
    assert result is not None and result.tier == 1
    assert result.country_id == "latin_america"
    assert result.region_display == "AMÉRICA LATINA"
