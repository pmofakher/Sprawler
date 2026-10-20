"""CAPTCHA solver extension point and plug-in interface."""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol
from crawler.domain.enums import CaptchaType


@dataclass
class SolveResult:
    """Represents the outcome of a CAPTCHA solver attempt."""
    solved: bool
    solution_token: Optional[str] = None
    cookies: Dict[str, str] = None
    error: Optional[str] = None


class CaptchaSolver(Protocol):
    """Protocol interface for external CAPTCHA solving services (e.g. 2Captcha, CapSolver)."""

    async def solve(
        self,
        captcha_type: CaptchaType,
        url: str,
        sitekey: Optional[str] = None,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> SolveResult:
        """Attempts to solve a detected CAPTCHA challenge."""
        ...


class NoOpCaptchaSolver:
    """Default no-op solver. Detection only per specification."""

    async def solve(
        self,
        captcha_type: CaptchaType,
        url: str,
        sitekey: Optional[str] = None,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> SolveResult:
        """TODO: Integrate external 2Captcha, Anti-Captcha, or local ML solver here.

        Example implementation:
            client = TwoCaptchaClient(api_key=...)
            res = await client.solve_recaptcha(sitekey=sitekey, page_url=url)
            return SolveResult(solved=True, solution_token=res.token)
        """
        return SolveResult(
            solved=False,
            solution_token=None,
            cookies={},
            error=f"NoOpCaptchaSolver active. CAPTCHA {captcha_type} detected but solver not configured.",
        )
