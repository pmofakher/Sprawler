"""FastAPI API routes defining the unified /sprawl endpoint."""

import time
import uuid
from fastapi import APIRouter, HTTPException, status

from crawler.api.schemas import HealthResponse, SprawlRequest, SprawlResponse
from crawler.core.config import settings
from crawler.core.exceptions import (
    InvalidUrlSchemeException,
    SSRFSecurityException,
    UrlNormalizationException,
)
from crawler.core.logging import logger
from crawler.frontier.normalizer import get_registrable_domain, normalize_url
from crawler.pipeline.orchestrator import CrawlOrchestrator
from crawler.storage.writer import SiteStorage

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["Monitoring"])
async def health_check() -> HealthResponse:
    """Liveness and readiness health check endpoint."""
    return HealthResponse()


@router.post(
    "/sprawl",
    response_model=SprawlResponse,
    status_code=status.HTTP_200_OK,
    tags=["Sprawl"],
    summary="Sprawl (Spider & Crawl) a domain or link and save JSON",
)
async def sprawl(request: SprawlRequest) -> SprawlResponse:
    """Unified endpoint to spider and crawl a domain or link.

    - Resolves and normalizes the target domain or URL
    - Enforces SSRF and scope security guards
    - Spiders and extracts business knowledge (contacts, hours, policies, pages)
    - Automatically saves the atomic `site.json` and `report.json` files to disk
    - Returns the aggregated knowledge JSON and the file paths where it was saved
    """
    raw_target = request.url or request.domain
    if not raw_target or not raw_target.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'url' or 'domain' must be provided in the request body.",
        )

    target_str = raw_target.strip()

    try:
        norm_url = normalize_url(target_str)
    except SSRFSecurityException as ssrf_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Security violation: {ssrf_err}",
        )
    except (InvalidUrlSchemeException, UrlNormalizationException) as url_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid URL or domain: {url_err}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid URL or domain: {exc}",
        )

    job_id = str(uuid.uuid4())
    start_time = time.monotonic()
    domain = get_registrable_domain(norm_url)

    logger.info(f"Initiating sprawl for target '{norm_url}' (job_id: {job_id})")

    orchestrator = CrawlOrchestrator(
        root_url=norm_url,
        job_id=job_id,
        max_pages=request.max_pages,
        max_depth=request.max_depth,
        allow_subdomains=request.allow_subdomains,
        use_crtsh=request.use_crtsh,
        force_browser=request.force_browser,
    )

    try:
        site_knowledge = await orchestrator.run()
    except Exception as exc:
        logger.exception(f"Sprawl execution failed for {norm_url}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Crawl execution failed for {norm_url}: {exc}",
        )

    duration = time.monotonic() - start_time
    storage = SiteStorage(settings.data_dir, domain)

    output_path = storage.site_json_path
    if request.output_filename:
        try:
            custom_path = storage.site_dir / request.output_filename
            await storage.save_atomic_json(custom_path, site_knowledge)
            output_path = custom_path
        except Exception as e:
            logger.warning(f"Could not save custom output filename {request.output_filename}: {e}")

    logger.info(
        f"Sprawl finished for {norm_url}. Pages crawled: {len(site_knowledge.pages)}. "
        f"Saved JSON: {output_path}"
    )

    return SprawlResponse(
        status="completed",
        job_id=job_id,
        domain=domain,
        url=norm_url,
        output_file=str(output_path.resolve()),
        report_file=str(storage.report_json_path.resolve()),
        pages_crawled=len(site_knowledge.pages),
        duration_seconds=round(duration, 2),
        site=site_knowledge.site,
        business=site_knowledge.business,
        pages=site_knowledge.pages,
        skipped=site_knowledge.skipped,
    )
