"""Pydantic v2 data models for Sprawler crawl results, analysis, and reports."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from crawler.domain.enums import (
    CaptchaType,
    CrawlStatus,
    PageType,
    RedirectType,
    RenderType,
    SkipReason,
    SourceType,
    WafVendor,
)


class SiteInfo(BaseModel):
    """Metadata describing the target site and overall crawl environment."""
    root_url: str
    domain: str
    crawled_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: CrawlStatus = CrawlStatus.OK
    render_type: RenderType = RenderType.STATIC
    language: str = "fa"
    waf: WafVendor = WafVendor.NONE
    captcha: Optional[CaptchaType] = None


class EntitySource(BaseModel):
    """Base model for extracted business attributes linking back to origin URL."""
    value: str
    source_url: str


class PhoneEntity(EntitySource):
    """Extracted telephone / mobile number normalized."""
    pass


class EmailEntity(EntitySource):
    """Extracted email address."""
    pass


class AddressEntity(EntitySource):
    """Extracted physical location / postal address."""
    pass


class SocialEntity(BaseModel):
    """Extracted social media channel profile."""
    platform: str
    url: str
    source_url: str


class WorkingHoursEntity(BaseModel):
    """Extracted business opening and operating hours."""
    text: str
    source_url: str


class GeoEntity(BaseModel):
    """Extracted map coordinates or embed reference."""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    maps_url: Optional[str] = None
    source_url: str


class BusinessInfo(BaseModel):
    """Aggregated, deduplicated business profile extracted from all pages."""
    name: str = ""
    description: str = ""
    category: str = ""
    phones: List[PhoneEntity] = Field(default_factory=list)
    emails: List[EmailEntity] = Field(default_factory=list)
    addresses: List[AddressEntity] = Field(default_factory=list)
    social: List[SocialEntity] = Field(default_factory=list)
    working_hours: List[WorkingHoursEntity] = Field(default_factory=list)
    geo: List[GeoEntity] = Field(default_factory=list)


class ImageMetadata(BaseModel):
    """Metadata of an image tag without downloading the binary payload."""
    src: str
    alt: str = ""
    title: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    link_href: Optional[str] = None
    context: str = ""


class LinkMetadata(BaseModel):
    """Extracted hyperlink information."""
    href: str
    text: str = ""
    internal: bool = True
    location: str = "body"  # nav | header | footer | body | sidebar
    wraps_image: bool = False


class HeadingItem(BaseModel):
    """Hierarchical heading tag content."""
    level: int  # 1 to 6
    text: str


class TableData(BaseModel):
    """Extracted structured HTML table."""
    headers: List[str] = Field(default_factory=list)
    rows: List[List[str]] = Field(default_factory=list)


class HtmlAnalysis(BaseModel):
    """Granular per-page structured breakdown."""
    title: str = ""
    meta: Dict[str, str] = Field(default_factory=dict)
    structured_data: List[Dict[str, Any]] = Field(default_factory=list)
    headings: List[HeadingItem] = Field(default_factory=list)
    paragraphs: List[str] = Field(default_factory=list)
    lists: List[List[str]] = Field(default_factory=list)
    tables: List[TableData] = Field(default_factory=list)
    images: List[ImageMetadata] = Field(default_factory=list)
    links: List[LinkMetadata] = Field(default_factory=list)
    text_raw: str = ""
    text_normalized: str = ""


class DocumentItem(BaseModel):
    """Extracted document payload (PDF text or OCR)."""
    url: str
    filename: str
    source_type: SourceType = SourceType.PDF
    text_raw: str = ""
    text_normalized: str = ""


class XhrData(BaseModel):
    """Captured background XHR/fetch JSON payload."""
    url: str
    method: str = "GET"
    status: int = 200
    content_type: str = "application/json"
    data: Any = None
    extracted_text: str = ""


class PageResult(BaseModel):
    """Complete extraction result for a single crawled URL."""
    url: str
    final_url: str
    status_code: int = 200
    redirect_chain: List[str] = Field(default_factory=list)
    redirect_type: RedirectType = RedirectType.NONE
    page_type: PageType = PageType.OTHER
    content_hash: str = ""
    fetched_with: str = "httpx"  # "httpx" | "playwright"
    html_analysis: HtmlAnalysis = Field(default_factory=HtmlAnalysis)
    xhr_data: List[XhrData] = Field(default_factory=list)
    documents: List[DocumentItem] = Field(default_factory=list)


class SkippedItem(BaseModel):
    """Record of a discovered URL intentionally filtered out."""
    url: str
    reason: SkipReason


class SiteKnowledge(BaseModel):
    """Top-level aggregate JSON model representing the entire site's extracted knowledge."""
    site: SiteInfo
    business: BusinessInfo
    pages: List[PageResult] = Field(default_factory=list)
    skipped: List[SkippedItem] = Field(default_factory=list)


class CoverageStats(BaseModel):
    """Numerical audit breakdown of discovered URLs."""
    discovered: int = 0
    crawled: int = 0
    failed: int = 0
    blocked: int = 0
    skipped: int = 0
    skipped_by_reason: Dict[str, int] = Field(default_factory=dict)


class SiteReport(BaseModel):
    """Comprehensive coverage and audit report for a crawl session."""
    job_id: str
    domain: str
    root_url: str
    started_at: str
    finished_at: Optional[str] = None
    duration_seconds: float = 0.0
    status: CrawlStatus = CrawlStatus.OK
    render_type: RenderType = RenderType.STATIC
    coverage: CoverageStats = Field(default_factory=CoverageStats)
    redirect_stats: Dict[str, int] = Field(default_factory=dict)
    captcha_detected: Optional[CaptchaType] = None
    waf_detected: WafVendor = WafVendor.NONE
    site_down: bool = False
