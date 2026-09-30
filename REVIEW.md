# Review notes

Follow-up on the international-relations scope. Office-holders, aliases, and international-relations terms are the verified `entities.yml` (as of 2026-09-30). Sources and caveats are in the leaders verification table supplied with that file. The matcher reads that file; names are not hard-coded.

## Filter

Headline only, accent-insensitive, Spanish / Portuguese / English / French. Language is guessed from function words so Spanish-press `EU` is the United States and English `EU` is the European Union. `UE` is the European Union in Spanish, Portuguese, and French. Those abbreviations are case-sensitive. A headline that is more than 70% uppercase still matches them.

- Tier 1: a Latin American country or leader plus a different country, leader, or institution (a second Latin American country counts). The OAS, IMF, EU, and UN are institutions, so "Colombia apela al FMI" and "Nicaragua responde a la UE" are Tier 1.
- Tier 2: exactly one Latin American country and a strong international-relations term, or two distinct weak terms on a country name. Weak terms are counted by the matched word, so Spanish `visita` and English `visit` do not double-count.
- Dropped: everything else. A weak alias counts only when a non-weak entity from a different group is also present. Puerto Rico plus the United States needs a strong international-relations term.

Law-signing phrases in `law_signing_stoplist` are masked before any entity or term match. `Lula sanciona ley de salario minimo` and `Sheinbaum sanciona reforma judicial` drop. `Trump sanciona a Petro` and `EEUU sanciona a funcionarios venezolanos` stay, because those are not law-signing phrases and they name two sides. Explicit sanction forms (`sanciones`, `sanctions`, `sanções`) remain strong terms. There is no bare `sancion*` wildcard.

Order of operations matches the reference checker. `law_signing_stoplist` is masked first. Entities and international-relations terms are matched second. `sports_rule` then runs on the original headline, after party-name exceptions such as `Partido Comunista` are blanked. A headline is a fixture when a hard term hits (`copa`, `eliminatorias`, `goles`, `selección de`, Libertadores, Sudamericana, `clasificatoria`, `amistoso`, a scoreline such as `1-1`, and pageant titles `Miss <country>`), when two distinct soft terms hit, or when a versus marker (`derrota a`, `vs`, `vence a`, `gana a`, `empata con`) joins two country names and no leader is named. Spanish and Portuguese `partido` are one soft term, not two. `deport(s|ed|ing|ation|ations|ee|ees)?` does not match `deporte`.

A leader override then keeps the fixture when it names leaders of two countries, a Latin American leader plus a foreign entity, or a foreign leader plus any Latin American entity. A cue beside a name (`entrenador`, `tecnico`, `delantero`, `gol de`, `goles de`) means that name is a coach or player, not the office-holder. `entrenador` and `tecnico` are also hard sports signals on their own. After that, `override_ir` keeps a strong international-relations term, including Mercosur, CELAC, the Comunidad Andina, the IMF, the OAS, and the Casa Blanca. Conmebol or FIFA sanctions do not count (`Conmebol sanciona a Argentina` still drops). `Argentina derrota a la inflacion` drops because it is one country and not an international-relations term.

The verified file already keeps `Argentina reclama a Brasil por partido de Mercosur` (one soft term, and Mercosur is in `override_ir`) and `Seleccion de Colombia visita la Casa Blanca; Petro y Trump hablan` (Petro and Trump are leaders from different countries). The same override keeps `Brasil gana a Argentina; Lula y Milei se cruzan en redes`, `Milei y Lula se enfrentan en la final de la Copa`, `Lula y Trump asisten a un partido durante visita de Estado`, `Copa: Trump y Sheinbaum se reunen antes del Mundial`, and `Partido de Petro rompe con Milei`. `Partido Comunista de Cuba rechaza sanciones de EEUU` stays because the party name is an exception and `sanciones` is a real term. `Miss Colombia visita Venezuela` drops.

Three fixtures are dropped beyond the 152, because the attached vocabulary does not yet mark them. `Amistoso Uruguay-Paraguay termina 1-1` drops on `amistoso` and the `1-1` scoreline. `El entrenador Lula Da Silva dirige a Brasil ante Argentina` drops because the coach cue is a sports signal and the namesake is not counted as the president. `Gol de Trump en Argentina vs Chile` drops because `gol de` before the name is a player cue. If Sources adds those terms to `entities.yml`, the labelled set and the matcher agree.

