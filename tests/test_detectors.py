"""Unit tests for redirect, CAPTCHA, WAF, and site downtime detection."""

import pytest
from crawler.detect.captcha import detect_captcha
from crawler.detect.redirect import (
    classify_redirect_hop,
    detect_js_redirect,
    detect_meta_refresh,
)
from crawler.detect.site_down import is_soft_down
from crawler.detect.waf import detect_waf
from crawler.domain.enums import CaptchaType, RedirectType, WafVendor


def test_detect_turnstile_captcha():
    html = """
    <html><body>
        <div class="cf-turnstile" data-sitekey="0x4AAAAAA"></div>
        <script src="https://challenges.cloudflare.com/turnstile/v0/api.js"></script>
    </body></html>
    """
    assert detect_captcha(html) == CaptchaType.TURNSTILE


def test_detect_recaptcha():
    html = """
    <html><body>
        <div class="g-recaptcha" data-sitekey="6Le-wvkSAAAAAPBnm3vx0xSVNqyGhPUQWvsYYTXR"></div>
        <script src="https://www.google.com/recaptcha/api.js"></script>
    </body></html>
    """
    assert detect_captcha(html) == CaptchaType.RECAPTCHA_V2


def test_detect_persian_captcha_keywords():
    html = "<html><body><p>لطفا جهت ادامه تایید کنید که من ربات نیستم</p></body></html>"
    assert detect_captcha(html, status_code=403) == CaptchaType.UNKNOWN


def test_waf_detection_cloudflare():
    headers = {"Server": "cloudflare", "cf-ray": "8d3e23214abc-IAD"}
    assert detect_waf(headers) == WafVendor.CLOUDFLARE


def test_waf_detection_arvancloud():
    headers = {"ar-request-id": "123456789", "Server": "ArvanCloud"}
    assert detect_waf(headers) == WafVendor.ARVANCLOUD


def test_soft_down_detection():
    # Empty body
    assert is_soft_down("")
    assert is_soft_down("   ")

    # Maintenance message (Persian)
    maintenance_fa = "<html><body><h1>سایت در حال تعمیر و بروزرسانی است. به زودی برمی‌گردیم.</h1></body></html>"
    assert is_soft_down(maintenance_fa)

    # Active page
    active_html = "<html><body><h1>درباره ما</h1><p>این شرکت در سال ۱۳۹۵ تاسیس شد و خدمات متنوعی ارائه میدهد.</p></body></html>"
    assert not is_soft_down(active_html)


def test_meta_refresh_detection():
    html = '<meta http-equiv="refresh" content="5;url=/new-page.html">'
    target, delay = detect_meta_refresh(html, "https://example.com/old")
    assert target == "https://example.com/new-page.html"
    assert delay == 5


def test_js_redirect_detection():
    html = '<script>window.location.href = "/dashboard";</script>'
    target = detect_js_redirect(html, "https://example.com/")
    assert target == "https://example.com/dashboard"


def test_redirect_hop_classification():
    # Canonical redirect
    can_type = classify_redirect_hop("http://example.com/", "https://example.com/")
    assert can_type == RedirectType.CANONICAL_REDIRECT

    # External redirect
    ext_type = classify_redirect_hop("https://example.com/", "https://otherdomain.com/")
    assert ext_type == RedirectType.EXTERNAL_REDIRECT

    # Standard 301 redirect
    http_301 = classify_redirect_hop("https://example.com/old", "https://example.com/new", status_code=301)
    assert http_301 == RedirectType.HTTP_3XX
