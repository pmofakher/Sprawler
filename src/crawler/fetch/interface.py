"""Fetcher interface and fetch response contracts."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol
from crawler.domain.enums import RedirectType
from crawler.domain.models import XhrData


@dataclass
class FetcherResult:
    """Standardized result returned by HTTP or Browser fetchers."""
    url: str
    final_url: str
    status_code: int = 200
    headers: Dict[str, str] = field(default_factory=dict)
    raw_html: str = ""
    rendered_html: Optional[str] = None
    redirect_chain: List[str] = field(default_factory=list)
    redirect_type: RedirectType = RedirectType.NONE
    fetched_with: str = "httpx"
    xhr_data: List[XhrData] = field(default_factory=list)
    error: Optional[str] = None


class Fetcher(Protocol):
    """Abstract protocol for page fetchers."""

    async def fetch(self, url: str) -> FetcherResult:
        """Fetches the page at the given URL."""
        ...
