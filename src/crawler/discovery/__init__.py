"""Discovery package for sitemaps, robots, certificate transparency, and links."""

from crawler.discovery.crtsh import discover_crtsh_subdomains
from crawler.discovery.links import extract_links_from_html
from crawler.discovery.robots import RobotsHandler
from crawler.discovery.sitemap import SitemapDiscoverer
from crawler.discovery.xhr import analyze_xhr_payload

__all__ = [
    "RobotsHandler",
    "SitemapDiscoverer",
    "discover_crtsh_subdomains",
    "extract_links_from_html",
    "analyze_xhr_payload",
]