Two headlines stay dropped and are left for the owner. `Brasil vence a Argentina en la Copa; Milei critica al arbitro` and `Maduro celebra triunfo de Venezuela sobre Colombia en eliminatorias` each name one leader beside a fixture, which is not enough for the leader override.

`bbc.com/mundo` is labelled BBC Mundo from the article path. Other `bbc.com` paths stay BBC News. The domain alone cannot tell them apart, and both still share one GDELT query.

152 labelled headlines in `tests/fixtures/test_headlines.yml` are asserted (72 keep, 80 drop) and match the reference checker with no mismatches. The 15 borderline headlines, plus five pattern notes, are in that file and are not gated. They are listed on the pull request so the owner can rule on them, together with the two one-leader fixture headlines above.

## Catalogue

145 outlets: 112 Latin American (21 country markets plus pan-regional "Latin America"), 33 international. No duplicate domains.

Reconciled with the verified outlet list: `republica.com` for República GT, `derechadiario.com.ar` for La Derecha Diario, `elheraldo.co` distinct from `elheraldo.hn`. `cnnespanol.cnn.com` is its own entry, so the longest host match labels only that host as CNN Español.

Removed `mppre.gob.ve`. Not added: `albertonews.com`, `reutersconnect.com`. UOL, R7, Voz de América, and MercoPress stay; they were already in and are not duplicates.

Pan-regional desks (Bloomberg Línea, Americas Quarterly, Diálogo Américas, El Cato, PanAm Post) have no home country. They use the same three-clause query as international wires.

## Leaders

`status` and `since_verified` are stored as in `entities.yml`. People marked `UNVERIFIED` stay in that file and are not matched. Todd Blanche is the one excluded name.

`since_verified: false` (the office was confirmed; the start date was not re-checked on 2026-09-30): Claudia Sheinbaum Pardo, Bernardo Arévalo de León, Carlos Ramiro Martínez, Nayib Bukele Ortez, Alexandra Hill Tinoco, José Raúl Mulino Quintero, Javier Eduardo Martínez-Acha Vásquez, Miguel Mario Díaz-Canel Bermúdez, Manuel Marrero Cruz, Bruno Rodríguez Parrilla, Luis Abinader Corona, Alix Didier Fils-Aimé, Jenniffer González Colón, Javier Gerardo Milei, Rodrigo Paz Pereira, Edmand Lara Montaño, Luiz Inácio Lula da Silva, Mauro Luiz Iecker Vieira, Daniel Noboa Azín, Santiago Peña Palacios, Diosdado Cabello.

`status: PARTIAL`: Carlos Ramiro Martínez, Juan Orlando Hernández, Daniel Ortega Saavedra, Rosario Murillo, Valdrack Ludwing Jaentschke Whitaker, Luis Caputo, Gabriel Boric, Félix Plasencia, María Corina Machado, and on the foreign side Pete Hegseth, Scott Bessent, Mauricio Claver-Carone, Johann Wadephul, Sébastien Lecornu, Jean-Noël Barrot, Abbas Araghchi. Todd Blanche is `UNVERIFIED` and excluded from matching.

Bolivia is contested in the source note: Rodrigo Paz is the constitutional president, and Edmand Lara declared himself president in exercise during the September 2026 UN trip. Both are in the file.

## Run time

`build_queries()` produces **494** requests (312 international, 182 Latin American). Encoded length maxes at 240. At 5.25 seconds that is about **43 minutes** before cap-splits. Tests still require at most 750 queries and under 80 minutes at the 5.1 second floor. A busy Monday that splits on the 250-record cap multiplies some of those requests. The 150-minute job has more headroom than the previous 604-query plan.

## Known limits

- Small independents may not be indexed by GDELT. The outlet check saw zero hits for Diálogo Américas, El Cato, El American, and No-Ficción, and left most other new domains untested because the API returned 429. That is a risk for the first real run, not a measured zero. An RSS or sitemap fallback is still a follow-up.
- The headline filter misses an international-relations story that names neither a country, a leader, nor an international-relations term.
- `tarifa` / `tarifas` can match a domestic price. French `Chili` is a weak, case-sensitive Chile alias. Georgia is fully masked.
- `afp.com` has no apex DNS; matching still accepts `www.afp.com`. `republica.com` also serves a US edition; non-IR headlines are dropped by the filter.
- GDELT leader tokens are only Milei, Lula, Trump, Rubio, and Putin. A bilateral story whose English text never uses a country, an IR term, or one of those surnames can be missed at the index.
- Paywalled international papers stay as domain entries. The monitor does not bypass paywalls.
