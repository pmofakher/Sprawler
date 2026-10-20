"""Unit tests for the Persian text normalization pipeline."""

import pytest
from crawler.text.persian import (
    normalize_arabic_characters,
    normalize_digits,
    normalize_persian_text,
    normalize_zwnj,
    remove_bidi_controls,
    remove_diacritics,
)


def test_arabic_character_normalization():
    # Arabic kaf (ك) -> Persian (ک), Arabic yeh (ي, ى) -> Persian (ی)
    raw = "شركت بازرگاني و فناوري اطلاعات و ارتباطات"
    expected = "شرکت بازرگانی و فناوری اطلاعات و ارتباطات"
    assert normalize_arabic_characters(raw) == expected


def test_diacritics_and_tatweel_removal():
    # Remove harakat (tanwin, damma, etc.) and tatweel
    raw = "سَــــلامٌ عَلَيْكُمْ"
    expected = "سلام علیکم"
    # remove_diacritics keeps the Arabic characters intact; full normalization maps them to Persian
    assert remove_diacritics(raw) == "سلام عليكم"


def test_zwnj_normalization():
    # Multiple ZWNJ collapsed, ZWNJ adjacent to spaces cleaned
    raw = "می\u200c\u200cرود و می \u200cآید"
    normalized = normalize_zwnj(raw)
    assert "\u200c\u200c" not in normalized
    assert " \u200c" not in normalized


def test_digit_normalization():
    # Persian/Arabic digits converted to Latin digits
    persian_digits = "شماره: ۰۹۱۲۳۴۵۶۷۸۹ و کد ٠١٢٣"
    to_latin = normalize_digits(persian_digits, target="latin")
    assert to_latin == "شماره: 09123456789 و کد 0123"

    # Latin digits converted to Persian digits
    latin_digits = "12345"
    to_persian = normalize_digits(latin_digits, target="persian")
    assert to_persian == "۱۲۳۴۵"


def test_bidi_controls_removal():
    # Strip invisible directional marks
    raw = "Hello\u200e \u200fWorld\u202a!"
    cleaned = remove_bidi_controls(raw)
    assert "\u200e" not in cleaned
    assert "\u200f" not in cleaned
    assert "\u202a" not in cleaned


def test_full_persian_pipeline():
    raw = "  شركت\u200e ما با شماره\u200c\u200c ۰۲۱-۸۸۷۷۶۶۵۵   فعّال است.   \n\n\n  "
    result = normalize_persian_text(raw, target_digits="latin")
    assert "شرکت" in result
    assert "021-88776655" in result
    assert "فعال" in result
    assert "\u200e" not in result
    assert "\n\n\n" not in result
