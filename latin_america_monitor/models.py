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
    published: datetime
    market: str
    scope: str
    domain: str
    language: str = ""

    def to_dict(self) -> dict[str, str]:
        data = asdict(self)
        data["published"] = self.published.isoformat()
        return data

