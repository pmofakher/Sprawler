"""Detection classifiers for redirects, CAPTCHA, WAF, and site downtime."""

from crawler.detect.captcha import detect_captcha
from crawler.detect.redirect import classify_redirect_hop, detect_js_redirect, detect_meta_refresh
from crawler.detect.site_down import check_dns, check_site_health, is_soft_down
from crawler.detect.waf import detect_waf

__all__ = [
    "detect_captcha",
    "classify_redirect_hop",
    "detect_meta_refresh",
    "detect_js_redirect",
    "check_dns",
    "is_soft_down",
    "check_site_health",
    "detect_waf",
]
