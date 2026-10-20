"""Extraction package for HTML analysis, entities, deduplication, page classification, and PDF."""

from crawler.extract.dedup import ContentDeduplicator, compute_content_hash
from crawler.extract.entities import (
    extract_emails,
    extract_geo_coordinates,
    extract_phones,
    extract_social_links,
    extract_working_hours,
)
from crawler.extract.html_analyzer import analyze_html
from crawler.extract.page_classifier import classify_page_type
from crawler.extract.pdf_extractor import PdfExtractor

__all__ = [
    "analyze_html",
    "extract_phones",
    "extract_emails",
    "extract_social_links",
    "extract_geo_coordinates",
    "extract_working_hours",
    "classify_page_type",
    "compute_content_hash",
    "ContentDeduplicator",
    "PdfExtractor",
]
