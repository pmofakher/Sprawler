"""Comprehensive HTML analyzer extracting structured DOM elements, microdata, and main text."""

import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
import trafilatura

from crawler.discovery.links import extract_links_from_html
from crawler.domain.models import HeadingItem, HtmlAnalysis, ImageMetadata, TableData
from crawler.text.persian import normalize_persian_text


def extract_json_ld(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """Extracts and parses all JSON-LD script blocks from the DOM."""
    structured_data: List[Dict[str, Any]] = []
    scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    for script in scripts:
        if script.string:
            try:
                data = json.loads(script.string.strip())
                if isinstance(data, list):
                    structured_data.extend(data)
                elif isinstance(data, dict):
                    structured_data.append(data)
            except Exception:
                pass
    return structured_data


def extract_headings(soup: BeautifulSoup) -> List[HeadingItem]:
    """Extracts h1-h6 heading tags while preserving document order and levels."""
    headings: List[HeadingItem] = []
    for tag in soup.find_all(re.compile(r"^h[1-6]$", re.I)):
        text = tag.get_text(separator=" ", strip=True)
        if text:
            try:
                level = int(tag.name[1])
                headings.append(HeadingItem(level=level, text=text))
            except ValueError:
                pass
    return headings


def extract_tables(soup: BeautifulSoup) -> List[TableData]:
    """Converts HTML table elements into structured TableData objects."""
    tables: List[TableData] = []
    for table in soup.find_all("table"):
        headers: List[str] = []
        rows: List[List[str]] = []

        # Find header columns
        for th in table.find_all("th"):
            txt = th.get_text(separator=" ", strip=True)
            if txt:
                headers.append(txt)

        # Find table body rows
        for tr in table.find_all("tr"):
            cols = [td.get_text(separator=" ", strip=True) for td in tr.find_all("td")]
            if cols:
                rows.append(cols)

        if headers or rows:
            tables.append(TableData(headers=headers, rows=rows))

    return tables


def extract_images(soup: BeautifulSoup, base_url: str) -> List[ImageMetadata]:
    """Extracts image metadata (handling lazy-loading src/srcset/data-src)."""
    images: List[ImageMetadata] = []
    for img in soup.find_all("img"):
        # Support lazy loading attributes
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or ""
        if not src:
            srcset = img.get("srcset") or img.get("data-srcset")
            if srcset:
                src = srcset.split(",")[0].split()[0]
        if not src or src.startswith("data:"):
            continue

        abs_src = urljoin(base_url, src.strip())
        alt = str(img.get("alt") or "").strip()
        title = str(img.get("title") or "").strip() if img.get("title") else None

        # Parent anchor link
        parent_a = img.find_parent("a")
        link_href = urljoin(base_url, str(parent_a["href"])) if parent_a and parent_a.get("href") else None

        # Nearest heading context
        prev_heading = img.find_previous(re.compile(r"^h[1-6]$", re.I))
        context = prev_heading.get_text(strip=True) if prev_heading else ""

        # Parse width / height if available
        width = None
        height = None
        if img.get("width") and str(img["width"]).isdigit():
            width = int(img["width"])
        if img.get("height") and str(img["height"]).isdigit():
            height = int(img["height"])

        images.append(
            ImageMetadata(
                src=abs_src,
                alt=alt,
                title=title,
                width=width,
                height=height,
                link_href=link_href,
                context=context,
            )
        )

    return images


def analyze_html(
    html_text: str,
    base_url: str,
    registrable_domain: str,
    allow_subdomains: bool = True,
) -> HtmlAnalysis:
    """Executes full structural extraction and text normalization on HTML."""
    if not html_text:
        return HtmlAnalysis()

    soup = BeautifulSoup(html_text, "html.parser")

    # 1. Clean boilerplate non-content tags before text extraction
    for tag_name in ["script", "style", "noscript", "svg"]:
        for tag in soup.find_all(tag_name):
            # Preserve JSON-LD scripts
            if tag_name == "noscript" or (tag_name == "script" and tag.get("type") == "application/ld+json"):
                continue
            tag.decompose()

    # Remove hidden elements (display:none, aria-hidden)
    for hidden in soup.find_all(attrs={"aria-hidden": "true"}):
        hidden.decompose()

    # 2. Extract Document Title
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    # 3. Meta Tags
    meta_dict: Dict[str, str] = {}
    for meta in soup.find_all("meta"):
        name = meta.get("name") or meta.get("property") or meta.get("http-equiv")
        content = meta.get("content")
        if name and content:
            meta_dict[str(name).strip().lower()] = str(content).strip()

    # 4. JSON-LD Microdata
    structured_data = extract_json_ld(soup)

    # 5. Headings
    headings = extract_headings(soup)

    # 6. Paragraphs and List Items
    paragraphs = [p.get_text(separator=" ", strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]

    lists: List[List[str]] = []
    for list_tag in soup.find_all(["ul", "ol"]):
        items = [li.get_text(separator=" ", strip=True) for li in list_tag.find_all("li", recursive=False) if li.get_text(strip=True)]
        if items:
            lists.append(items)

    # 7. Tables
    tables = extract_tables(soup)

    # 8. Images
    images = extract_images(soup, base_url)

    # 9. Links
    links = extract_links_from_html(html_text, base_url, registrable_domain, allow_subdomains)

    # 10. Clean Main Text Extraction via Trafilatura with DOM fallback
    main_text = ""
    try:
        trafilatura_text = trafilatura.extract(
            html_text,
            include_comments=False,
            include_tables=True,
            favor_precision=True,
        )
        if trafilatura_text:
            main_text = trafilatura_text
    except Exception:
        pass

    if not main_text:
        # Fallback to DOM body text
        body = soup.body
        main_text = body.get_text(separator="\n", strip=True) if body else ""

    normalized_text = normalize_persian_text(main_text)

    return HtmlAnalysis(
        title=title,
        meta=meta_dict,
        structured_data=structured_data,
        headings=headings,
        paragraphs=paragraphs,
        lists=lists,
        tables=tables,
        images=images,
        links=links,
        text_raw=main_text,
        text_normalized=normalized_text,
    )
