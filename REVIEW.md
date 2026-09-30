# Review notes

Scope change on top of `main` at `cd60dfa`. The monitor now keeps only Latin American international-relations headlines. Domestic politics are dropped. The report is `Publisher: headline` plus the direct link, grouped by region and country, with Tier 1 (a country or leader paired with a different country or leader) sorted first inside each country. CSV and JSON outputs are gone. Email uses the same layout and is sent only when SMTP secrets are set.

## Filter

Matching is headline-only, accent- and case-insensitive, in Spanish, Portuguese, English, and French. Names, aliases, and terms are data in `latin_america_monitor/entities.yml`.

- Tier 1: a Latin American country or leader plus a different country or leader.
- Tier 2: one Latin American entity (or a pan-regional phrase) plus an international-relations term (sanctions, tariffs/`aranceles`/`tarifas`, visas, ambassador and `llama a consultas`, diplomatic or consular relations, treaty, extradition, deportation, summit, OAS/OEA, UN/ONU, IMF/FMI, ICC/CPI, EU/UE, Shield of the Americas, and the other aliases in the file). China is a foreign country, so a Latin American entity plus China is Tier 1.
- Anything else is dropped. Word boundaries apply. Stop phrases blank Nuevo México / New Mexico, the Panama Papers, and bare Georgia before matching.

`US` / `USA` / `EU` / `UE` / `UN` / `UK` match as uppercase tokens (plus phrases such as `la ue`). Portuguese `eu`, Spanish `un`, French `a eu`, and `US$` do not. Multi-country headlines are filed once, under the first specific Latin American country or leader. Pan-regional-only headlines are filed under AMÉRICA LATINA.

GDELT searches English machine translation, so the index query is a narrower recall net than the headline aliases. Latin American domains are `domain AND (other countries OR foreign/IR terms OR non-home leaders)`, which leaves out the outlet's own country. International domains are `domain AND a Latin American place AND (IR terms OR the short leader list)`. Leader tokens actually sent to GDELT are Milei, Lula, Trump, Rubio, and Putin. Other leaders are headline-only, so a bilateral story whose English text never uses a country name, an IR term, or one of those five surnames can be missed at the index even though the headline filter would have kept it.

## Catalogue

146 outlets: 108 Latin American across 21 markets, 38 international. No duplicate domains. Longest-domain match is unchanged, so `cnnespanol.cnn.com` is CNN Español and `edition.cnn.com` stays CNN, `elheraldo.co` is Colombia and `elheraldo.hn` is Honduras, and `folha.uol.com.br` stays Folha while `economia.uol.com.br` is UOL.

### Added

International: AFP (`afp.com`; the apex has no DNS A record, `www.afp.com` is AFP and matching strips `www`), EFE (`efe.com`), Bloomberg Línea (`bloomberglinea.com`), Americas Quarterly (`americasquarterly.org`), Diálogo Américas (`dialogo-americas.com`), El Cato (`elcato.org`), PanAm Post (`panampost.com`), El American (`elamerican.com`), CNN Español (`cnnespanol.cnn.com`), El Nuevo Herald (`elnuevoherald.com`), Voz de América (`vozdeamerica.com`), MercoPress (`mercopress.com`).

Mexico: Proceso (`proceso.com.mx`), Aristegui Noticias (`aristeguinoticias.com`).

Central America and the Caribbean: Plaza Pública (`plazapublica.com.gt`), No-Ficción (`no-ficcion.com`), República GT (`republica.com`), Contracorriente (`contracorriente.red`), Criterio.hn (`criterio.hn`), Revista Factum (`revistafactum.com`), Divergentes (`divergentes.com`), El 19 Digital (`el19digital.com`), Delfino (`delfino.cr`), Semanario Universidad (`semanariouniversidad.com`), Diario de Cuba (`diariodecuba.com`), El Toque (`eltoque.com`), Acento (`acento.com.do`).

Andean and northern South America: La Silla Vacía (`lasillavacia.com`), El Colombiano (`elcolombiano.com`), El Heraldo (`elheraldo.co`), Expreso (`expreso.ec`), Plan V (`planv.com.ec`), GK (`gk.city`), IDL-Reporteros (`idl-reporteros.pe`), RPP (`rpp.pe`), Brújula Digital (`brujuladigital.net`), El Pitazo (`elpitazo.net`), Armando.info (`armando.info`), Prodavinci (`prodavinci.com`), Runrun.es (`runrun.es`), Globovisión (`globovision.com`), teleSUR (`telesurtv.net`), Banca y Negocios (`bancaynegocios.com`), Ministerio de Relaciones Exteriores (`mppre.gob.ve`).

