"""Unit tests for URL normalization, validation, and SSRF guard."""

import pytest
from crawler.core.exceptions import (
    InvalidUrlSchemeException,
    SSRFSecurityException,
    UrlNormalizationException,
)
from crawler.frontier.normalizer import (
    get_registrable_domain,
    is_in_domain_scope,
    normalize_url,
    validate_ssrf,
)


def test_normalize_url_basic():
    raw = "HTTP://Example.COM:80/about//team/?b=2&a=1#section3"
    expected = "http://example.com/about/team/?a=1&b=2"
    assert normalize_url(raw) == expected


def test_normalize_url_strip_tracking_params():
    raw = "https://example.com/news?utm_source=google&id=42&fbclid=xyz123"
    expected = "https://example.com/news?id=42"
    assert normalize_url(raw) == expected


def test_normalize_url_default_scheme():
    raw = "example.com/contact"
    expected = "https://example.com/contact"
    assert normalize_url(raw) == expected


def test_normalize_url_relative_resolution():
    base = "https://example.com/blog/article-1"
    relative = "../about-us"
    expected = "https://example.com/about-us"
    assert normalize_url(relative, base_url=base) == expected


def test_prohibited_schemes():
    with pytest.raises(InvalidUrlSchemeException):
        normalize_url("javascript:alert(1)")

    with pytest.raises(InvalidUrlSchemeException):
        normalize_url("mailto:info@example.com")

    with pytest.raises(InvalidUrlSchemeException):
        normalize_url("file:///etc/passwd")


def test_ssrf_protection():
    with pytest.raises(SSRFSecurityException):
        normalize_url("http://127.0.0.1/admin")

    with pytest.raises(SSRFSecurityException):
        normalize_url("http://localhost:8080/metrics")

    with pytest.raises(SSRFSecurityException):
        normalize_url("http://192.168.1.1/router")

    with pytest.raises(SSRFSecurityException):
        normalize_url("http://10.0.0.5/api")


def test_domain_scope_checks():
    root = "example.com"

    # Same domain
    assert is_in_domain_scope("https://example.com/about", root, allow_subdomains=True)
    assert is_in_domain_scope("https://www.example.com/about", root, allow_subdomains=True)

    # Subdomain allowed
    assert is_in_domain_scope("https://blog.example.com/post", root, allow_subdomains=True)

    # Subdomain disallowed
    assert not is_in_domain_scope("https://blog.example.com/post", root, allow_subdomains=False)

    # External domain
    assert not is_in_domain_scope("https://external.org/page", root, allow_subdomains=True)


def test_get_registrable_domain():
    assert get_registrable_domain("https://sub.sub2.plantlandtehran.com/about") == "plantlandtehran.com"
    assert get_registrable_domain("http://example.co.uk/page") == "example.co.uk"
