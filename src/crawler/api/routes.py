from typing import Any, Dict
from fastapi import APIRouter, HTTPException, status

from crawler.api.schemas import (
    AnalyzeUrlRequest,
    AnalyzeUrlResponse,
    CrawlJobResponse,
    CrawlRequest,
    CrawlStatusResponse,
    HealthResponse,
)
from crawler.core.constants import DEFAULT_USER_AGENT
from crawler.core.exceptions import CrawlerException, SSRFSecurityException
from crawler.detect.captcha import detect_captcha
from crawler.detect.site_down import check_site_health
from crawler.detect.waf import detect_waf
from crawler.domain.models import SiteKnowledge, SiteReport
from crawler.fetch.http_fetcher import HttpFetcher
from crawler.fetch.render_detector import detect_render_type_from_html
from crawler.frontier.normalizer import normalize_url
from crawler.pipeline.manager import job_manager

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["Monitoring"])
async def health_check() -> HealthResponse:
    """Liveness and readiness health check endpoint."""
    return HealthResponse()


@router.post("/crawl", response_model=CrawlJobResponse, status_code=status.HTTP_202_ACCEPTED, tags=["Crawling"])
async def start_crawl(request: CrawlRequest) -> CrawlJobResponse:
    """Initiates an asynchronous website crawl job and returns its unique tracking ID."""
    try:
        norm_url = normalize_url(request.url)
    except SSRFSecurityException as ssrf_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Security violation: {ssrf_err}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid URL: {exc}",
        )

    job_id = await job_manager.start_job(
        url=norm_url,
        max_pages=request.max_pages,
        max_depth=request.max_depth,
        allow_subdomains=request.allow_subdomains,
        use_crtsh=request.use_crtsh,
        force_browser=request.force_browser,
    )

    return CrawlJobResponse(job_id=job_id, status="running", url=norm_url)


@router.get("/crawl/{job_id}", response_model=CrawlStatusResponse, tags=["Crawling"])
async def get_crawl_status(job_id: str) -> CrawlStatusResponse:
    """Retrieves current execution progress and live queue counts for a job."""
    job = await job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found")

    coverage_data = None
    if job.orchestrator.frontier:
        try:
            coverage_data = await job.orchestrator.frontier.get_stats()
        except Exception:
            pass

    return CrawlStatusResponse(
        job_id=job_id,
        status=job.status,
        url=job.url,
        error=job.error,
        coverage=coverage_data,
    )


@router.get("/crawl/{job_id}/result", response_model=SiteKnowledge, tags=["Crawling"])
async def get_crawl_result(job_id: str) -> SiteKnowledge:
    """Fetches the aggregated business knowledge JSON document for a completed crawl."""
    result = await job_manager.get_job_result(job_id)
    if not result:
        job = await job_manager.get_job(job_id)
        if job and job.status == "running":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Crawl job {job_id} is still in progress.",
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Results for job {job_id} not found.",
        )
    return result


@router.get("/crawl/{job_id}/report", response_model=SiteReport, tags=["Crawling"])
async def get_crawl_report(job_id: str) -> SiteReport:
    """Fetches the comprehensive coverage and audit report for a crawl."""
    report = await job_manager.get_job_report(job_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report for job {job_id} not available.",
        )
    return report


@router.post("/crawl/{job_id}/cancel", tags=["Crawling"])
async def cancel_crawl(job_id: str) -> Dict[str, Any]:
    """Gracefully interrupts and cancels a running crawl job."""
    success = await job_manager.cancel_job(job_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found.",
        )
    return {"job_id": job_id, "status": "cancelled"}


@router.post("/crawl/{job_id}/resume", response_model=CrawlJobResponse, tags=["Crawling"])
async def resume_crawl(job_id: str) -> CrawlJobResponse:
    """Resumes an incomplete or interrupted crawl job using its persistent frontier."""
    new_job_id = await job_manager.resume_job(job_id)
    if not new_job_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} could not be resumed or does not exist.",
        )
    job = await job_manager.get_job(new_job_id)
    return CrawlJobResponse(job_id=new_job_id, status="running", url=job.url if job else "")


@router.post("/analyze/url", response_model=AnalyzeUrlResponse, tags=["Diagnostics"])
async def analyze_single_url(request: AnalyzeUrlRequest) -> AnalyzeUrlResponse:
    """Diagnostic tool: inspects a single URL without crawling."""
    try:
        norm_url = normalize_url(request.url)
    except SSRFSecurityException as ssrf_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ssrf_err))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # Health check
    is_healthy, health_msg = await check_site_health(norm_url)

    # HTTP Probe
    fetcher = HttpFetcher(user_agent=DEFAULT_USER_AGENT, timeout=15.0)
    fetch_res = await fetcher.fetch(norm_url)

    # Render type detection
    render_type, confidence = detect_render_type_from_html(fetch_res.raw_html)

    # WAF and CAPTCHA detection
    waf = detect_waf(fetch_res.headers, html_text=fetch_res.raw_html)
    captcha = detect_captcha(fetch_res.raw_html, status_code=fetch_res.status_code)

    return AnalyzeUrlResponse(
        url=norm_url,
        final_url=fetch_res.final_url,
        status_code=fetch_res.status_code,
        is_healthy=is_healthy,
        health_message=health_msg,
        render_type=render_type,
        render_confidence=confidence,
        redirect_chain=fetch_res.redirect_chain,
        redirect_type=fetch_res.redirect_type.value,
        waf=waf,
        captcha=captcha,
    )
