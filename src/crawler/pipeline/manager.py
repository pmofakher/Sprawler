"""Job manager holding active, cancelled, and completed background crawl tasks."""

import asyncio
import json
import uuid
from typing import Dict, Optional
from crawler.core.config import settings
from crawler.core.logging import logger
from crawler.domain.models import SiteKnowledge, SiteReport
from crawler.frontier.normalizer import get_registrable_domain, normalize_url
from crawler.pipeline.orchestrator import CrawlOrchestrator
from crawler.storage.writer import SiteStorage


class CrawlJob:
    """Represents a managed crawl session state."""

    def __init__(self, job_id: str, url: str, orchestrator: CrawlOrchestrator):
        self.job_id = job_id
        self.url = url
        self.orchestrator = orchestrator
        self.task: Optional[asyncio.Task] = None
        self.status: str = "pending"  # pending, running, completed, failed, cancelled
        self.error: Optional[str] = None
        self.result: Optional[SiteKnowledge] = None


class JobManager:
    """In-memory coordinator for asynchronous crawl jobs."""

    def __init__(self):
        self._jobs: Dict[str, CrawlJob] = {}
        self._lock = asyncio.Lock()

    async def start_job(
        self,
        url: str,
        max_pages: Optional[int] = None,
        max_depth: Optional[int] = None,
        allow_subdomains: Optional[bool] = None,
        use_crtsh: Optional[bool] = None,
        force_browser: Optional[bool] = None,
    ) -> str:
        """Spawns an asynchronous background crawl job and returns its unique job_id."""
        job_id = str(uuid.uuid4())
        norm_url = normalize_url(url)

        orchestrator = CrawlOrchestrator(
            root_url=norm_url,
            job_id=job_id,
            max_pages=max_pages,
            max_depth=max_depth,
            allow_subdomains=allow_subdomains,
            use_crtsh=use_crtsh,
            force_browser=force_browser,
        )

        job = CrawlJob(job_id=job_id, url=norm_url, orchestrator=orchestrator)
        job.status = "running"

        async def _worker():
            try:
                res = await orchestrator.run()
                job.result = res
                job.status = "completed"
            except asyncio.CancelledError:
                job.status = "cancelled"
            except Exception as exc:
                job.status = "failed"
                job.error = str(exc)
                logger.exception(f"Job {job_id} encountered fatal error: {exc}")

        task = asyncio.create_task(_worker())
        job.task = task

        async with self._lock:
            self._jobs[job_id] = job

        return job_id

    async def cancel_job(self, job_id: str) -> bool:
        """Cancels a running crawl job."""
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False

            job.orchestrator.is_cancelled = True
            if job.task and not job.task.done():
                job.task.cancel()
            job.status = "cancelled"
            return True

    async def resume_job(self, job_id: str) -> Optional[str]:
        """Resumes crawling for a previous job's domain using its persistent frontier."""
        async with self._lock:
            old_job = self._jobs.get(job_id)
            if not old_job:
                return None
            target_url = old_job.url

        # Start fresh job instance targeting same URL and frontier database
        return await self.start_job(url=target_url)

    async def get_job(self, job_id: str) -> Optional[CrawlJob]:
        async with self._lock:
            return self._jobs.get(job_id)

    async def get_job_result(self, job_id: str) -> Optional[SiteKnowledge]:
        """Retrieves in-memory result or reads from disk."""
        job = await self.get_job(job_id)
        if job and job.result:
            return job.result

        # Fallback: attempt loading from disk if domain known
        if job:
            domain = get_registrable_domain(job.url)
            storage = SiteStorage(settings.data_dir, domain)
            if storage.site_json_path.exists():
                data = json.loads(storage.site_json_path.read_text(encoding="utf-8"))
                return SiteKnowledge.model_validate(data)
        return None

    async def get_job_report(self, job_id: str) -> Optional[SiteReport]:
        """Reads the site coverage report from disk."""
        job = await self.get_job(job_id)
        if not job:
            return None

        domain = get_registrable_domain(job.url)
        storage = SiteStorage(settings.data_dir, domain)
        if storage.report_json_path.exists():
            data = json.loads(storage.report_json_path.read_text(encoding="utf-8"))
            return SiteReport.model_validate(data)
        return None


# Global job manager singleton
job_manager = JobManager()
