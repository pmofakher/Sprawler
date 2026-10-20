"""Plugins package containing CAPTCHA and WAF solver interfaces."""

from crawler.plugins.captcha_solver import (
    CaptchaSolver,
    NoOpCaptchaSolver,
    SolveResult,
)
from crawler.plugins.waf_bypass import (
    NoOpWafHandler,
    WafBypassResult,
    WafHandler,
)

__all__ = [
    "CaptchaSolver",
    "NoOpCaptchaSolver",
    "SolveResult",
    "WafHandler",
    "NoOpWafHandler",
    "WafBypassResult",
]
