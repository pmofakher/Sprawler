"""Site accessibility and soft-down (maintenance) detection."""

import asyncio
import socket
from typing import Tuple
from urllib.parse import urlparse

import httpx

from crawler.core.constants import DEFAULT_USER_AGENT, MAINTENANCE_KEYWORDS


async def check_dns(hostname: str) -> bool:
    """Performs non-blocking DNS resolution in an executor thread pool."""
    loop = asyncio.get_running_loop()
    try:
        # socket.getaddrinfo is blocking, run in default thread executor
        await loop.run_in_executor(None, socket.getaddrinfo, hostname, 80)
        return True
    except (socket.gaierror, socket.herror, Exception):
        return False


def is_soft_down(html_text: str) -> bool:
    """Detects whether a 200 OK response is actually an under-maintenance or empty placeholder page."""
    if not html_text or len(html_text.strip()) < 50:
        return True

    lower_html = html_text.lower()
    for keyword in MAINTENANCE_KEYWORDS:
        if keyword in lower_html:
            return True

    return False


async def check_site_health(url: str, timeout: float = 10.0) -> Tuple[bool, str]:
    """Executes a multi-layer pre-crawl health check (DNS -> lightweight HEAD/GET).

    Returns:
      (is_healthy, status_detail)
    """
    parsed = urlparse(url)
    hostname = parsed.netloc.split(":")[0]

    # Layer 1: DNS Resolution
    dns_ok = await check_dns(hostname)
    if not dns_ok:
        return False, f"DNS resolution failed for host '{hostname}'"

    # Layer 2: HTTP HEAD / GET
    headers = {"User-Agent": DEFAULT_USER_AGENT}
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, verify=False) as client:
            try:
                resp = await client.head(url, headers=headers)
                if resp.status_code >= 500:
                    return False, f"Server returned 5xx status ({resp.status_code})"
                return True, f"HTTP HEAD healthy ({resp.status_code})"
            except (httpx.RequestError, httpx.HTTPStatusError):
                # Fallback to lightweight GET
                resp = await client.get(url, headers=headers)
                if resp.status_code >= 500:
                    return False, f"Server returned 5xx status ({resp.status_code})"
                if is_soft_down(resp.text):
                    return False, "Target site is in soft-down (maintenance) state"
                return True, f"HTTP GET healthy ({resp.status_code})"
    except Exception as exc:
        return False, f"Connection or TLS handshake failed: {exc}"
