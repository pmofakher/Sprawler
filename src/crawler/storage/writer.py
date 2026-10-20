"""Atomic disk storage and artifact persistence for per-site crawl assets."""

import hashlib
import json
from pathlib import Path
from typing import Any, List, Optional
from pydantic import BaseModel

from crawler.domain.models import SiteKnowledge, SiteReport, XhrData


def compute_url_hash(url: str) -> str:
    """Computes a consistent MD5 hex hash from a URL to use as filesystem keys."""
    return hashlib.md5(url.encode("utf-8")).hexdigest()


class SiteStorage:
    """Encapsulates file persistence and layout for a specific crawled domain."""

    def __init__(self, base_data_dir: Path, domain: str):
        # Sanitize domain name for Windows & POSIX safe path
        safe_domain = "".join(c if c.isalnum() or c in ".-_" else "_" for c in domain)
        self.site_dir = base_data_dir / safe_domain

        self.html_raw_dir = self.site_dir / "html" / "raw"
        self.html_rendered_dir = self.site_dir / "html" / "rendered"
        self.text_dir = self.site_dir / "text"
        self.xhr_dir = self.site_dir / "xhr"
        self.files_dir = self.site_dir / "files"
        self.logs_dir = self.site_dir / "logs"

        self.site_json_path = self.site_dir / "site.json"
        self.report_json_path = self.site_dir / "report.json"
        self.frontier_db_path = self.site_dir / "frontier.db"
        self.log_file_path = self.logs_dir / "crawl.log"

    def initialize_directories(self) -> None:
        """Creates all requisite directory structures on the filesystem."""
        for path in [
            self.site_dir,
            self.html_raw_dir,
            self.html_rendered_dir,
            self.text_dir,
            self.xhr_dir,
            self.files_dir,
            self.logs_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    async def save_raw_html(self, url: str, content: str) -> Path:
        """Saves raw HTML payload to disk."""
        url_hash = compute_url_hash(url)
        dest = self.html_raw_dir / f"{url_hash}.html"
        dest.write_text(content, encoding="utf-8", errors="replace")
        return dest

    async def save_rendered_html(self, url: str, content: str) -> Path:
        """Saves post-JS rendered DOM to disk."""
        url_hash = compute_url_hash(url)
        dest = self.html_rendered_dir / f"{url_hash}.html"
        dest.write_text(content, encoding="utf-8", errors="replace")
        return dest

    async def save_text(self, url: str, content: str) -> Path:
        """Saves clean normalized text to disk."""
        url_hash = compute_url_hash(url)
        dest = self.text_dir / f"{url_hash}.txt"
        dest.write_text(content, encoding="utf-8", errors="replace")
        return dest

    async def save_xhr_data(self, url: str, xhr_list: List[XhrData]) -> Optional[Path]:
        """Saves captured API responses for a page."""
        if not xhr_list:
            return None
        url_hash = compute_url_hash(url)
        dest = self.xhr_dir / f"{url_hash}.json"
        serialized = [item.model_dump() for item in xhr_list]
        dest.write_text(json.dumps(serialized, ensure_ascii=False, indent=2), encoding="utf-8")
        return dest

    async def save_atomic_json(self, target_file: Path, data: BaseModel) -> None:
        """Writes JSON models atomically using a temporary file and replace to prevent partial reads."""
        temp_file = target_file.with_suffix(".tmp")
        json_data = data.model_dump_json(indent=2)

        # Write to temporary file
        temp_file.write_text(json_data, encoding="utf-8")
        # Atomic rename
        temp_file.replace(target_file)

    async def save_site_json(self, site_knowledge: SiteKnowledge) -> None:
        """Atomically saves the aggregated business knowledge site.json."""
        await self.save_atomic_json(self.site_json_path, site_knowledge)

    async def save_report_json(self, report: SiteReport) -> None:
        """Atomically saves the crawl coverage report.json."""
        await self.save_atomic_json(self.report_json_path, report)
