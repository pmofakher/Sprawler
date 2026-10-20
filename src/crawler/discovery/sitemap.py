"""Recursive sitemap and sitemap index parser with gzip support."""

import gzip
import io
from typing import List, Set
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import httpx

from crawler.core.constants import DEFAULT_USER_AGENT, SITEMAP_FALLBACK_PATHS
from crawler.core.logging import logger
from crawler.frontier.filter import should_skip_url
from crawler.frontier.normalizer import is_in_domain_scope, normalize_url


class SitemapDiscoverer:
    """Discovers and parses XML sitemaps to seed the crawler frontier."""

    def __init__(
        self,
        root_url: str,
        registrable_domain: str,
        allow_subdomains: bool = True,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = 15.0,
    ):
        self.root_url = root_url
        self.registrable_domain = registrable_domain
        self.allow_subdomains = allow_subdomains
        self.user_agent = user_agent
        self.timeout = timeout
        self._parsed_sitemaps: Set[str] = set()

    async def discover_urls(self, explicit_sitemaps: List[str] = None) -> List[str]:
        """Discovers internal, non-skipped page URLs across declared and fallback sitemaps."""
        sitemap_targets: Set[str] = set(explicit_sitemaps or [])

        # Add fallback candidates based on root URL
        parsed = urlparse(self.root_url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        for path in SITEMAP_FALLBACK_PATHS:
            sitemap_targets.add(urljoin(base, path))

        discovered_urls: Set[str] = set()

        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers={"User-Agent": self.user_agent},
            verify=False,
            follow_redirects=True,
        ) as client:
            for sitemap_url in sitemap_targets:
                await self._crawl_sitemap_recursive(client, sitemap_url, discovered_urls)

        logger.info(
            f"Discovered {len(discovered_urls)} valid page URLs from XML sitemaps",
            extra={"domain": self.registrable_domain},
        )
        return list(discovered_urls)

    async def _crawl_sitemap_recursive(
        self,
        client: httpx.AsyncClient,
        sitemap_url: str,
        output_urls: Set[str],
        depth: int = 0,
    ) -> None:
        """Recursively parses a single sitemap or sitemap index."""
        if sitemap_url in self._parsed_sitemaps or depth > 3:
            return
        self._parsed_sitemaps.add(sitemap_url)

        try:
            resp = await client.get(sitemap_url)
            if resp.status_code != 200 or not resp.content:
                return

            content_bytes = resp.content
            # Decompress if gzipped
            if sitemap_url.endswith(".gz") or content_bytes.startswith(b"\x1f\x8b"):
                try:
                    with gzip.GzipFile(fileobj=io.BytesIO(content_bytes)) as gz:
                        content_bytes = gz.read()
                except Exception as exc:
                    logger.debug(f"Failed to decompress gzip sitemap {sitemap_url}: {exc}")
                    return

            soup = BeautifulSoup(content_bytes, "xml")

            # Check if this is a sitemap index (contains <sitemap><loc>...)
            sub_sitemaps = soup.find_all("sitemap")
            if sub_sitemaps:
                for sub in sub_sitemaps:
                    loc = sub.find("loc")
                    if loc and loc.text:
                        sub_url = loc.text.strip()
                        await self._crawl_sitemap_recursive(client, sub_url, output_urls, depth + 1)
                return

            # Parse regular <url><loc> entries
            url_tags = soup.find_all("url")
            for url_tag in url_tags:
                loc = url_tag.find("loc")
                if loc and loc.text:
                    raw_url = loc.text.strip()
                    try:
                        norm = normalize_url(raw_url)
                        if not is_in_domain_scope(norm, self.registrable_domain, self.allow_subdomains):
                            continue
                        skip, _ = should_skip_url(norm)
                        if not skip:
                            output_urls.add(norm)
                    except Exception:
                        continue
        except Exception as exc:
            logger.debug(f"Error fetching sitemap {sitemap_url}: {exc}")
