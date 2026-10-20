"""Persian text normalization pipeline.

Provides deterministic, pure-Python transformations for standardizing Persian
strings, unifying Arabic characters, cleaning directional marks, normalizing digits,
and properly handling Zero-Width Non-Joiners (ZWNJ).
"""

import re
import unicodedata
from typing import Literal

# Character mapping tables
ARABIC_TO_PERSIAN_CHARS = {
    ord("ي"): "ی",
    ord("ى"): "ی",
    ord("ك"): "ک",
    ord("ؤ"): "و",
    ord("إ"): "ا",
    ord("أ"): "ا",
    ord("ء"): "",  # Remove stand-alone hamza if non-letter
    ord("ة"): "ه",
}

# Arabic & Persian diacritics / harakat range: U+064B through U+065F, and U+0670
DIACRITICS_REGEX = re.compile(r"[\u064B-\u065F\u0670]")

# Tatweel (kashida): U+0640
TATWEEL_REGEX = re.compile(r"\u0640")

# RTL/LTR bidi direction control characters: U+200E, U+200F, U+202A-U+202E, U+2066-U+2069
BIDI_CHARS_REGEX = re.compile(r"[\u200E\u200F\u202A-\u202E\u2066-\u2069]")

# Digit mapping tables
PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
LATIN_DIGITS = "0123456789"

TO_LATIN_DIGITS_MAP = str.maketrans(
    PERSIAN_DIGITS + ARABIC_DIGITS,
    LATIN_DIGITS * 2,
)

TO_PERSIAN_DIGITS_MAP = str.maketrans(
    LATIN_DIGITS + ARABIC_DIGITS,
    PERSIAN_DIGITS * 2,
)

# Whitespace and ZWNJ constants
ZWNJ = "\u200c"
MULTIPLE_ZWNJ_REGEX = re.compile(r"\u200c{2,}")
ZWNJ_NEAR_SPACES_REGEX = re.compile(r"\s+\u200c|\u200c\s+")
MULTIPLE_SPACES_REGEX = re.compile(r"[ \t\f\v]+")
MULTIPLE_NEWLINES_REGEX = re.compile(r"\n{3,}")


def remove_bidi_controls(text: str) -> str:
    """Strips invisible bidirectional formatting controls."""
    if not text:
        return ""
    return BIDI_CHARS_REGEX.sub("", text)


def remove_diacritics(text: str) -> str:
    """Removes Arabic/Persian short vowels (harakat) and tatweel."""
    if not text:
        return ""
    no_tatweel = TATWEEL_REGEX.sub("", text)
    return DIACRITICS_REGEX.sub("", no_tatweel)


def normalize_arabic_characters(text: str) -> str:
    """Maps Arabic Kaf, Yeh, and related characters to Persian equivalents."""
    if not text:
        return ""
    return text.translate(ARABIC_TO_PERSIAN_CHARS)


def normalize_zwnj(text: str) -> str:
    """Collapses consecutive ZWNJs and removes superfluous ZWNJs adjacent to whitespace."""
    if not text:
        return ""
    # Collapse multiple consecutive half-spaces into one
    cleaned = MULTIPLE_ZWNJ_REGEX.sub(ZWNJ, text)
    # Remove half-space if it is preceded or followed by a regular space
    cleaned = ZWNJ_NEAR_SPACES_REGEX.sub(" ", cleaned)
    return cleaned


def normalize_digits(text: str, target: Literal["latin", "persian", "keep"] = "latin") -> str:
    """Converts numerals across Persian, Arabic, and Latin representations."""
    if not text or target == "keep":
        return text
    if target == "latin":
        return text.translate(TO_LATIN_DIGITS_MAP)
    elif target == "persian":
        return text.translate(TO_PERSIAN_DIGITS_MAP)
    return text


def collapse_whitespace(text: str) -> str:
    """Collapses horizontal spaces and excessive newlines into clean structure."""
    if not text:
        return ""
    # Collapse consecutive spaces and tabs
    cleaned = MULTIPLE_SPACES_REGEX.sub(" ", text)
    # Limit excessive consecutive newlines to at most two (paragraph separation)
    cleaned = MULTIPLE_NEWLINES_REGEX.sub("\n\n", cleaned)
    return cleaned.strip()


def normalize_persian_text(
    text: str,
    target_digits: Literal["latin", "persian", "keep"] = "latin",
    apply_nfkc: bool = True,
) -> str:
    """Executes the full canonical Persian normalization pipeline.

    Steps:
      1. Unicode NFKC normalization
      2. Strip bidirectional control characters
      3. Map Arabic glyphs to Persian
      4. Strip diacritics and tatweel
      5. Standardize ZWNJ usage
      6. Normalize numbers
      7. Collapse whitespace and trim
    """
    if not text:
        return ""

    result = text
    if apply_nfkc:
        result = unicodedata.normalize("NFKC", result)

    result = remove_bidi_controls(result)
    result = normalize_arabic_characters(result)
    result = remove_diacritics(result)
    result = normalize_zwnj(result)
    result = normalize_digits(result, target=target_digits)
    result = collapse_whitespace(result)

    return result
