"""Robots.txt parser with Protego support, crawl-delay extraction, and sitemap discovery."""

from typing import List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from protego import Protego

from crawler.core.constants import DEFAULT_USER_AGENT
from crawler.core.logging import logger


class RobotsHandler:
    """Fetches, parses, and provides compliance checks for a site's robots.txt."""

    def __init__(self, robots_txt: str = "", user_agent: str = DEFAULT_USER_AGENT):
        self.user_agent = user_agent
        self.sitemaps: List[str] = []
        self.crawl_delay: Optional[float] = None
        self._parser: Optional[Protego] = None

        if robots_txt:
            self._parse(robots_txt)

    def _parse(self, text: str) -> None:
        try:
            self._parser = Protego.parse(text)
            self.sitemaps = list(self._parser.sitemaps)
            delay = self._parser.crawl_delay(self.user_agent)
            if delay is not None:
                self.crawl_delay = float(delay)
        except Exception as exc:
            logger.warning(f"Error parsing robots.txt with Protego: {exc}")
            self._parser = None

    def is_allowed(self, url: str) -> bool:
        """Checks if the user-agent is permitted to crawl the specified URL."""
        if not self._parser:
            # Permissive default if robots.txt is absent or unparseable
            return True
        try:
            return self._parser.can_fetch(url, self.user_agent)
        except Exception:
            return True

    @classmethod
    async def fetch(
        cls,
        root_url: str,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = 10.0,
    ) -> "RobotsHandler":
        """Fetches robots.txt from the root host over HTTP/HTTPS."""
        parsed = urlparse(root_url)
        robots_url = urljoin(f"{parsed.scheme}://{parsed.netloc}", "/robots.txt")

        try:
            async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
                resp = await client.get(robots_url, headers={"User-Agent": user_agent})
                if resp.status_code == 200:
                    return cls(robots_txt=resp.text, user_agent=user_agent)
        except Exception as exc:
            logger.debug(f"Could not fetch robots.txt from {robots_url}: {exc}")

        return cls(robots_txt="", user_agent=user_agent)
