"""End-to-end crawl pipeline orchestrator managing discovery, classification, and persistence."""

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

from crawler.core.config import settings
from crawler.core.constants import DEFAULT_USER_AGENT
from crawler.core.exceptions import (
    CrawlerException,
    RobotsDisallowedException,
    SSRFSecurityException,
)
from crawler.core.logging import setup_logger
from crawler.detect.captcha import detect_captcha
from crawler.detect.redirect import classify_redirect_hop
from crawler.detect.site_down import check_site_health, is_soft_down
from crawler.detect.waf import detect_waf
from crawler.discovery.crtsh import discover_crtsh_subdomains
from crawler.discovery.robots import RobotsHandler
from crawler.discovery.sitemap import SitemapDiscoverer
from crawler.domain.enums import (
    CaptchaType,
    CrawlStatus,
    FrontierStatus,
    PageType,
    RedirectType,
    RenderType,
    SkipReason,
    WafVendor,
)
from crawler.domain.models import (
    AddressEntity,
    BusinessInfo,
    EmailEntity,
    GeoEntity,
    PageResult,
    PhoneEntity,
    SiteInfo,
    SiteKnowledge,
    SiteReport,
    SkippedItem,
    SocialEntity,
    WorkingHoursEntity,
)
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
from crawler.fetch.browser_fetcher import BrowserFetcher
from crawler.fetch.http_fetcher import HttpFetcher
from crawler.fetch.render_detector import detect_render_type_from_html, render_cache
from crawler.frontier.filter import (
    calculate_url_priority,
    is_document_url,
    should_skip_url,
)
from crawler.frontier.normalizer import (
    get_registrable_domain,
    is_in_domain_scope,
    normalize_url,
    validate_ssrf,
)
from crawler.frontier.sqlite_frontier import SqliteFrontier
from crawler.plugins.captcha_solver import NoOpCaptchaSolver
from crawler.plugins.waf_bypass import NoOpWafHandler
from crawler.resilience.circuit_breaker import DomainCircuitBreaker
from crawler.resilience.rate_limiter import DomainRateLimiter
from crawler.storage.report_generator import generate_coverage_report
from crawler.storage.writer import SiteStorage


