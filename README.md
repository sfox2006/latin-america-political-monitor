# Latin America Political Monitor

A weekday political-headline monitor modelled on `diesel-policy-monitor`. It scans a curated catalogue of widely read Latin American newspapers and major international outlets that cover the region, then produces a complete ledger containing:

- every matching headline returned in the coverage window;
- the publisher;
- first-indexed time (not an asserted publisher publication time);
- a link to the publisher's original article;
- market and local/international classification.

The scheduled GitHub Action runs Monday-Friday at **11:00 UTC**. Monday covers the previous **72 hours** (the weekend roundup); Tuesday-Friday cover the previous **24 hours**.

## Coverage

The curated catalogue contains **91 outlets total: 65 regional outlets across 21 Latin American/Caribbean markets and 26 international outlets**. This is an editable watchlist, not a verified ranking or an exhaustive list of every popular newspaper. The complete catalogue is in [`latin_america_monitor/sources.py`](latin_america_monitor/sources.py).

Discovery uses the [GDELT DOC 2.0 API](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/) and filters results back to the catalogue. GDELT provides direct publisher URLs. As with any news index, inaccessible or unindexed articles can be missed; the report deliberately states this instead of claiming mathematically complete internet coverage.

Both regional and international queries require political terms and a Latin American place mention in the indexed article text. This broad keyword method can still include incidental mentions or miss articles without those terms. Headlines remain in the source language. The time window applies to GDELT's `seendate`, exposed as `seen_at`; publisher publication times are not inferred from index times.

Queries reaching the 250-result limit are split into smaller overlapping windows and deduplicated by article URL. If a 15-minute window still reaches the limit, or any query fails after retries, the run fails visibly and writes `failure.json`; no misleading empty or partial briefing is sent. Distinct article IDs in query parameters are preserved, while common tracking parameters are removed.

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
| `MONITOR_TIMEZONE` | `America/New_York` | Determines Monday for manual runs; scheduled runs use their fixed UTC boundary |
| `REQUEST_DELAY_SECONDS` | `5.25` | Pause between GDELT queries; clamped to at least 5.1 seconds to respect the API limit |
| `ENRICH_HEADLINES` | `false` | Fetch original pages to refresh titles and canonical links; slower and some publishers block it |

## GitHub setup

1. Push this project to GitHub.
2. Add the email secrets if delivery is wanted.
3. Open **Actions → Weekday Latin America Political Monitor → Run workflow** for a test.
4. Scheduled runs begin automatically after the workflow exists on the default branch.

Scheduled coverage ends at **11:00 UTC** regardless of queue delays, so adjacent windows meet without gaps. Successful scheduled runs cache their last coverage boundary; after a missed or failed run, the next run expands its window to recover the gap. Manual runs do not change that state. GitHub may evict caches; if that happens the normal 24/72-hour window is used. Report artifacts are retained for 30 days. Email remains disabled until SMTP credentials and recipients are configured.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

## Adding or removing newspapers

Edit the two lists in `latin_america_monitor/sources.py`. Each entry contains a display name, domain, market, and scope. No scraper selector is required because discovery is domain-filtered through GDELT.
