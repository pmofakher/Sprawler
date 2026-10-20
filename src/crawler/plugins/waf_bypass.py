"""WAF bypass extension point and plug-in interface."""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol
from crawler.domain.enums import WafVendor


@dataclass
class WafBypassResult:
    """Outcome of a WAF challenge mitigation attempt."""
    bypassed: bool
    headers: Dict[str, str] = None
    cookies: Dict[str, str] = None
    error: Optional[str] = None


class WafHandler(Protocol):
    """Protocol interface for handling WAF challenges (e.g. FlareSolverr, residential proxy rotation)."""

    async def handle_challenge(
        self,
        vendor: WafVendor,
        url: str,
        current_headers: Dict[str, str],
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> WafBypassResult:
        """Attempts to negotiate or bypass a WAF challenge."""
        ...


class NoOpWafHandler:
    """Default no-op handler. Detection only per specification."""

    async def handle_challenge(
        self,
        vendor: WafVendor,
        url: str,
        current_headers: Dict[str, str],
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> WafBypassResult:
        """TODO: Integrate FlareSolverr, TLS fingerprint impersonation, or rotating residential proxies.

        Example implementation:
            session = await flaresolverr.get_clearance_cookie(url)
            return WafBypassResult(bypassed=True, cookies=session.cookies, headers=session.headers)
        """
        return WafBypassResult(
            bypassed=False,
            headers={},
            cookies={},
            error=f"NoOpWafHandler active. WAF {vendor} detected; challenge bypass not configured.",
        )
