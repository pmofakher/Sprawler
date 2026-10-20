"""HTML link extraction and DOM location categorization."""

from typing import List, Tuple
from urllib.parse import urljoin
from bs4 import BeautifulSoup, Tag

from crawler.domain.models import LinkMetadata
from crawler.frontier.normalizer import is_in_domain_scope, normalize_url


def determine_element_location(tag: Tag) -> str:
    """Classifies the semantic structural location of a DOM tag."""
    for parent in tag.parents:
        if not parent or not parent.name:
            continue
        pname = parent.name.lower()
        pid = (parent.get("id") or "").lower()
        pclass = " ".join(parent.get("class") or []).lower()

        if pname == "nav" or "nav" in pid or "nav" in pclass or "menu" in pclass:
            return "nav"
        if pname == "header" or "header" in pid or "header" in pclass:
            return "header"
        if pname == "footer" or "footer" in pid or "footer" in pclass:
            return "footer"
        if pname == "aside" or "sidebar" in pid or "sidebar" in pclass:
            return "sidebar"

    return "body"


def extract_links_from_html(
    html_text: str,
    base_url: str,
    registrable_domain: str,
    allow_subdomains: bool = True,
) -> List[LinkMetadata]:
    """Parses all hyperlinks, areas, canonical links, and contact anchors from HTML."""
    if not html_text:
        return []

    soup = BeautifulSoup(html_text, "html.parser")
    links: List[LinkMetadata] = []

    # 1. <a> and <area> anchors
    anchor_tags = soup.find_all(["a", "area"])
    for tag in anchor_tags:
        href_raw = tag.get("href")
        if not href_raw:
            continue
        href_raw = str(href_raw).strip()
        if not href_raw or href_raw.startswith("#") or href_raw.startswith("javascript:"):
            continue

        location = determine_element_location(tag)
        text = tag.get_text(separator=" ", strip=True)
        has_img = bool(tag.find("img"))

        # Contact schemes (tel:, mailto:) are preserved as links
        if href_raw.lower().startswith("tel:") or href_raw.lower().startswith("mailto:"):
            links.append(
                LinkMetadata(
                    href=href_raw,
                    text=text or href_raw,
                    internal=True,
                    location=location,
                    wraps_image=has_img,
                )
            )
            continue

        try:
            abs_url = urljoin(base_url, href_raw)
            norm_url = normalize_url(abs_url)
            internal = is_in_domain_scope(norm_url, registrable_domain, allow_subdomains)

            links.append(
                LinkMetadata(
                    href=norm_url,
                    text=text,
                    internal=internal,
                    location=location,
                    wraps_image=has_img,
                )
            )
        except Exception:
            continue

    # 2. <link rel="canonical">
    canonical_tag = soup.find("link", attrs={"rel": "canonical"})
    if canonical_tag and canonical_tag.get("href"):
        can_href = str(canonical_tag["href"]).strip()
        try:
            norm_can = normalize_url(urljoin(base_url, can_href))
            internal = is_in_domain_scope(norm_can, registrable_domain, allow_subdomains)
            links.append(
                LinkMetadata(
                    href=norm_can,
                    text="canonical",
                    internal=internal,
                    location="header",
                    wraps_image=False,
                )
            )
        except Exception:
            pass

    return links
