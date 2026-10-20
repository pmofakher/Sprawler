"""Rule-based Iranian business entity extraction (phones, emails, addresses, social, geo, hours)."""

import re
from typing import List, Optional, Set, Tuple
from urllib.parse import parse_qs, unquote, urlparse

from crawler.domain.models import (
    AddressEntity,
    EmailEntity,
    GeoEntity,
    PhoneEntity,
    SocialEntity,
    WorkingHoursEntity,
)
from crawler.text.persian import normalize_digits

# Iranian Mobile regex: 09xx xxx xxxx, +989xx xxx xxxx, 00989xx xxx xxxx
IRAN_MOBILE_REGEX = re.compile(
    r"(?:\+98|0098|0)?9\d{2}[-\s]?\d{3}[-\s]?\d{4}\b"
)

# Iranian Landline regex: e.g. 021-xxxxxxxx, (021)xxxxxxxx, 021xxxxxxxx
IRAN_LANDLINE_REGEX = re.compile(
    r"(?:\+98|0098|0)?(?:21|26|31|41|51|71|81|11|13|17|23|24|25|28|34|35|38|44|45|54|56|58|61|66|74|76|77|83|84|86|87)[-\s]?\d{4}[-\s]?\d{4}\b"
)

# General phone regex for international or 4-digit/5-digit business lines (e.g. 1820, 1500)
SHORT_PHONE_REGEX = re.compile(r"\b(?:1[0-9]{3}|[2-9][0-9]{3,4})\b")

# Email regex (avoiding image files like icon@2x.png)
EMAIL_REGEX = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"
)

# Google Maps coordinates pattern
GEO_COORDS_REGEX = re.compile(
    r"[@/]([-+]?[0-9]{1,2}\.[0-9]{4,10})[,\s]+([-+]?[0-9]{1,3}\.[0-9]{4,10})"
)

# Working hours regex triggers
WORKING_HOURS_REGEX = re.compile(
    r"(?:ساعت کار|ساعات کاری|شنبه تا [^\n,]+|[0-9]{1,2}(?::[0-9]{2})?\s*(?:الی|تا|-)\s*[0-9]{1,2}(?::[0-9]{2})?|working hours|opening hours)",
    re.IGNORECASE,
)

# Social platforms mapping
KNOWN_SOCIAL_DOMAINS = {
    "instagram.com": "instagram",
    "t.me": "telegram",
    "telegram.me": "telegram",
    "linkedin.com": "linkedin",
    "twitter.com": "twitter",
    "x.com": "twitter",
    "facebook.com": "facebook",
    "wa.me": "whatsapp",
    "api.whatsapp.com": "whatsapp",
    "aparat.com": "aparat",
    "eitaa.com": "eitaa",
    "ble.ir": "bale",
    "rubika.ir": "rubika",
    "youtube.com": "youtube",
}


def normalize_phone_number(raw_phone: str) -> str:
    """Normalizes phone string to clean Iranian format: +98... or 0..."""
    # Convert any Persian/Arabic digits to Latin digits first
    digits_only = re.sub(r"[^\d+]", "", normalize_digits(raw_phone, target="latin"))
    if digits_only.startswith("0098"):
        digits_only = "+98" + digits_only[4:]
    elif digits_only.startswith("09") and len(digits_only) == 11:
        digits_only = "+98" + digits_only[1:]
    elif digits_only.startswith("0") and len(digits_only) >= 10:
        digits_only = "+98" + digits_only[1:]
    return digits_only


def extract_phones(text: str, source_url: str) -> List[PhoneEntity]:
    """Extracts and normalizes unique phone numbers from text."""
    if not text:
        return []

    latin_text = normalize_digits(text, target="latin")
    phones: List[PhoneEntity] = []
    seen: Set[str] = set()

    # Match mobiles
    for match in IRAN_MOBILE_REGEX.finditer(latin_text):
        num = normalize_phone_number(match.group(0))
        if num and num not in seen:
            seen.add(num)
            phones.append(PhoneEntity(value=num, source_url=source_url))

    # Match landlines
    for match in IRAN_LANDLINE_REGEX.finditer(latin_text):
        num = normalize_phone_number(match.group(0))
        if num and num not in seen:
            seen.add(num)
            phones.append(PhoneEntity(value=num, source_url=source_url))

    return phones


def extract_emails(text: str, source_url: str) -> List[EmailEntity]:
    """Extracts valid email addresses from text."""
    if not text:
        return []

    emails: List[EmailEntity] = []
    seen: Set[str] = set()

    for match in EMAIL_REGEX.finditer(text):
        val = match.group(0).lower()
        # Filter out common false positives (e.g. image filenames)
        if any(val.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"]):
            continue
        if val not in seen:
            seen.add(val)
            emails.append(EmailEntity(value=val, source_url=source_url))

    return emails


def extract_social_links(links: List[str], source_url: str) -> List[SocialEntity]:
    """Detects social media profiles from hyperlinks."""
    socials: List[SocialEntity] = []
    seen: Set[str] = set()

    for link in links:
        if not link or not link.startswith("http"):
            continue
        parsed = urlparse(link)
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]

        for domain, platform in KNOWN_SOCIAL_DOMAINS.items():
            if domain in netloc:
                if link not in seen:
                    seen.add(link)
                    socials.append(
                        SocialEntity(
                            platform=platform,
                            url=link,
                            source_url=source_url,
                        )
                    )
                break

    return socials


def extract_geo_coordinates(text_or_url: str, source_url: str) -> Optional[GeoEntity]:
    """Extracts latitude and longitude from Google Maps embeds, links, or coordinates."""
    if not text_or_url:
        return None

    # Check for direct lat,lng pattern
    match = GEO_COORDS_REGEX.search(text_or_url)
    if match:
        try:
            lat = float(match.group(1))
            lng = float(match.group(2))
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                return GeoEntity(
                    latitude=lat,
                    longitude=lng,
                    maps_url=text_or_url if text_or_url.startswith("http") else None,
                    source_url=source_url,
                )
        except ValueError:
            pass

    # Check if Google Maps query param: ?q=lat,lng
    if "maps" in text_or_url.lower() and text_or_url.startswith("http"):
        parsed = urlparse(text_or_url)
        params = parse_qs(parsed.query)
        q = params.get("q", [""])[0]
        if q and "," in q:
            parts = q.split(",")
            try:
                lat = float(parts[0].strip())
                lng = float(parts[1].strip())
                return GeoEntity(
                    latitude=lat,
                    longitude=lng,
                    maps_url=text_or_url,
                    source_url=source_url,
                )
            except Exception:
                pass

    return None


def extract_working_hours(text: str, source_url: str) -> List[WorkingHoursEntity]:
    """Extracts sentences or blocks describing business working hours."""
    if not text:
        return []

    hours_list: List[WorkingHoursEntity] = []
    lines = text.split("\n")
    for line in lines:
        cleaned = line.strip()
        if WORKING_HOURS_REGEX.search(cleaned) and len(cleaned) < 150:
            hours_list.append(WorkingHoursEntity(text=cleaned, source_url=source_url))

    return hours_list
