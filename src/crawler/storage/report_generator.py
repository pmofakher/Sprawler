"""Coverage and audit report generator."""

from datetime import datetime, timezone
from typing import Any, Dict, List

from crawler.domain.enums import CrawlStatus
from crawler.domain.models import CoverageStats, PageResult, SiteKnowledge, SiteReport


def generate_coverage_report(
    job_id: str,
    domain: str,
    root_url: str,
    started_at: str,
    frontier_stats: Dict[str, Any],
    site_knowledge: SiteKnowledge,
    duration_seconds: float,
    site_down: bool = False,
) -> SiteReport:
    """Builds a structured coverage and quality audit report from crawl outputs."""
    finished_at = datetime.now(timezone.utc).isoformat()

    # Calculate redirect stats across crawled pages
    redirect_stats: Dict[str, int] = {}
    for page in site_knowledge.pages:
        if page.redirect_type.value != "none":
            rtype = page.redirect_type.value
            redirect_stats[rtype] = redirect_stats.get(rtype, 0) + 1

    # Overall site status
    status = site_knowledge.site.status
    if site_down:
        status = CrawlStatus.SITE_DOWN
    elif site_knowledge.site.captcha:
        status = CrawlStatus.BLOCKED
    elif len(site_knowledge.pages) == 0 and frontier_stats.get("failed", 0) > 0:
        status = CrawlStatus.PARTIAL
    else:
        status = CrawlStatus.OK

    coverage = CoverageStats(
        discovered=frontier_stats.get("total", 0),
        crawled=frontier_stats.get("done", 0),
        failed=frontier_stats.get("failed", 0),
        blocked=frontier_stats.get("blocked", 0),
        skipped=frontier_stats.get("skipped", 0),
        skipped_by_reason=frontier_stats.get("skipped_by_reason", {}),
    )

    return SiteReport(
        job_id=job_id,
        domain=domain,
        root_url=root_url,
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=round(duration_seconds, 2),
        status=status,
        render_type=site_knowledge.site.render_type,
        coverage=coverage,
        redirect_stats=redirect_stats,
        captcha_detected=site_knowledge.site.captcha,
        waf_detected=site_knowledge.site.waf,
        site_down=site_down,
    )