Southern cone and Brazil: Ámbito Financiero (`ambito.com`), La Derecha Diario (`derechadiario.com.ar`), Filo News (`filo.news`), El Líbero (`ellibero.cl`), CIPER (`ciperchile.cl`), Búsqueda (`busqueda.com.uy`), Poder360 (`poder360.com.br`), Gazeta do Povo (`gazetadopovo.com.br`), UOL (`uol.com.br`), R7 (`r7.com`).

Several of those hosts returned 403 or 429 from this environment (Cloudflare or a bot wall) and were still added because the domain is the known site. El Nuevo Herald resolved in DNS; HTTPS from this environment failed, and the sample briefing URL uses that host.

### Skipped

- `albertonews.com` — DNS resolves, but the homepage and the sample article both returned a Cloudflare challenge. Identity was not confirmed.
- `republicagt.com` — an unrelated site, not República GT. The Guatemala desk is `republica.com` (the `/guatemala` title is República GT). The apex geo-redirects; non-IR headlines are still dropped by the filter.
- `factum.la` — does not resolve. Revista Factum is `revistafactum.com`.
- `laderechadiario.com.ar` — does not resolve. La Derecha Diario is `derechadiario.com.ar`.
- Desks already in the previous 92 (Reuters, AP, Infobae, El País, DW, and the national papers) were not added again. CNN Español is a new subdomain entry; `cnn.com` remains CNN.

## Leaders marked `verified: false`

LAPM Sources is checking offices separately. These entries are the seed implied by the sample briefings or by the current public office, and they should be corrected in `entities.yml` rather than in code:

Claudia Sheinbaum (Mexico), Bernardo Arévalo (Guatemala), Xiomara Castro (Honduras), Rosario Murillo (Nicaragua), Rodrigo Chaves (Costa Rica), José Raúl Mulino (Panama), Luis Abinader (Dominican Republic), Abelardo de la Espriella (Colombia; aliases include Abelardo and De la Espriella), Gustavo Petro (Colombia), Delcy Rodríguez (Venezuela), Nicolás Maduro (Venezuela), María Corina Machado (Venezuela; no bare Machado), Diosdado Cabello (Venezuela; no bare Cabello), Daniel Noboa (Ecuador), Keiko Fujimori (Peru), Luis Arce (Bolivia), José Antonio Kast (Chile), Gabriel Boric (Chile), Yamandú Orsi (Uruguay), Santiago Peña (Paraguay; no bare Peña), Xi Jinping (China), Vladimir Putin (Russia).

Marked `verified: true`: Javier Milei, Luiz Inácio Lula da Silva, Nayib Bukele, Daniel Ortega (alias is the full name, not bare Ortega), Miguel Díaz-Canel, Donald Trump, Marco Rubio.

## Run time

`build_queries()` produces **604** requests (398 international, 206 Latin American) with encoded length at most 240. At 5.25 seconds that is about **53 minutes** before cap-splits. Tests require `len(queries) <= 750` and `len(queries) * 5.1 < 80 minutes`. A busy Monday that splits on the 250-record cap multiplies some of those requests. The 150-minute job still has headroom, and the first real run should be watched.

## Known limits

- Small independents may not be indexed by GDELT (No-Ficción, Plaza Pública, Criterio.hn, Divergentes, El Toque, and similar desks). Measure that on the first real run. A per-outlet RSS or sitemap fallback is a follow-up; it is not in this change.
- The headline filter misses an international-relations story that names neither a country, a leader, nor an IR term.
- `tarifa` / `tarifas` can match a domestic price story. Bare `consultas` is not an IR term; only the recalled-ambassador phrases are. Portuguese `visto` (visa) is omitted because Spanish `visto` means "seen".
- French `Chili` is a Chile alias.
- `norteamericano` maps to the United States.
- Georgia is fully masked, including the country.
- `afp.com` has no apex DNS; catalogue matching still accepts `www.afp.com`.
- República GT's domain also serves a US edition.
- Paywalled international papers stay as domain entries. The monitor does not bypass paywalls.
