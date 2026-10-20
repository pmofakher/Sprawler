"""Fetching package providing HTTP and browser fetchers, interface contracts, and render detection."""

from crawler.fetch.browser_fetcher import BrowserFetcher
from crawler.fetch.http_fetcher import HttpFetcher
from crawler.fetch.interface import Fetcher, FetcherResult
from crawler.fetch.render_detector import detect_render_type_from_html, render_cache

__all__ = [
    "Fetcher",
    "FetcherResult",
    "HttpFetcher",
    "BrowserFetcher",
    "detect_render_type_from_html",
    "render_cache",
]
