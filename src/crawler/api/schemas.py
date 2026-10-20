"""Pydantic API request and response schemas with OpenAPI examples."""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from crawler.domain.enums import CaptchaType, RenderType, WafVendor


class CrawlRequest(BaseModel):
    """Payload to initiate an asynchronous site crawl."""
    url: str = Field(..., json_schema_extra={"example": "https://plantlandtehran.com/"}, description="The root site URL to crawl")
    max_pages: Optional[int] = Field(default=None, ge=1, le=10000, json_schema_extra={"example": 50}, description="Max pages to crawl")
    max_depth: Optional[int] = Field(default=None, ge=0, le=10, json_schema_extra={"example": 3}, description="Max crawl depth")
    allow_subdomains: Optional[bool] = Field(default=None, json_schema_extra={"example": True}, description="Whether subdomains are in scope")
    use_crtsh: Optional[bool] = Field(default=None, json_schema_extra={"example": False}, description="Query crt.sh for subdomains")
    force_browser: Optional[bool] = Field(default=None, json_schema_extra={"example": False}, description="Force Chromium Playwright rendering")


class CrawlJobResponse(BaseModel):
    """Immediate acknowledgment containing the job identifier."""
    job_id: str
    status: str
    url: str


class CrawlStatusResponse(BaseModel):
    """Real-time progress and coverage metrics for a running or finished job."""
    job_id: str
    status: str
    url: str
    error: Optional[str] = None
    coverage: Optional[Dict[str, Any]] = None


class AnalyzeUrlRequest(BaseModel):
    """Payload for instant single-URL diagnostic inspection."""
    url: str = Field(..., json_schema_extra={"example": "https://plantlandtehran.com/"}, description="Target URL to inspect")


class AnalyzeUrlResponse(BaseModel):
    """Diagnostic assessment results for a single target URL."""
    url: str
    final_url: str
    status_code: int
    is_healthy: bool
    health_message: str
    render_type: RenderType
    render_confidence: float
    redirect_chain: list[str]
    redirect_type: str
    waf: WafVendor
    captcha: Optional[CaptchaType]


class HealthResponse(BaseModel):
    """Service liveness and readiness response."""
    status: str = "ok"
    version: str = "1.0.0"
    service: str = "sprawler"
