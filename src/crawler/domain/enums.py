"""Domain enumerations for crawling, classification, and status reporting."""

from enum import Enum


class RenderType(str, Enum):
    """Classification of how a page is rendered."""
    STATIC = "static"
    SSR = "ssr"
    CSR = "csr"


class PageType(str, Enum):
    """Categorization of page content for business intelligence."""
    HOME = "home"
    ABOUT = "about"
    CONTACT = "contact"
    FAQ = "faq"
    BLOG = "blog"
    SERVICES = "services"
    POLICIES = "policies"
    OTHER = "other"


class SkipReason(str, Enum):
    """Explicit rationale for why a discovered URL was not crawled."""
    PAGINATION = "pagination"
    PRODUCT = "product"
    ROBOTS = "robots"
    EXTERNAL = "external"
    DUPLICATE = "duplicate"
    DISALLOWED_SCHEME = "disallowed_scheme"
    LOGIN_WALL = "login_wall"
    MAX_DEPTH_EXCEEDED = "max_depth_exceeded"
    CIRCUIT_OPEN = "circuit_open"


class CrawlStatus(str, Enum):
    """Overall status of a site crawl."""
    OK = "ok"
    PARTIAL = "partial"
    SITE_DOWN = "site_down"
    BLOCKED = "blocked"


class RedirectType(str, Enum):
    """Mechanics behind an observed URL redirect."""
    NONE = "none"
    HTTP_3XX = "http_3xx"
    META_REFRESH = "meta_refresh"
    JS_REDIRECT = "js_redirect"
    CANONICAL_REDIRECT = "canonical_redirect"
    EXTERNAL_REDIRECT = "external_redirect"


class CaptchaType(str, Enum):
    """Detected CAPTCHA challenge subtype."""
    RECAPTCHA_V2 = "recaptcha_v2"
    RECAPTCHA_V3 = "recaptcha_v3"
    HCAPTCHA = "hcaptcha"
    TURNSTILE = "turnstile"
    CLOUDFLARE_CHALLENGE = "cloudflare_challenge"
    UNKNOWN = "unknown"


class WafVendor(str, Enum):
    """Fingerprinted WAF / anti-bot vendor."""
    NONE = "none"
    CLOUDFLARE = "cloudflare"
    AKAMAI = "akamai"
    SUCURI = "sucuri"
    IMPERVA = "imperva"
    ARVANCLOUD = "arvancloud"
    DDOS_GUARD = "ddos_guard"
    UNKNOWN = "unknown"


class FrontierStatus(str, Enum):
    """Queue lifecycle status for a URL item in the persistent frontier."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class SourceType(str, Enum):
    """Origin source of extracted textual chunk."""
    HTML = "html"
    PDF = "pdf"
    OCR = "ocr"
    XHR_JSON = "xhr_json"


class CircuitState(str, Enum):
    """State machine states for domain resilience circuit breaker."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"
