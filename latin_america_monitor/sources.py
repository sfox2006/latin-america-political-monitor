"""Curated catalogue of widely read Latin American and international news outlets."""

from __future__ import annotations

from .models import Publication


def _p(name: str, domain: str, market: str, scope: str = "latin_america") -> Publication:
    return Publication(name=name, domain=domain.lower(), market=market, scope=scope)


LATIN_AMERICAN_PUBLICATIONS = [
    _p("Clarín", "clarin.com", "Argentina"),
    _p("La Nación", "lanacion.com.ar", "Argentina"),
    _p("Página/12", "pagina12.com.ar", "Argentina"),
    _p("Infobae", "infobae.com", "Argentina"),
    _p("Perfil", "perfil.com", "Argentina"),
    _p("El Deber", "eldeber.com.bo", "Bolivia"),
    _p("La Razón", "la-razon.com", "Bolivia"),
    _p("Los Tiempos", "lostiempos.com", "Bolivia"),
    _p("Folha de S.Paulo", "folha.uol.com.br", "Brazil"),
    _p("O Globo", "oglobo.globo.com", "Brazil"),
    _p("G1", "g1.globo.com", "Brazil"),
    _p("O Estado de S. Paulo", "estadao.com.br", "Brazil"),
    _p("Valor Econômico", "valor.globo.com", "Brazil"),
    _p("Correio Braziliense", "correiobraziliense.com.br", "Brazil"),
    _p("El Mercurio / Emol", "emol.com", "Chile"),
    _p("La Tercera", "latercera.com", "Chile"),
    _p("El Mostrador", "elmostrador.cl", "Chile"),
    _p("Diario Financiero", "df.cl", "Chile"),
    _p("El Tiempo", "eltiempo.com", "Colombia"),
    _p("El Espectador", "elespectador.com", "Colombia"),
    _p("Semana", "semana.com", "Colombia"),
    _p("La República", "larepublica.co", "Colombia"),
    _p("La Nación", "nacion.com", "Costa Rica"),
    _p("CRHoy", "crhoy.com", "Costa Rica"),
    _p("Granma", "granma.cu", "Cuba"),
    _p("14ymedio", "14ymedio.com", "Cuba"),
    _p("Listín Diario", "listindiario.com", "Dominican Republic"),
    _p("Diario Libre", "diariolibre.com", "Dominican Republic"),
    _p("El Universo", "eluniverso.com", "Ecuador"),
    _p("El Comercio", "elcomercio.com", "Ecuador"),
    _p("Primicias", "primicias.ec", "Ecuador"),
    _p("La Prensa Gráfica", "laprensagrafica.com", "El Salvador"),
    _p("El Diario de Hoy", "elsalvador.com", "El Salvador"),
    _p("El Faro", "elfaro.net", "El Salvador"),
    _p("Prensa Libre", "prensalibre.com", "Guatemala"),
    _p("Soy502", "soy502.com", "Guatemala"),
    _p("Le Nouvelliste", "lenouvelliste.com", "Haiti"),
    _p("Haiti Libre", "haitilibre.com", "Haiti"),
    _p("La Prensa", "laprensa.hn", "Honduras"),
    _p("El Heraldo", "elheraldo.hn", "Honduras"),
    _p("El Universal", "eluniversal.com.mx", "Mexico"),
    _p("Reforma", "reforma.com", "Mexico"),
    _p("Milenio", "milenio.com", "Mexico"),
    _p("La Jornada", "jornada.com.mx", "Mexico"),
    _p("Excélsior", "excelsior.com.mx", "Mexico"),
    _p("El Financiero", "elfinanciero.com.mx", "Mexico"),
    _p("Animal Político", "animalpolitico.com", "Mexico"),
    _p("La Prensa", "laprensani.com", "Nicaragua"),
    _p("Confidencial", "confidencial.digital", "Nicaragua"),
    _p("La Prensa", "prensa.com", "Panama"),
    _p("La Estrella de Panamá", "laestrella.com.pa", "Panama"),
    _p("ABC Color", "abc.com.py", "Paraguay"),
    _p("Última Hora", "ultimahora.com", "Paraguay"),
    _p("El Comercio", "elcomercio.pe", "Peru"),
    _p("La República", "larepublica.pe", "Peru"),
    _p("Gestión", "gestion.pe", "Peru"),
    _p("Perú21", "peru21.pe", "Peru"),
    _p("El Nuevo Día", "elnuevodia.com", "Puerto Rico"),
    _p("Primera Hora", "primerahora.com", "Puerto Rico"),
    _p("El País", "elpais.com.uy", "Uruguay"),
    _p("El Observador", "elobservador.com.uy", "Uruguay"),
    _p("La Diaria", "ladiaria.com.uy", "Uruguay"),
    _p("El Nacional", "elnacional.com", "Venezuela"),
    _p("El Universal", "eluniversal.com", "Venezuela"),
    _p("TalCual", "talcualdigital.com", "Venezuela"),
    _p("Efecto Cocuyo", "efectococuyo.com", "Venezuela"),
]

INTERNATIONAL_PUBLICATIONS = [
    _p("Reuters", "reuters.com", "International", "international"),
    _p("Associated Press", "apnews.com", "International", "international"),
    _p("BBC News", "bbc.com", "United Kingdom", "international"),
    _p("The Guardian", "theguardian.com", "United Kingdom", "international"),
    _p("Financial Times", "ft.com", "United Kingdom", "international"),
    _p("The Economist", "economist.com", "United Kingdom", "international"),
    _p("The Times", "thetimes.com", "United Kingdom", "international"),
    _p("The New York Times", "nytimes.com", "United States", "international"),
    _p("The Washington Post", "washingtonpost.com", "United States", "international"),
    _p("The Wall Street Journal", "wsj.com", "United States", "international"),
    _p("Los Angeles Times", "latimes.com", "United States", "international"),
    _p("Bloomberg", "bloomberg.com", "United States", "international"),
    _p("Politico", "politico.com", "United States", "international"),
    _p("CNN", "cnn.com", "United States", "international"),
    _p("The Globe and Mail", "theglobeandmail.com", "Canada", "international"),
    _p("CBC News", "cbc.ca", "Canada", "international"),
    _p("El País", "elpais.com", "Spain", "international"),
    _p("El Mundo", "elmundo.es", "Spain", "international"),
    _p("Le Monde", "lemonde.fr", "France", "international"),
    _p("France 24", "france24.com", "France", "international"),
    _p("Deutsche Welle", "dw.com", "Germany", "international"),
    _p("Al Jazeera", "aljazeera.com", "Qatar", "international"),
    _p("Nikkei Asia", "asia.nikkei.com", "Japan", "international"),
    _p("South China Morning Post", "scmp.com", "Hong Kong", "international"),
    _p("The Sydney Morning Herald", "smh.com.au", "Australia", "international"),
    _p("ABC News Australia", "abc.net.au", "Australia", "international"),
]

PUBLICATIONS = LATIN_AMERICAN_PUBLICATIONS + INTERNATIONAL_PUBLICATIONS
PUBLICATION_BY_DOMAIN = {publication.domain: publication for publication in PUBLICATIONS}


def match_publication(domain: str) -> Publication | None:
    """Match a host returned by GDELT, accepting www and subdomain variants."""
    domain = domain.lower().removeprefix("www.")
    exact = PUBLICATION_BY_DOMAIN.get(domain)
    if exact:
        return exact
    matches = [p for p in PUBLICATIONS if domain == p.domain or domain.endswith("." + p.domain)]
    return max(matches, key=lambda p: len(p.domain), default=None)

