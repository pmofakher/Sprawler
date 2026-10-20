"""Redirect detection and classification (HTTP 3xx, meta refresh, JS, canonical)."""

import re
from typing import List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from crawler.domain.enums import RedirectType
from crawler.frontier.normalizer import get_registrable_domain

# Regular expressions for JS-based redirects
JS_REDIRECT_REGEX = re.compile(
    r"(?:window\.|document\.)?location(?:\.href|\.replace)?\s*=\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)
META_REFRESH_REGEX = re.compile(
    r"^\s*([0-9]+)\s*;\s*url=['\"]?([^'\";\s]+)['\"]?",
    re.IGNORECASE,
)


def detect_meta_refresh(html_text: str, base_url: str) -> Optional[Tuple[str, int]]:
    """Detects <meta http-equiv="refresh" content="..."> in raw HTML."""
    if not html_text:
        return None
    try:
        soup = BeautifulSoup(html_text, "html.parser")
        meta = soup.find("meta", attrs={"http-equiv": re.compile(r"^refresh$", re.I)})
        if meta and meta.get("content"):
            content = str(meta["content"])
            match = META_REFRESH_REGEX.search(content)
            if match:
                delay = int(match.group(1))
                target = match.group(2)
                resolved = urljoin(base_url, target)
                return resolved, delay
    except Exception:
        pass
    return None


def detect_js_redirect(html_text: str, base_url: str) -> Optional[str]:
    """Inspects inline script elements for window.location / location.href redirects."""
    if not html_text:
        return None
    try:
        matches = JS_REDIRECT_REGEX.findall(html_text)
        if matches:
            target = matches[0]
            # Avoid javascript: or anchor-only redirects
            if not target.startswith("javascript:") and not target.startswith("#"):
                return urljoin(base_url, target)
    except Exception:
        pass
    return None


def classify_redirect_hop(
    initial_url: str,
    final_url: str,
    status_code: Optional[int] = None,
    is_meta: bool = False,
    is_js: bool = False,
) -> RedirectType:
    """Classifies the mechanical nature of a redirection transition."""
    if initial_url == final_url:
        return RedirectType.NONE

    parsed_init = urlparse(initial_url)
    parsed_final = urlparse(final_url)

    reg_init = get_registrable_domain(initial_url)
    reg_final = get_registrable_domain(final_url)

    # Cross-domain redirection
    if reg_init != reg_final:
        return RedirectType.EXTERNAL_REDIRECT

    # Canonical hostname normalization (e.g. http -> https or www <-> non-www)
    init_host = parsed_init.netloc.lower()
    final_host = parsed_final.netloc.lower()
    clean_init_host = init_host[4:] if init_host.startswith("www.") else init_host
    clean_final_host = final_host[4:] if final_host.startswith("www.") else final_host
    if clean_init_host == clean_final_host and parsed_init.path == parsed_final.path:
        return RedirectType.CANONICAL_REDIRECT

    if is_meta:
        return RedirectType.META_REFRESH

    if is_js:
        return RedirectType.JS_REDIRECT

    if status_code and 300 <= status_code < 400:
        return RedirectType.HTTP_3XX

    return RedirectType.NONE
