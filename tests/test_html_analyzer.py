"""Unit tests for the HTML analyzer and structure extraction."""

import pytest
from crawler.extract.html_analyzer import analyze_html


def test_html_analyzer_extraction(sample_html_with_entities):
    base_url = "https://plantlandtehran.com/"
    analysis = analyze_html(
        html_text=sample_html_with_entities,
        base_url=base_url,
        registrable_domain="plantlandtehran.com",
    )

    # Title & Meta
    assert "پلنت لند" in analysis.title or "فروشگاه" in analysis.title
    assert "description" in analysis.meta
    assert "گیاهان آپارتمانی" in analysis.meta["description"]

    # Structured Data (JSON-LD)
    assert len(analysis.structured_data) > 0
    assert analysis.structured_data[0].get("name") == "پلنت لند تهران"

    # Headings
    h1s = [h for h in analysis.headings if h.level == 1]
    assert len(h1s) > 0
    assert "خدمات نگهداری" in h1s[0].text

    # Links
    assert len(analysis.links) > 0
    internal_links = [l.href for l in analysis.links if l.internal]
    assert any("/about-us" in l for l in internal_links)
    assert any("/contact" in l for l in internal_links)

    # Normalized text
    assert "پلنت لند" in analysis.text_normalized
    assert "10 سال سابقه" in analysis.text_normalized  # Persian digits converted to Latin