class CrawlOrchestrator:
    """Coordinates the full crawl lifecycle for a target root website."""

    def __init__(
        self,
        root_url: str,
        job_id: str,
        max_pages: Optional[int] = None,
        max_depth: Optional[int] = None,
        allow_subdomains: Optional[bool] = None,
        use_crtsh: Optional[bool] = None,
        force_browser: Optional[bool] = None,
    ):
        self.raw_root_url = root_url
        self.job_id = job_id
        self.max_pages = max_pages or settings.max_pages_per_site
        self.max_depth = max_depth if max_depth is not None else settings.max_depth
        self.allow_subdomains = allow_subdomains if allow_subdomains is not None else settings.allow_subdomains
        self.use_crtsh = use_crtsh if use_crtsh is not None else settings.use_crtsh
        self.force_browser = force_browser if force_browser is not None else settings.force_browser

        self.root_url: str = ""
        self.domain: str = ""
        self.storage: Optional[SiteStorage] = None
        self.frontier: Optional[SqliteFrontier] = None
        self.logger = setup_logger("sprawler", job_id=self.job_id)

        # Runtime components
        self.http_fetcher = HttpFetcher(
            user_agent=settings.user_agent,
            timeout=settings.request_timeout,
            max_page_size_bytes=settings.max_page_size_bytes,
        )
        self.browser_fetcher = BrowserFetcher(
            headless=settings.browser_headless,
            user_agent=settings.user_agent,
            timeout_ms=settings.browser_timeout_ms,
            networkidle_timeout_ms=settings.networkidle_timeout_ms,
            dismiss_consent_walls=settings.dismiss_consent_walls,
        )
        self.pdf_extractor = PdfExtractor(
            max_size_bytes=settings.max_pdf_size_bytes,
            ocr_enabled=settings.ocr_enabled_for_pdf,
            ocr_languages=settings.ocr_languages,
            user_agent=settings.user_agent,
        )
        self.rate_limiter = DomainRateLimiter(default_delay=settings.politeness_delay_seconds)
        self.circuit_breaker: Optional[DomainCircuitBreaker] = None
        self.deduplicator = ContentDeduplicator()
        self.captcha_solver = NoOpCaptchaSolver()
        self.waf_handler = NoOpWafHandler()

        # State tracking
        self.is_cancelled = False
        self.site_down = False
        self.detected_waf = WafVendor.NONE
        self.detected_captcha: Optional[CaptchaType] = None
        self.detected_render_type = RenderType.STATIC

    async def run(self) -> SiteKnowledge:
        """Executes the systematic crawl sequence."""
        start_time = time.monotonic()
        started_at = datetime.now(timezone.utc).isoformat()

        # Step 1: Validate & normalize root URL and SSRF check
        self.root_url = normalize_url(self.raw_root_url)
        self.domain = get_registrable_domain(self.root_url)
        parsed_root = urlparse(self.root_url)
        validate_ssrf(parsed_root.netloc.split(":")[0])

        # Step 1b: Initialize storage and per-site rotating logger
        self.storage = SiteStorage(settings.data_dir, self.domain)
        self.storage.initialize_directories()
        self.logger = setup_logger(
            f"sprawler.{self.domain}",
            log_file=self.storage.log_file_path,
            job_id=self.job_id,
            domain=self.domain,
        )
        self.logger.info(f"Starting crawl for {self.root_url} (domain: {self.domain})")

        # Step 1c: Initialize persistent frontier and circuit breaker
        self.frontier = SqliteFrontier(self.storage.frontier_db_path)
        await self.frontier.initialize()
        self.circuit_breaker = DomainCircuitBreaker(
            domain=self.domain,
            failure_threshold=settings.circuit_breaker_failure_threshold,
            recovery_timeout=settings.circuit_breaker_recovery_timeout,
        )

        site_info = SiteInfo(
            root_url=self.root_url,
            domain=self.domain,
            crawled_at=started_at,
            status=CrawlStatus.OK,
            render_type=RenderType.STATIC,
            language="fa",
            waf=WafVendor.NONE,
            captcha=None,
        )
        business_info = BusinessInfo()
        page_results: List[PageResult] = []

        try:
            # Step 2: Health check
            is_healthy, health_detail = await check_site_health(self.root_url)
            if not is_healthy:
                self.logger.error(f"Pre-crawl health check failed for {self.root_url}: {health_detail}")
                self.site_down = True
                site_info.status = CrawlStatus.SITE_DOWN
                site_knowledge = SiteKnowledge(site=site_info, business=business_info, pages=[], skipped=[])
                await self._persist_final(site_knowledge, started_at, start_time)
                return site_knowledge

            # Step 3: Fetch robots.txt & honor Crawl-delay
            robots = await RobotsHandler.fetch(self.root_url, user_agent=settings.user_agent)
            if robots.crawl_delay and settings.honor_crawl_delay:
                self.logger.info(f"Setting politeness delay to {robots.crawl_delay}s from robots.txt")
                self.rate_limiter.set_domain_delay(self.domain, robots.crawl_delay)

            # Step 4: Render-type detection
            if self.force_browser:
                self.detected_render_type = RenderType.CSR
            elif render_cache.contains(self.domain):
                self.detected_render_type, _ = render_cache.get(self.domain)
            else:
                initial_probe = await self.http_fetcher.fetch(self.root_url)
                if initial_probe.status_code == 200 and initial_probe.raw_html:
                    self.detected_render_type, conf = detect_render_type_from_html(initial_probe.raw_html)
                    render_cache.set(self.domain, self.detected_render_type, conf)
                    self.logger.info(f"Detected render type: {self.detected_render_type.value} (confidence: {conf:.2f})")
                else:
                    self.detected_render_type = RenderType.STATIC

            site_info.render_type = self.detected_render_type

            # Step 5: URL Discovery (Sitemaps, crt.sh, Seed root)
            await self.frontier.add_url(self.root_url, depth=0, priority=100)

            # Sitemap discovery
            sitemap_discoverer = SitemapDiscoverer(
                root_url=self.root_url,
                registrable_domain=self.domain,
                allow_subdomains=self.allow_subdomains,
                user_agent=settings.user_agent,
            )
            sitemap_urls = await sitemap_discoverer.discover_urls(explicit_sitemaps=robots.sitemaps)
            for s_url in sitemap_urls:
                priority = calculate_url_priority(s_url, depth=1)
                await self.frontier.add_url(s_url, depth=1, priority=priority)

            # crt.sh certificate transparency subdomains
            if self.use_crtsh and self.allow_subdomains:
                subdomains = await discover_crtsh_subdomains(self.domain, timeout=settings.crtsh_timeout_seconds)
                for sub in subdomains:
                    await self.frontier.add_url(sub, depth=1, priority=60)

            # Step 6: Main Crawl Loop
            crawled_count = 0
            while crawled_count < self.max_pages and not self.is_cancelled:
                # Check circuit breaker
                if not await self.circuit_breaker.can_execute():
                    self.logger.warning(f"Circuit breaker is OPEN for {self.domain}. Pausing crawl.")
                    await asyncio.sleep(5.0)
                    continue

                item = await self.frontier.get_next_url()
                if not item:
                    # No pending URLs left in queue
                    break

                target_url = item.url
                target_depth = item.depth

                # Check robots.txt compliance
                if not robots.is_allowed(target_url):
                    self.logger.info(f"Skipping {target_url} (Disallowed by robots.txt)")
                    await self.frontier.mark_status(target_url, FrontierStatus.SKIPPED, skip_reason=SkipReason.ROBOTS)
                    continue

                # Enforce politeness delay
                await self.rate_limiter.wait(self.domain)

                # Fetch page with appropriate fetcher
                use_browser = (self.detected_render_type == RenderType.CSR) or self.force_browser
                current_fetcher = self.browser_fetcher if use_browser else self.http_fetcher

                fetch_res = await current_fetcher.fetch(target_url)

                # Handle failure / error
                if fetch_res.status_code == 0 or fetch_res.error:
                    await self.circuit_breaker.record_failure(fetch_res.error or "HTTP error")
                    await self.frontier.mark_status(target_url, FrontierStatus.FAILED, last_error=fetch_res.error)
                    continue

                # Record success for circuit breaker
                await self.circuit_breaker.record_success()

                # Step 6a: Classify response (CAPTCHA, WAF, Soft-down)
                html_body = fetch_res.rendered_html or fetch_res.raw_html

                captcha = detect_captcha(html_body, status_code=fetch_res.status_code)
                if captcha:
                    self.detected_captcha = captcha
                    site_info.captcha = captcha
                    self.logger.warning(f"CAPTCHA challenge detected on {target_url}: {captcha.value}")
                    # Invoke plug-in hook
                    await self.captcha_solver.solve(captcha, target_url)
                    await self.frontier.mark_status(target_url, FrontierStatus.BLOCKED, last_error=f"CAPTCHA: {captcha.value}")
                    continue

                waf = detect_waf(fetch_res.headers, html_text=html_body)
                if waf != WafVendor.NONE:
                    self.detected_waf = waf
                    site_info.waf = waf
                    # Invoke plug-in hook
                    await self.waf_handler.handle_challenge(waf, target_url, fetch_res.headers)

                if is_soft_down(html_body):
                    self.logger.warning(f"Soft-down / placeholder detected on {target_url}")
                    await self.frontier.mark_status(target_url, FrontierStatus.FAILED, last_error="Soft-down")
                    continue

                # Step 6b: HTML Analysis & Text Extraction
                analysis = analyze_html(
                    html_text=html_body,
                    base_url=fetch_res.final_url,
                    registrable_domain=self.domain,
                    allow_subdomains=self.allow_subdomains,
                )

                # Fallback to browser if httpx returned suspiciously little text on an active page
                if (
                    not use_browser
                    and len(analysis.text_raw) < 150
                    and fetch_res.status_code == 200
                    and not is_document_url(target_url)
                ):
                    self.logger.info(f"Suspiciously short text on {target_url}; re-fetching with Playwright browser")
                    fetch_res = await self.browser_fetcher.fetch(target_url)
                    html_body = fetch_res.rendered_html or fetch_res.raw_html
                    analysis = analyze_html(
                        html_text=html_body,
                        base_url=fetch_res.final_url,
                        registrable_domain=self.domain,
                        allow_subdomains=self.allow_subdomains,
                    )

                # Step 6c: Content Hash & Duplicate Checking
                content_hash = compute_content_hash(analysis.text_normalized)
                if self.deduplicator.is_duplicate_content(content_hash):
                    self.logger.info(f"Duplicate content hash on {target_url}. Skipping.")
                    await self.frontier.mark_status(target_url, FrontierStatus.SKIPPED, skip_reason=SkipReason.DUPLICATE)
                    continue

                # Register page lines for site-wide boilerplate deduplication
                self.deduplicator.register_page_lines(analysis.text_raw)

                # Step 6d: Entity Extraction & Aggregation
                phones = extract_phones(analysis.text_raw, source_url=target_url)
                emails = extract_emails(analysis.text_raw, source_url=target_url)
                hours = extract_working_hours(analysis.text_raw, source_url=target_url)
                socials = extract_social_links([link.href for link in analysis.links], source_url=target_url)
                geo = extract_geo_coordinates(html_body, source_url=target_url)

                # Merge into business_info
                business_info.phones.extend(phones)
                business_info.emails.extend(emails)
                business_info.working_hours.extend(hours)
                business_info.social.extend(socials)
                if geo:
                    business_info.geo.append(geo)

                # Classify page type
                p_type = classify_page_type(target_url, title=analysis.title, text_snippet=analysis.text_raw)

                # Extract business name and description if on home / about
                if p_type in (PageType.HOME, PageType.ABOUT):
                    if not business_info.name and analysis.title:
                        business_info.name = analysis.title.split("-")[0].split("|")[0].strip()
                    if not business_info.description and "description" in analysis.meta:
                        business_info.description = analysis.meta["description"]

                # Step 6e: Persist Per-Page Assets
                await self.storage.save_raw_html(target_url, fetch_res.raw_html)
                if fetch_res.rendered_html:
                    await self.storage.save_rendered_html(target_url, fetch_res.rendered_html)
                await self.storage.save_text(target_url, analysis.text_normalized)
                if fetch_res.xhr_data:
                    await self.storage.save_xhr_data(target_url, fetch_res.xhr_data)

                # Step 6f: Handle Linked Documents (PDFs)
                doc_items = []
                for link in analysis.links:
                    if link.internal and is_document_url(link.href):
                        doc = await self.pdf_extractor.process_pdf(link.href)
                        if doc:
                            doc_items.append(doc)

                page_res = PageResult(
                    url=target_url,
                    final_url=fetch_res.final_url,
                    status_code=fetch_res.status_code,
                    redirect_chain=fetch_res.redirect_chain,
                    redirect_type=fetch_res.redirect_type,
                    page_type=p_type,
                    content_hash=content_hash,
                    fetched_with=fetch_res.fetched_with,
                    html_analysis=analysis,
                    xhr_data=fetch_res.xhr_data,
                    documents=doc_items,
                )
                page_results.append(page_res)
                await self.frontier.mark_status(target_url, FrontierStatus.DONE)
                crawled_count += 1

                # Step 6g: Feed newly discovered links into frontier
                if target_depth < self.max_depth:
                    for link in analysis.links:
                        if not link.internal:
                            continue
                        candidate_url = link.href
                        skip, skip_reason = should_skip_url(candidate_url, max_depth=self.max_depth, depth=target_depth + 1)
                        if skip:
                            await self.frontier.add_url(
                                candidate_url,
                                depth=target_depth + 1,
                                status=FrontierStatus.SKIPPED,
                                skip_reason=skip_reason,
                            )
                        else:
                            prio = calculate_url_priority(candidate_url, depth=target_depth + 1)
                            await self.frontier.add_url(candidate_url, depth=target_depth + 1, priority=prio)

        finally:
            # Clean up browser and connections
            await self.browser_fetcher.close()

        # Deduplicate business entities
        business_info.phones = list({p.value: p for p in business_info.phones}.values())
        business_info.emails = list({e.value: e for e in business_info.emails}.values())
        business_info.social = list({s.url: s for s in business_info.social}.values())
        business_info.working_hours = list({w.text: w for w in business_info.working_hours}.values())

        # Collect skipped items from SQLite frontier
        skipped_records = await self.frontier.get_all_skipped()
        skipped_items = [
            SkippedItem(url=u, reason=SkipReason(r) if r in [e.value for e in SkipReason] else SkipReason.DUPLICATE)
            for u, r in skipped_records
        ]

        site_knowledge = SiteKnowledge(
            site=site_info,
            business=business_info,
            pages=page_results,
            skipped=skipped_items,
        )

        await self._persist_final(site_knowledge, started_at, start_time)
        return site_knowledge

    async def _persist_final(
        self,
        site_knowledge: SiteKnowledge,
        started_at: str,
        start_time: float,
    ) -> None:
        """Saves site.json and report.json atomically."""
        duration = time.monotonic() - start_time
        frontier_stats = await self.frontier.get_stats()

        report = generate_coverage_report(
            job_id=self.job_id,
            domain=self.domain,
            root_url=self.root_url,
            started_at=started_at,
            frontier_stats=frontier_stats,
            site_knowledge=site_knowledge,
            duration_seconds=duration,
            site_down=self.site_down,
        )

        await self.storage.save_site_json(site_knowledge)
        await self.storage.save_report_json(report)
        await self.frontier.close()
        self.logger.info(
            f"Crawl job {self.job_id} finished in {duration:.2f}s. Pages crawled: {len(site_knowledge.pages)}"
        )
