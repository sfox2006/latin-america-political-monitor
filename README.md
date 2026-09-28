# Latin America Political Monitor

A weekday political-headline monitor modelled on `diesel-policy-monitor`. It scans a curated catalogue of widely read Latin American newspapers and major international outlets that cover the region, then produces a complete ledger containing:

- every matching headline returned in the coverage window;
- the publisher;
- publication time;
- a link to the publisher's original article;
- market and local/international classification.

The scheduled GitHub Action runs Monday-Friday at **11:00 UTC**. Monday covers the previous **72 hours** (the weekend roundup); Tuesday-Friday cover the previous **24 hours**.

## Coverage

The source catalogue currently contains **90+ publications across 20+ Latin American and Caribbean markets**, plus Reuters, AP, BBC, the Financial Times, New York Times, Washington Post, Wall Street Journal, Guardian, Economist, Bloomberg, El País, Le Monde, DW, Al Jazeera, and other major international outlets. The complete, editable catalogue is in [`latin_america_monitor/sources.py`](latin_america_monitor/sources.py).

Discovery uses the [GDELT DOC 2.0 API](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/) and filters results back to the catalogue. GDELT provides direct publisher URLs. As with any news index, inaccessible or unindexed articles can be missed; the report deliberately states this instead of claiming mathematically complete internet coverage.

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

Each run writes dated `.md`, `.csv`, and `.json` files under `output/`. The CSV opens directly in Excel or Google Sheets.

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

If email credentials are absent, the Action still generates and uploads the complete report as a workflow artifact.

Optional repository variables:

| Variable | Default | Purpose |
|---|---:|---|
| `MONITOR_TIMEZONE` | `America/New_York` | Determines which run is Monday |
| `REQUEST_DELAY_SECONDS` | `5.25` | Pause between GDELT queries; clamped to at least 5.1 seconds to respect the API limit |
| `ENRICH_HEADLINES` | `false` | Fetch original pages to refresh titles and canonical links; slower and some publishers block it |

## GitHub setup

1. Push this project to GitHub.
2. Add the email secrets if delivery is wanted.
3. Open **Actions → Weekday Latin America Political Monitor → Run workflow** for a test.
4. Scheduled runs begin automatically after the workflow exists on the default branch.

GitHub schedules can be delayed during periods of heavy Actions load. The coverage-window logic uses the actual run time, so a delayed Monday run still looks back 72 hours.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

## Adding or removing newspapers

Edit the two lists in `latin_america_monitor/sources.py`. Each entry contains a display name, domain, market, and scope. No scraper selector is required because discovery is domain-filtered through GDELT.
