from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from .models import Headline
from .window import CoverageWindow


def _safe(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def _md_link(title: str, url: str) -> str:
    text = _safe(title).replace("[", "\\[").replace("]", "\\]")
    href = url.replace(" ", "%20").replace("(", "%28").replace(")", "%29")
    return f"[{text}]({href})"


def build_markdown(headlines: list[Headline], window: CoverageWindow, generated_at: datetime) -> str:
    source_count = len({item.domain for item in headlines})
    lines = [
        f"# Latin America Political Monitor — {generated_at:%d %B %Y}",
        "",
        f"**Coverage:** {window.start:%Y-%m-%d %H:%M UTC} to {window.end:%Y-%m-%d %H:%M UTC} ({window.label})  ",
        f"**Results:** {len(headlines)} headlines from {source_count} publishers",
        "",
    ]
    if not headlines:
        lines += ["_No matching headlines were indexed during this coverage window._", ""]
        return "\n".join(lines)

    groups: dict[str, list[Headline]] = defaultdict(list)
    for item in headlines:
        group = item.market if item.scope == "latin_america" else "International coverage"
        groups[group].append(item)

    local_markets = sorted(group for group in groups if group != "International coverage")
    ordered_groups = local_markets + (["International coverage"] if "International coverage" in groups else [])
    for group in ordered_groups:
        items = groups[group]
        lines += [f"## {group} ({len(items)})", "", "| First indexed (UTC) | Publisher | Headline |", "|---|---|---|"]
        for item in items:
            lines.append(f"| {item.seen_at:%Y-%m-%d %H:%M} | {_safe(item.publisher)} | {_md_link(item.title, item.url)} |")
        lines.append("")

    lines += [
        "---",
        "",
        "Headlines are discovered through the GDELT global news index and link directly to the publisher. "
        "Coverage depends on publisher accessibility and GDELT indexing; it should not be read as a claim that every article on the internet was captured.",
        "",
    ]
    return "\n".join(lines)


def write_outputs(headlines: list[Headline], window: CoverageWindow, output_dir: Path) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = window.end.strftime("%Y-%m-%d")
    md_path = output_dir / f"latin_america_political_monitor_{stamp}.md"
    csv_path = output_dir / f"latin_america_political_monitor_{stamp}.csv"
    json_path = output_dir / f"latin_america_political_monitor_{stamp}.json"
    md_path.write_text(build_markdown(headlines, window, window.end), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["seen_at", "publisher", "headline", "original_url", "market", "scope", "domain", "language"])
        writer.writeheader()
        for item in headlines:
            writer.writerow({
                "seen_at": item.seen_at.isoformat(), "publisher": item.publisher, "headline": item.title,
                "original_url": item.url, "market": item.market, "scope": item.scope,
                "domain": item.domain, "language": item.language,
            })
    json_path.write_text(json.dumps([item.to_dict() for item in headlines], ensure_ascii=False, indent=2), encoding="utf-8")
    return md_path, csv_path, json_path


def publisher_summary(headlines: list[Headline]) -> str:
    counts = Counter(item.publisher for item in headlines)
    return ", ".join(f"{name} ({count})" for name, count in counts.most_common(12))
