"""CAPTCHA challenge detection (reCAPTCHA, hCaptcha, Turnstile, Cloudflare)."""

from typing import Optional
from bs4 import BeautifulSoup

from crawler.core.constants import CAPTCHA_KEYWORDS
from crawler.domain.enums import CaptchaType


def detect_captcha(
    html_text: str,
    status_code: int = 200,
    headers: Optional[dict] = None,
) -> Optional[CaptchaType]:
    """Inspects response status, headers, and DOM content for bot challenges.

    Returns:
      CaptchaType if a challenge is identified, otherwise None.
    """
    if not html_text:
        if status_code in (403, 429, 503):
            return CaptchaType.UNKNOWN
        return None

    lower_html = html_text.lower()

    # 1. Cloudflare Turnstile
    if (
        "challenges.cloudflare.com/turnstile" in lower_html
        or "cf-turnstile" in lower_html
        or 'class="cf-turnstile"' in lower_html
    ):
        return CaptchaType.TURNSTILE

    # 2. Google reCAPTCHA
    if (
        "google.com/recaptcha" in lower_html
        or "g-recaptcha" in lower_html
        or "recaptcha/api.js" in lower_html
    ):
        if "recaptcha/api.js?render=" in lower_html or "grecaptcha.execute" in lower_html:
            return CaptchaType.RECAPTCHA_V3
        return CaptchaType.RECAPTCHA_V2

    # 3. hCaptcha
    if (
        "hcaptcha.com" in lower_html
        or "h-captcha" in lower_html
        or "data-sitekey" in lower_html and "hcaptcha" in lower_html
    ):
        return CaptchaType.HCAPTCHA

    # 4. Cloudflare Managed Challenge interstitial
    if (
        "just a moment..." in lower_html
        or "checking your browser" in lower_html
        or "cf-browser-verification" in lower_html
        or "ray id:" in lower_html and status_code in (403, 503)
    ):
        return CaptchaType.CLOUDFLARE_CHALLENGE

    # 5. Challenge status code (403, 429, 503) + keyword signals
    if status_code in (403, 429, 503):
        for kw in CAPTCHA_KEYWORDS:
            if kw in lower_html:
                return CaptchaType.UNKNOWN

    # 6. Abnormally short body with security check keyword
    if len(html_text) < 2000:
        for kw in CAPTCHA_KEYWORDS:
            if kw in lower_html:
                return CaptchaType.UNKNOWN

    return None
