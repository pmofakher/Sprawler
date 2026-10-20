"""Storage package for atomic disk writers, artifact layouts, and reports."""

from crawler.storage.report_generator import generate_coverage_report
from crawler.storage.writer import SiteStorage, compute_url_hash

__all__ = ["SiteStorage", "compute_url_hash", "generate_coverage_report"]
