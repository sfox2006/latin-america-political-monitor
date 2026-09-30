from __future__ import annotations

import re
from html import escape
from pathlib import Path

from .models import Headline
from .relations import group_headlines
from .window import CoverageWindow

_EMPTY = "No international-relations headlines were indexed in this window.\n"


def _one_line(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def build_markdown(headlines: list[Headline]) -> str:
    """Publisher, headline, and link, grouped by region and country.

    Tier 1 (a Latin American country or leader paired with a different one)
    is listed before Tier 2 inside each country. Headlines that are not
    international relations are omitted.
    """
    sections = group_headlines(headlines)
    if not sections:
        return _EMPTY
    lines: list[str] = []
    for section in sections:
        lines.append(section.title)
        lines.append("")
        for block in section.blocks:
            if block.title:
                lines.append(block.title)
            for item in block.items:
                lines.append(f"{_one_line(item.publisher)}: {_one_line(item.title)}")
                lines.append(item.url.strip())
                lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_html(headlines: list[Headline]) -> str:
    sections = group_headlines(headlines)
    parts = ['<!doctype html><html><body style="font-family:Georgia,serif;color:#17233c;max-width:40rem">']
    if not sections:
        parts.append(f"<p>{escape(_EMPTY.strip())}</p>")
    for section in sections:
        parts.append(f"<h2>{escape(section.title)}</h2>")
        for block in section.blocks:
            if block.title:
                parts.append(f"<h3>{escape(block.title)}</h3>")
            for item in block.items:
                title = _one_line(item.title)
                url = item.url.strip()
                parts.append(
                    f"<p><strong>{escape(_one_line(item.publisher))}:</strong> {escape(title)}<br>"
                    f'<a href="{escape(url, quote=True)}">{escape(url)}</a></p>'
                )
    parts.append("</body></html>")
    return "".join(parts)


def write_outputs(headlines: list[Headline], window: CoverageWindow, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"latin_america_political_monitor_{window.end:%Y-%m-%d}.md"
    path.write_text(build_markdown(headlines), encoding="utf-8")
    return path
