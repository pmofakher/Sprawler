"""Core constants and definitions for the crawler system."""

from typing import Final, List, Pattern, Set
import re

# Application metadata
APP_NAME: Final[str] = "sprawler"
DEFAULT_USER_AGENT: Final[str] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 (compatible; Sprawler/1.0; +https://github.com/sprawler/sprawler)"
)

# Common fallback paths for sitemaps
SITEMAP_FALLBACK_PATHS: Final[List[str]] = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/wp-sitemap.xml",
    "/sitemap/sitemap.xml",
    "/post-sitemap.xml",
    "/page-sitemap.xml",
]

# Tracking query parameters to drop during URL normalization
TRACKING_PARAMS: Final[Set[str]] = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "gclsrc",
    "dclid",
    "zanpid",
    "msclkid",
    "mc_cid",
    "mc_eid",
    "ref",
    "source",
    "_ga",
    "_gl",
    "yclid",
}

# Pagination query parameters to skip
PAGINATION_QUERY_KEYS: Final[Set[str]] = {
    "page",
    "p",
    "paged",
    "pg",
    "offset",
    "start",
    "page_id",
}

# Pagination path patterns (e.g. /page/2, /p/3)
PAGINATION_PATH_REGEX: Final[Pattern[str]] = re.compile(
    r"(?:^|/)(?:page|p|paged)/[0-9]+/?$",
    re.IGNORECASE,
)

# Product, catalog, cart, account, checkout denial regex patterns
PRODUCT_DENY_PATTERNS: Final[List[Pattern[str]]] = [
    re.compile(r"/(?:product|products|item|items|goods)(?:/|$|\?)", re.IGNORECASE),
    re.compile(r"/(?:shop|store|catalog|catalogue|product-category)(?:/|$|\?)", re.IGNORECASE),
    re.compile(r"/(?:cart|basket|checkout|my-account|order|wishlist)(?:/|$|\?)", re.IGNORECASE),
    re.compile(r"/(?:search|filter|find)(?:/|$|\?)", re.IGNORECASE),
    re.compile(r"[?&](?:orderby|sort|sort_by|filter_|min_price|max_price)=", re.IGNORECASE),
]

# High priority URL indicators for business knowledge
PRIORITY_URL_KEYWORDS: Final[List[str]] = [
    "about",
    "about-us",
    "contact",
    "contact-us",
    "services",
    "service",
    "faq",
    "faqs",
    "policy",
    "privacy",
    "terms",
    "rules",
    "shipping",
    "return",
    "refund",
    "team",
    "history",
    "branches",
    "branch",
    "portfolio",
    "blog",
    "articles",
    "article",
    "news",
    # Persian transliterations & terms
    "darbare",
    "tamas",
    "khadamat",
    "ghavanin",
    "shoab",
    "rahnama",
]

# Maintenance & soft-down keywords (English and Persian)
MAINTENANCE_KEYWORDS: Final[List[str]] = [
    "under maintenance",
    "site is down",
    "coming soon",
    "temporarily unavailable",
    "scheduled maintenance",
    "در حال تعمیر",
    "در حال بروزرسانی",
    "به زودی",
    "سایت در دست ساخت است",
    "به زودی برمی‌گردیم",
]

# CAPTCHA keywords (English and Persian)
CAPTCHA_KEYWORDS: Final[List[str]] = [
    "verify you are human",
    "checking your browser",
    "just a moment",
    "attention required",
    "please complete the security check",
    "cloudflare ray id",
    "ربات نیستم",
    "تایید هویت",
    "تایید امنیتی",
    "من ربات نیستم",
    "لطفا تایید کنید که انسان هستید",
]

# Safe schemes for crawler
ALLOWED_SCHEMES: Final[Set[str]] = {"http", "https"}

# Rejected schemes for SSRF / protocol safety
REJECTED_SCHEMES: Final[Set[str]] = {
    "javascript",
    "mailto",
    "tel",
    "file",
    "ftp",
    "data",
    "blob",
    "ssh",
}

# Cookie / Consent Banner dismiss selectors
CONSENT_SELECTORS: Final[List[str]] = [
    "button#onetrust-accept-btn-handler",
    "button.cookie-consent-accept",
    "button[data-cookie-accept]",
    "#accept-cookies",
    ".accept-cookies-button",
    "button:has-text('Accept All')",
    "button:has-text('Accept Cookies')",
    "button:has-text('پذیرش همه')",
    "button:has-text('موافقم')",
]
