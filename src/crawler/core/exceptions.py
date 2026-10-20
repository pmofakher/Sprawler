"""Custom exception hierarchy for the crawler service."""

class CrawlerException(Exception):
    """Base exception for all sprawler domain errors."""
    pass


class SSRFSecurityException(CrawlerException):
    """Raised when a URL attempts to target a private, loopback, or unsafe network address."""
    pass


class InvalidUrlSchemeException(CrawlerException):
    """Raised when a URL has an unsupported or prohibited scheme."""
    pass


class UrlNormalizationException(CrawlerException):
    """Raised when URL parsing or normalization fails."""
    pass


class CircuitBreakerOpenException(CrawlerException):
    """Raised when requests to a domain are blocked because its circuit breaker is OPEN."""
    pass


class SiteDownException(CrawlerException):
    """Raised when a target site is unreachable via DNS, TCP/TLS, or returns soft-down maintenance."""
    pass


class RobotsDisallowedException(CrawlerException):
    """Raised when robots.txt strictly forbids crawling a requested path."""
    pass


class RateLimitExceededException(CrawlerException):
    """Raised when the target host's rate limit or crawl-delay is violated."""
    pass


class FetchTimeoutException(CrawlerException):
    """Raised when HTTP or Browser fetching times out."""
    pass


class StorageException(CrawlerException):
    """Raised when persisting crawl artifacts to disk or database fails."""
    pass


class FrontierException(CrawlerException):
    """Raised when queue or persistent database operations fail in the crawl frontier."""
    pass
