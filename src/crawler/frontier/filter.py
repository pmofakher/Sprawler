"""URL filtering and priority scoring for business knowledge acquisition."""

from typing import List, Optional, Pattern, Tuple
from urllib.parse import parse_qsl, urlparse

from crawler.core.constants import (
    PAGINATION_PATH_REGEX,
    PAGINATION_QUERY_KEYS,
    PRIORITY_URL_KEYWORDS,
    PRODUCT_DENY_PATTERNS,
)
from crawler.domain.enums import SkipReason

# Static non-content asset file extensions
STATIC_ASSET_EXTENSIONS = {
    ".css",
    ".js",
    ".json",
    ".xml",
    ".rss",
    ".svg",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".bmp",
    ".tiff",
    ".mp3",
    ".mp4",
    ".avi",
    ".mov",
    ".wmv",
    ".flv",
    ".wav",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".otf",
    ".zip",
    ".tar",
    ".gz",
    ".rar",
    ".7z",
    ".exe",
    ".bin",
    ".dmg",
}

# Supported document extensions to be processed
DOCUMENT_EXTENSIONS = {".pdf"}


def is_pagination_url(url: str) -> bool:
    """Checks whether the URL represents a paginated list page."""
    parsed = urlparse(url)

    # 1. Query parameter check (e.g. ?page=2, ?p=3, ?offset=20)
    if parsed.query:
        query_keys = {k.lower() for k, _ in parse_qsl(parsed.query)}
        if any(key in PAGINATION_QUERY_KEYS for key in query_keys):
            return True

    # 2. Path pattern check (e.g. /blog/page/2/ or /news/p/3)
    if PAGINATION_PATH_REGEX.search(parsed.path):
        return True

    return False


def is_product_centric_url(url: str, custom_deny_patterns: Optional[List[Pattern[str]]] = None) -> bool:
    """Checks whether the URL targets e-commerce items, carts, checkouts, or product catalogs."""
    patterns = custom_deny_patterns or PRODUCT_DENY_PATTERNS
    for pattern in patterns:
        if pattern.search(url):
            return True
    return False


def is_static_asset(url: str) -> bool:
    """Checks whether the URL points to a static media or style asset (excluding documents like PDFs)."""
    parsed = urlparse(url)
    path = parsed.path.lower()
    for ext in STATIC_ASSET_EXTENSIONS:
        if path.endswith(ext):
            return True
    return False


def is_document_url(url: str) -> bool:
    """Checks whether the URL represents an extractable PDF document."""
    parsed = urlparse(url)
    path = parsed.path.lower()
    for ext in DOCUMENT_EXTENSIONS:
        if path.endswith(ext):
            return True
    return False


def should_skip_url(url: str, max_depth: int = 4, depth: int = 0) -> Tuple[bool, Optional[SkipReason]]:
    """Evaluates filtering criteria on a candidate URL.

    Returns:
      (skip_decision, skip_reason)
    """
    if depth > max_depth:
        return True, SkipReason.MAX_DEPTH_EXCEEDED

    if is_pagination_url(url):
        return True, SkipReason.PAGINATION

    if is_product_centric_url(url):
        return True, SkipReason.PRODUCT

    if is_static_asset(url):
        # Non-document static asset (css, js, images) are skipped as crawl pages
        return True, SkipReason.PRODUCT

    return False, None


def calculate_url_priority(url: str, depth: int = 0) -> int:
    """Computes a frontier priority score (higher integer = crawled earlier).

    High scores are granted to core business identity pages (about, contact, faq, policies).
    Base score decreases with depth.
    """
    score = 50 - (depth * 10)
    lower_url = url.lower()

    # Home page priority
    parsed = urlparse(url)
    if parsed.path in {"", "/"}:
        return 100

    # Business entity keyword matching
    for keyword in PRIORITY_URL_KEYWORDS:
        if keyword in lower_url:
            score += 40
            break

    # Documents (PDFs)
    if is_document_url(url):
        score += 20

    return max(1, min(100, score))
