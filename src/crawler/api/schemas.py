"""Pydantic API request and response schemas with OpenAPI examples."""

from typing import List, Optional
from pydantic import BaseModel, Field

from crawler.domain.models import BusinessInfo, PageResult, SiteInfo, SkippedItem


class SprawlRequest(BaseModel):
    """Payload to sprawl (spider/crawl) a domain or link and save the JSON result."""

    url: Optional[str] = Field(
        default=None,
        json_schema_extra={"example": "https://plantlandtehran.com/"},
        description="Target URL or web link to spider/crawl",
    )
    domain: Optional[str] = Field(
        default=None,
        json_schema_extra={"example": "plantlandtehran.com"},
        description="Target domain name (can be provided instead of or in addition to url)",
    )
    max_pages: Optional[int] = Field(
        default=None,
        ge=1,
        le=10000,
        json_schema_extra={"example": 50},
        description="Max pages to crawl (defaults to config: 200)",
    )
    max_depth: Optional[int] = Field(
        default=None,
        ge=0,
        le=10,
        json_schema_extra={"example": 3},
        description="Max crawl depth (defaults to config: 4)",
    )
    allow_subdomains: Optional[bool] = Field(
        default=None,
        json_schema_extra={"example": True},
        description="Whether subdomains are in scope for crawling",
    )
    force_browser: Optional[bool] = Field(
        default=None,
        json_schema_extra={"example": False},
        description="Force Chromium Playwright rendering for all pages",
    )
    use_crtsh: Optional[bool] = Field(
        default=None,
        json_schema_extra={"example": False},
        description="Query crt.sh certificate transparency logs for subdomains",
    )
    output_filename: Optional[str] = Field(
        default=None,
        json_schema_extra={"example": "site.json"},
        description="Optional custom filename for the saved JSON (defaults to site.json)",
    )


class SprawlResponse(BaseModel):
    """Aggregated result of the sprawl execution, including saved file paths and knowledge."""

    status: str = Field(default="completed", description="Crawl status ('completed' or 'failed')")
    job_id: str = Field(description="Unique crawl execution ID")
    domain: str = Field(description="Target registrable domain")
    url: str = Field(description="Root normalized URL that was crawled")
    output_file: str = Field(description="Absolute path to the saved site.json file on disk")
    report_file: str = Field(description="Absolute path to the saved report.json file on disk")
    pages_crawled: int = Field(description="Total number of pages successfully crawled and indexed")
    duration_seconds: float = Field(description="Total execution time in seconds")
    site: SiteInfo = Field(description="Aggregated site metadata and detected technologies")
    business: BusinessInfo = Field(description="Extracted business entities (phones, emails, hours, address, social)")
    pages: List[PageResult] = Field(description="Extracted knowledge and content per crawled page")
    skipped: List[SkippedItem] = Field(description="List of skipped URLs and skip reasons")


class HealthResponse(BaseModel):
    """Service liveness and readiness response."""

    status: str = "ok"
    version: str = "1.0.0"
    service: str = "sprawler"
