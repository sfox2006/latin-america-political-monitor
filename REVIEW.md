# Review notes

Gating fixes for the specialist review of `main` at `baa7b689` are covered by tests: G1 matching, cross-publisher briefing rows, UTC scheduled Monday versus `MONITOR_TIMEZONE`, and `--scheduled` failure/success state handling.

## Left as-is (non-blocking)

Cuba, Haiti, and Nicaragua stay thin on purpose. Each market keeps the outlets already in `latin_america_monitor/sources.py` (Granma and 14ymedio; Le Nouvelliste and Haiti Libre; La Prensa and Confidencial). No extra titles were added for those markets.

Paywalled international papers stay in the catalogue as domain entries only. The monitor does not bypass paywalls. GDELT still supplies the publisher name and the original article URL when the index has the story. The Economist, Financial Times, The Times, The Wall Street Journal, and similar titles are unchanged.
