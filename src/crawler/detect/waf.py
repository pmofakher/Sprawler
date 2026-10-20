"""WAF and anti-bot vendor fingerprinting."""

from typing import Dict, Optional
from crawler.domain.enums import WafVendor


def detect_waf(
    headers: Dict[str, str],
    cookies: Optional[Dict[str, str]] = None,
    html_text: str = "",
) -> WafVendor:
    """Analyzes response headers, cookies, and page signatures to identify the active WAF."""
    norm_headers = {k.lower(): v.lower() for k, v in headers.items()}
    norm_cookies = {k.lower(): v.lower() for k, v in (cookies or {}).items()}
    lower_html = html_text.lower() if html_text else ""

    # Cloudflare
    if (
        "cf-ray" in norm_headers
        or "cf-cache-status" in norm_headers
        or "__cf_bm" in norm_cookies
        or "cloudflare" in norm_headers.get("server", "")
    ):
        return WafVendor.CLOUDFLARE

    # ArvanCloud (Common in Iranian internet infrastructure)
    if (
        "ar-request-id" in norm_headers
        or "ar-powered-by" in norm_headers
        or "x-arvan-cache" in norm_headers
        or "arvancloud" in norm_headers.get("server", "")
    ):
        return WafVendor.ARVANCLOUD

    # Sucuri
    if (
        "x-sucuri-id" in norm_headers
        or "x-sucuri-cache" in norm_headers
        or "sucuri" in norm_headers.get("x-sucuri-id", "")
    ):
        return WafVendor.SUCURI

    # Imperva / Incapsula
    if (
        "x-iinfo" in norm_headers
        or "x-cdn" in norm_headers and "incapsula" in norm_headers["x-cdn"]
        or any("incap_ses" in c or "visid_incap" in c for c in norm_cookies)
    ):
        return WafVendor.IMPERVA

    # Akamai
    if (
        "x-akamai-transformed" in norm_headers
        or "akamai-origin-hop" in norm_headers
        or "akamai" in norm_headers.get("server", "")
    ):
        return WafVendor.AKAMAI

    # DDoS-Guard
    if (
        "ddos-guard" in norm_headers.get("server", "")
        or any("ddg" in c for c in norm_cookies)
        or "ddos-guard" in lower_html
    ):
        return WafVendor.DDOS_GUARD

    return WafVendor.NONE
