# Latin America Political Monitor

A weekday monitor of Latin America's international relations. It keeps headlines about how Latin American countries, leaders, and governments deal with other countries or international institutions, and drops domestic news.

Each kept item is one line, `Publisher: headline`, followed by the article link. Items are grouped by region (Norteamérica, Centroamérica + Caribe, Sudamérica) and then by country. Headlines that pair a Latin American country or leader with a different country or leader are listed first inside that country. There is no summary, no count, and no top-N cap.

The scheduled GitHub Action runs Monday–Friday at **11:00 UTC**. Monday covers the previous **72 hours** (Friday 11:00 UTC through Monday 11:00 UTC). Tuesday–Friday cover the previous **24 hours**, so weekday windows meet without a gap. A delayed job anchors to the most recent 11:00 UTC boundary instead of moving the window forward.

## Timezone

Scheduled runs (`python main.py --scheduled`, including the weekday GitHub Action) decide Monday in **UTC**. `scheduled_window` calls `coverage_window(end, "UTC")`. They do not read `MONITOR_TIMEZONE`, and they are not interpreted in `America/New_York`.

Manual runs (`python main.py` without `--scheduled`) use `MONITOR_TIMEZONE` (default `America/New_York`) only to decide whether the local calendar day is Monday. Monday in that timezone uses 72 hours; Tuesday–Friday use 24 hours. A manual run can therefore disagree with a scheduled run near a timezone boundary: 11:00 UTC Monday is still Sunday in `Etc/GMT+12` and already Tuesday in `Pacific/Kiritimati`, but the scheduled job still uses the UTC Monday weekend window.

## What counts

The filter runs on the **headline only**, after accent folding and case folding, in Spanish, Portuguese, English, and French. Countries, leaders, aliases, and international-relations terms live in [`latin_america_monitor/entities.yml`](latin_america_monitor/entities.yml). The matcher does not hard-code them.

- **Tier 1.** The headline names a Latin American country, leader, or bloc (Mercosur, CELAC, the Comunidad Andina, the Alianza del Pacífico, ALBA) and a different country, leader, institution, or bloc (including a second Latin American country, or the OAS, IMF, EU, or UN). A bloc with no country named still counts. These sort first within the country, or under América Latina when no country is named.
- **Tier 2.** Exactly one Latin American country or bloc and a strong international-relations term (sanctions, tariffs, visas, ambassador, treaty, and the rest of `ir_terms` in `entities.yml`). Two different weak terms on a country name also qualify. A leader and that leader's own country count as one entity. A bloc alone, with no foreign side and no strong term, is dropped.
- **Dropped.** Anything else. The order is fixed. `law_signing_stoplist` is masked first, so `sanciona ley`, `sancionou lei`, and `sanctions a law` are not sanctions. Explicit forms (`sanciones`, `sancionan`, `sanctions`, `sanções`) still are. Entities are matched next. `sports_rule` then drops a fixture: a hard term (`copa`, `amistoso`, Libertadores, Sudamericana, `clasificatoria`, `goleada`, `árbitro`, `selección de`, `Miss <country>`, and transfer words such as `fichaje` and `traspaso`), two distinct soft terms (`campeonato` and `championship` are soft; Spanish and Portuguese `partido` count once; a scoreline such as `1-1` counts as one and skips dates, ranges, times, units, and vote counts), a versus marker (`vs`, `vence a`, `gana a`, `empata con`) between country names, a namesake cue beside a leader, or a dashless wire score such as `Brasil 2 Argentina 1`. `Cumbre Sudamericana` and `Union Sudamericana` are exceptions. A leader override keeps two countries' leaders, a Latin American leader plus a foreign entity, or a foreign leader plus any Latin American entity. `override_ir` keeps Mercosur, CELAC, the Comunidad Andina, the IMF, the OAS, and the Casa Blanca. `policy_override` rescues only a soft-only sports reading: strong words (`acusa`, `espionaje`, `negociacion`, `tratado`, `embajador`) rescue any soft-only reading, and ambiguous words (`acuerdo`, `frontera`, `denuncia`) rescue a single soft signal when no player or coach cue is present. Hard terms are not rescued, so `Paraguay y Uruguay: acuerdo por fichaje de delantero` drops and `Argentina y Chile sellan acuerdo de gas en la final de la Copa` stays dropped. `Venezuela acusa a Colombia de espionaje en el Campeonato` and `Colombia y Venezuela empatan 1-1 en negociacion de frontera` stay. Conmebol or FIFA sanctions do not. `deport(s|ed|ing|...)` does not match `deporte`.

Short names use word boundaries. Stop phrases blank Nuevo México / New Mexico, the Panama Papers, Equatorial Guinea, British Columbia, and bare Georgia before matching. A longer official name wins when it overlaps a shorter one, so `Estados Unidos Mexicanos` is Mexico. `US$` / `USD` are currency, not the United States.

Spanish-press `EU` means Estados Unidos. English `EU` means the European Union. `UE` is the European Union in Spanish, Portuguese, and French. Those abbreviations are case-sensitive, so lowercase `ue` does not match. On a headline that is more than 70% uppercase, the case-sensitive abbreviations are matched either way.

