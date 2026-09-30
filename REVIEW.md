# Review notes

Follow-up on the international-relations scope. Office-holders, aliases, and international-relations terms are the verified `entities.yml` (as of 2026-09-30). Sources and caveats are in the leaders verification table supplied with that file. The matcher reads that file; names are not hard-coded.

## Filter

Headline only, accent-insensitive, Spanish / Portuguese / English / French. Language is guessed from function words so Spanish-press `EU` is the United States and English `EU` is the European Union. `UE` is the European Union in Spanish, Portuguese, and French. Those abbreviations are case-sensitive. A headline that is more than 70% uppercase still matches them.

- Tier 1: a Latin American country or leader plus a different country, leader, or institution (a second Latin American country counts). The OAS, IMF, EU, and UN are institutions, so "Colombia apela al FMI" and "Nicaragua responde a la UE" are Tier 1.
- Tier 2: exactly one Latin American country and a strong international-relations term, or two distinct weak terms on a country name. Weak terms are counted by the matched word, so Spanish `visita` and English `visit` do not double-count.
- Dropped: everything else. A weak alias counts only when a non-weak entity from a different group is also present. Puerto Rico plus the United States needs a strong international-relations term.

Two tester false positives are closed in the matcher:

- `Lula sanciona ley de salario minimo` is dropped. `sanciona` means "signs a law". `sanciones`, `sancionan`, `sanctions`, and `sanções` still count. The ignored token is `gdelt.not_ir_tokens` in `entities.yml`.
- `Chile vs Argentina: final de la Copa` and `Brasil derrota a Argentina en las eliminatorias` are dropped. Sports and culture terms in `out_of_scope_hint_terms` drop the headline before entity matching (`copa`, `eliminatorias`, `goles`, `selección`, `derrota a`, and the rest of that list). Bare `partido` is not on the list: in Spanish it is also a political party, and `El partido de Lula y Trump acuerdan aranceles` stays.

`bbc.com/mundo` is labelled BBC Mundo from the article path. Other `bbc.com` paths stay BBC News. The domain alone cannot tell them apart, and both still share one GDELT query.

82 labelled headlines in `tests/fixtures/test_headlines.yml` are asserted (44 keep, 38 drop). The 15 borderline headlines, plus five pattern notes, are in that file and are not gated. They are listed on the pull request so the owner can rule on them.

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
