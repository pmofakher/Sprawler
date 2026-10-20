"""URL normalization, validation, and SSRF security protection."""

import ipaddress
import socket
from typing import Optional, Set, Tuple
from urllib.parse import parse_qsl, unquote, urlencode, urljoin, urlparse, urlunparse

import tldextract

from crawler.core.constants import (
    ALLOWED_SCHEMES,
    REJECTED_SCHEMES,
    TRACKING_PARAMS,
)
from crawler.core.exceptions import (
    InvalidUrlSchemeException,
    SSRFSecurityException,
    UrlNormalizationException,
)

_extract = tldextract.TLDExtract()


def is_private_ip(ip_str: str) -> bool:
    """Verifies whether an IP string belongs to private, loopback, link-local, or reserved networks."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        )
    except ValueError:
        return False


def validate_ssrf(hostname: str) -> None:
    """Guards against Server-Side Request Forgery by disallowing localhost and private network addresses."""
    cleaned_host = hostname.strip("[]")

    # Direct IP string check
    if is_private_ip(cleaned_host):
        raise SSRFSecurityException(f"Target host '{hostname}' resolves to private/loopback IP address.")

    # Localhost alias check
    if cleaned_host.lower() in {"localhost", "localhost.localdomain", "broadcasthost"}:
        raise SSRFSecurityException(f"Target host '{hostname}' is a forbidden local loopback alias.")


def get_registrable_domain(url: str) -> str:
    """Extracts the registered domain (e.g. 'plantlandtehran.com' from 'sub.plantlandtehran.com')."""
    ext = _extract(url)
    dom = getattr(ext, "top_domain_under_public_suffix", None) or getattr(ext, "registered_domain", None)
    if dom:
        return dom.lower()
    return ext.domain.lower()


def is_in_domain_scope(url: str, root_registrable_domain: str, allow_subdomains: bool = True) -> bool:
    """Determines whether the given URL falls strictly inside the allowed crawl domain scope."""
    if not url:
        return False
    parsed = urlparse(url)
    if not parsed.netloc:
        return False

    url_host = parsed.netloc.split(":")[0].lower()
    ext = _extract(url)
    dom = getattr(ext, "top_domain_under_public_suffix", None) or getattr(ext, "registered_domain", None)
    url_reg_domain = dom.lower() if dom else ext.domain.lower()

    if url_reg_domain != root_registrable_domain.lower():
        return False

    if not allow_subdomains:
        # Host must match exact registrable domain (or www. equivalent)
        clean_url_host = url_host[4:] if url_host.startswith("www.") else url_host
        clean_root = root_registrable_domain[4:] if root_registrable_domain.startswith("www.") else root_registrable_domain
        return clean_url_host == clean_root

    return True


def normalize_url(url: str, base_url: Optional[str] = None) -> str:
    """Normalizes an arbitrary URL according to production crawler standards.

    Actions:
      - Resolves relative URLs against base_url
      - Enforces allowed schemes (http/https) and blocks unsafe schemes
      - Strips URL fragments (#)
      - Lowercases scheme and hostname
      - Normalizes default ports (80/443)
      - Strips tracking query parameters (utm_*, etc.)
      - Sorts query parameters deterministically
      - Decodes unnecessary percent-encodings
      - Collapses consecutive slashes in the path
    """
    if not url or not isinstance(url, str):
        raise UrlNormalizationException("URL cannot be empty or non-string.")

    clean_raw = url.strip()

    # Pre-check scheme against explicit rejects
    scheme_candidate = clean_raw.split(":", 1)[0].lower() if ":" in clean_raw else ""
    if scheme_candidate in REJECTED_SCHEMES:
        raise InvalidUrlSchemeException(f"Prohibited URL scheme: '{scheme_candidate}'")

    # If relative, resolve against base_url
    if base_url:
        clean_raw = urljoin(base_url, clean_raw)
    elif "://" not in clean_raw and not clean_raw.startswith("//"):
        # Default to https
        clean_raw = "https://" + clean_raw

    parsed = urlparse(clean_raw)

    scheme = parsed.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise InvalidUrlSchemeException(f"Unsupported scheme '{scheme}'. Only HTTP/HTTPS allowed.")

    netloc = parsed.netloc.lower()
    if not netloc:
        raise UrlNormalizationException(f"URL missing valid network location/host: {url}")

    # Remove standard ports
    if ":" in netloc:
        host, port = netloc.split(":", 1)
        if (scheme == "http" and port == "80") or (scheme == "https" and port == "443"):
            netloc = host
    else:
        host = netloc

    # IDNA encode/decode hostname to support Persian/IDN hostnames safely
    try:
        host_idna = host.encode("idna").decode("ascii")
        if ":" in netloc:
            _, port_str = netloc.split(":", 1)
            netloc = f"{host_idna}:{port_str}"
        else:
            netloc = host_idna
    except Exception:
        # Fallback to existing host if IDNA conversion fails
        pass

    # SSRF guard on parsed host
    validate_ssrf(host)

    # Normalize path: collapse duplicate slashes while keeping single root /
    path = parsed.path
    if not path:
        path = "/"
    else:
        # Collapse multiple consecutive slashes
        while "//" in path:
            path = path.replace("//", "/")

    # Unquote and re-normalize Persian percent-encodings in path
    try:
        path = unquote(path)
    except Exception:
        pass

    # Filter and sort query parameters
    query = ""
    if parsed.query:
        params = parse_qsl(parsed.query, keep_blank_values=False)
        filtered_params = [
            (k, v) for k, v in params if k.lower() not in TRACKING_PARAMS
        ]
        # Sort query keys for deterministic uniqueness
        filtered_params.sort(key=lambda x: (x[0], x[1]))
        query = urlencode(filtered_params)

    # Reconstruct normalized URL (fragment is omitted)
    normalized = urlunparse((scheme, netloc, path, "", query, ""))
    return normalized
