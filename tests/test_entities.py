"""Unit tests for Iranian business entity extractors."""

import pytest
from crawler.extract.entities import (
    extract_emails,
    extract_geo_coordinates,
    extract_phones,
    extract_social_links,
    extract_working_hours,
    normalize_phone_number,
)


def test_phone_extraction_and_normalization():
    text = """
    شماره همراه ما ۰۹۱۲۳۴۵۶۷۸۹ و 09351112233 می باشد.
    تلفن ثابت دفتر مرکزی: ۰۲۱-۸۸۷۷۶۶۵۵ و یا 02188990011.
    کد شهرستان: 031-33445566
    """
    phones = extract_phones(text, source_url="https://example.com/contact")
    phone_values = [p.value for p in phones]

    # Mobile normalized
    assert "+989123456789" in phone_values
    assert "+989351112233" in phone_values

    # Landlines normalized
    assert "+982188776655" in phone_values
    assert "+982188990011" in phone_values
    assert "+983133445566" in phone_values


def test_email_extraction():
    text = "ارتباط با مدیر: info@plantlandtehran.com و پشتیبانی: support@example.co.ir."
    emails = extract_emails(text, source_url="https://example.com/about")
    email_values = [e.value for e in emails]

    assert "info@plantlandtehran.com" in email_values
    assert "support@example.co.ir" in email_values


def test_social_links_extraction():
    links = [
        "https://www.instagram.com/plantlandtehran/",
        "https://t.me/plantland_channel",
        "https://wa.me/989121112233",
        "https://github.com/someuser",
    ]
    socials = extract_social_links(links, source_url="https://example.com/")
    platforms = {s.platform: s.url for s in socials}

    assert "instagram" in platforms
    assert "telegram" in platforms
    assert "whatsapp" in platforms


def test_geo_extraction():
    url = "https://maps.google.com/?q=35.6892,51.3890"
    geo = extract_geo_coordinates(url, source_url="https://example.com/contact")
    assert geo is not None
    assert geo.latitude == 35.6892
    assert geo.longitude == 51.3890


def test_working_hours_extraction():
    text = "ساعات کاری: شنبه تا چهارشنبه ۹ الی ۱۸ و پنجشنبه ها تا ساعت ۱۳"
    hours = extract_working_hours(text, source_url="https://example.com/contact")
    assert len(hours) > 0
    assert "شنبه تا چهارشنبه" in hours[0].text