A headline that names several Latin American countries is filed under the first specific country or leader in reading order. A bloc headline with no country, and a pan-regional headline with no specific country, are filed under América Latina. Puerto Rico plus the United States is domestic unless a strong international-relations term is also present.

Each person has `status` (`VERIFIED`, `PARTIAL`, or `UNVERIFIED`) and, where the file gives it, `since_verified`. `UNVERIFIED` people are not matched. Correct `entities.yml` when an office changes; do not edit the matcher.

## Catalogue

The watchlist has **145 outlets: 112 Latin American outlets across 22 markets (21 countries plus a pan-regional "Latin America" market), and 33 international outlets**. The full list is in [`latin_america_monitor/sources.py`](latin_america_monitor/sources.py). Domains already in the catalogue were not added again. `elheraldo.co` is El Heraldo (Colombia) and `elheraldo.hn` is the Honduran paper. `cnnespanol.cnn.com` is CNN Español; any other `cnn.com` host stays CNN. `bbc.com/mundo` is labelled BBC Mundo from the article path; other BBC paths stay BBC News, because the domain alone cannot tell them apart.

Not in the catalogue: `mppre.gob.ve` (official page, out of scope for this pass), `albertonews.com`, and `reutersconnect.com`.

Discovery uses the [GDELT DOC 2.0 API](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/) and filters results back to the catalogue. GDELT searches the English machine translation of the article, not the headline. Queries are therefore a recall net, and the headline filter is the precision layer:

- A Latin American outlet is requested as `domain AND (another Latin American country, a foreign or IR term, or a non-home leader)`. The outlet's own country and its own leaders are left out, so a domestic story that only names home is not requested.
- An international wire, and a pan-regional desk with no home country, is requested as `domain AND a Latin American place AND (an IR term or a configured leader token)`.

GDELT leader tokens in the query are a short high-signal set (`Milei`, `Lula`, `Trump`, `Rubio`, `Putin`), stored in `gdelt.yml` rather than in `entities.yml`. Other leaders are still matched on the headline. Encoded queries stay at or under 240 characters. The same story from two publishers is kept; duplicates are removed only when the canonical URL matches (tracking parameters stripped, article ids preserved).

A full pass is **494 index queries** (312 international, including the pan-regional desks, and 182 Latin American), each at or under 240 encoded characters. At the 5.25 second delay that is about **43 minutes** before any 250-result cap splits. The workflow allows 150 minutes. Tests reject a plan above 750 queries or 80 minutes at the 5.1 second floor.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py --no-email
```

Manual lookback override:

```bash
python main.py --lookback-hours 48 --no-email
```

Each run writes one dated Markdown file under `output/`, named `latin_america_political_monitor_YYYY-MM-DD.md`. The email body is that same text, plus an HTML rendering of the same lines. There is no CSV and no JSON report.

## Email delivery

Copy `.env.example` to `.env` and configure SMTP values. For GitHub Actions, add these repository secrets:

| Secret | Meaning |
|---|---|
| `SMTP_HOST` | SMTP server, such as `smtp.gmail.com` |
| `SMTP_PORT` | Usually `587` |
| `SMTP_USER` | SMTP username |
| `SMTP_PASSWORD` | App password or SMTP credential |
| `EMAIL_FROM` | Sender address |
| `EMAIL_TO` | One or more comma-separated recipients |

Email is sent only when `SMTP_USER`, `SMTP_PASSWORD`, and `EMAIL_TO` are set. Otherwise the Action uploads the report as a workflow artifact and does not send mail.

Optional repository variables:

| Variable | Default | Purpose |
|---|---:|---|
| `MONITOR_TIMEZONE` | `America/New_York` | Monday detection for manual runs only. Scheduled runs always use UTC |
| `REQUEST_DELAY_SECONDS` | `5.25` | Pause between GDELT queries; clamped to at least 5.1 seconds to respect the API limit |
| `ENRICH_HEADLINES` | `false` | Fetch original pages to refresh titles and canonical links; slower and some publishers block it |

## GitHub setup

1. Push this project to GitHub.
2. Add the email secrets if delivery is wanted.
3. Open **Actions → Weekday Latin America Political Monitor → Run workflow** for a test.
4. Scheduled runs begin automatically after the workflow exists on the default branch.

Scheduled coverage ends at **11:00 UTC**. A job that starts up to 10 minutes early still uses that day's boundary; a job that starts later uses the most recent boundary, so a Monday run that slips past midnight still covers the weekend. Successful scheduled runs cache their last coverage boundary; after a missed or failed run, the next run expands its window to recover the gap and labels that span as recovered coverage. Manual runs do not change that state. GitHub may evict caches; if that happens the normal 24/72-hour window is used. A failed collection writes `output/failure.json`, sends no email, and does not advance the last-success state. The weekday job allows 150 minutes. Report artifacts are retained for 30 days.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

## Adding or removing newspapers

Edit the two lists in `latin_america_monitor/sources.py`. Each entry contains a display name, domain, market, and scope. A country market must match the English country name in `entities.yml`. The market `Latin America` is the pan-regional case and uses the international query shape. No scraper selector is required because discovery is domain-filtered through GDELT.

Known limits, skipped domains, and leaders whose start date or status is still partial are in [`REVIEW.md`](REVIEW.md).
