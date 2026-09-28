from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass(frozen=True)
class Publication:
    name: str
    domain: str
    market: str
    scope: str  # "latin_america" or "international"


@dataclass
class Headline:
    title: str
    publisher: str
    url: str
    seen_at: datetime
    market: str
    scope: str
    domain: str
    language: str = ""

    def to_dict(self) -> dict[str, str]:
        data = asdict(self)
        data["seen_at"] = self.seen_at.isoformat()
        return data
