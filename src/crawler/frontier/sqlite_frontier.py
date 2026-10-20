"""Persistent SQLite-backed queue frontier with crash-recovery and resume support."""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import aiosqlite

from crawler.domain.enums import FrontierStatus, SkipReason


class FrontierItem:
    """Represents a scheduled crawl task item in the frontier."""

    def __init__(
        self,
        url: str,
        depth: int,
        priority: int,
        status: FrontierStatus,
        attempts: int = 0,
        last_error: Optional[str] = None,
        skip_reason: Optional[SkipReason] = None,
    ):
        self.url = url
        self.depth = depth
        self.priority = priority
        self.status = status
        self.attempts = attempts
        self.last_error = last_error
        self.skip_reason = skip_reason


class SqliteFrontier:
    """Asynchronous SQLite queue managing discovery, deduplication, and resume states."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initializes tables, indices, and recovers any interrupted tasks."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self.db_path))
        self._db.row_factory = aiosqlite.Row

        # Table schema for persistent URLs
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS frontier (
                url TEXT PRIMARY KEY,
                depth INTEGER NOT NULL DEFAULT 0,
                priority INTEGER NOT NULL DEFAULT 50,
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                skip_reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        # Index for efficient priority ordering of pending URLs
        await self._db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_frontier_status_priority
            ON frontier (status, priority DESC, depth ASC)
            """
        )

        # Crash recovery: reset any 'in_progress' tasks back to 'pending'
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            """
            UPDATE frontier
            SET status = 'pending', updated_at = ?
            WHERE status = 'in_progress'
            """,
            (now,),
        )
        await self._db.commit()

    async def add_url(
        self,
        url: str,
        depth: int = 0,
        priority: int = 50,
        status: FrontierStatus = FrontierStatus.PENDING,
        skip_reason: Optional[SkipReason] = None,
    ) -> bool:
        """Inserts a new URL if not already tracked. Returns True if inserted, False if duplicate."""
        if not self._db:
            await self.initialize()

        async with self._lock:
            now = datetime.now(timezone.utc).isoformat()
            try:
                assert self._db is not None
                await self._db.execute(
                    """
                    INSERT INTO frontier (url, depth, priority, status, attempts, skip_reason, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 0, ?, ?, ?)
                    """,
                    (
                        url,
                        depth,
                        priority,
                        status.value,
                        skip_reason.value if skip_reason else None,
                        now,
                        now,
                    ),
                )
                await self._db.commit()
                return True
            except aiosqlite.IntegrityError:
                # URL already exists in database (deduplication)
                return False

    async def get_next_url(self) -> Optional[FrontierItem]:
        """Fetches the highest priority pending URL and transitions it to 'in_progress' atomically."""
        if not self._db:
            await self.initialize()

        async with self._lock:
            assert self._db is not None
            cursor = await self._db.execute(
                """
                SELECT url, depth, priority, status, attempts, last_error, skip_reason
                FROM frontier
                WHERE status = 'pending'
                ORDER BY priority DESC, depth ASC, attempts ASC
                LIMIT 1
                """
            )
            row = await cursor.fetchone()
            if not row:
                return None

            url = row["url"]
            now = datetime.now(timezone.utc).isoformat()
            await self._db.execute(
                """
                UPDATE frontier
                SET status = 'in_progress', attempts = attempts + 1, updated_at = ?
                WHERE url = ?
                """,
                (now, url),
            )
            await self._db.commit()

            return FrontierItem(
                url=url,
                depth=row["depth"],
                priority=row["priority"],
                status=FrontierStatus.IN_PROGRESS,
                attempts=row["attempts"] + 1,
                last_error=row["last_error"],
                skip_reason=SkipReason(row["skip_reason"]) if row["skip_reason"] else None,
            )

    async def mark_status(
        self,
        url: str,
        status: FrontierStatus,
        last_error: Optional[str] = None,
        skip_reason: Optional[SkipReason] = None,
    ) -> None:
        """Updates the status and error detail of a URL item."""
        if not self._db:
            await self.initialize()

        async with self._lock:
            assert self._db is not None
            now = datetime.now(timezone.utc).isoformat()
            await self._db.execute(
                """
                UPDATE frontier
                SET status = ?, last_error = ?, skip_reason = ?, updated_at = ?
                WHERE url = ?
                """,
                (
                    status.value,
                    last_error,
                    skip_reason.value if skip_reason else None,
                    now,
                    url,
                ),
            )
            await self._db.commit()

    async def get_stats(self) -> Dict[str, Any]:
        """Returns count statistics across all status values."""
        if not self._db:
            await self.initialize()

        async with self._lock:
            assert self._db is not None
            cursor = await self._db.execute(
                """
                SELECT status, count(*) as count
                FROM frontier
                GROUP BY status
                """
            )
            rows = await cursor.fetchall()
            counts = {r["status"]: r["count"] for r in rows}

            # Skipped breakdown
            cursor_skip = await self._db.execute(
                """
                SELECT skip_reason, count(*) as count
                FROM frontier
                WHERE status = 'skipped' AND skip_reason IS NOT NULL
                GROUP BY skip_reason
                """
            )
            skip_rows = await cursor_skip.fetchall()
            skipped_by_reason = {r["skip_reason"]: r["count"] for r in skip_rows}

            total = sum(counts.values())
            return {
                "total": total,
                "pending": counts.get("pending", 0),
                "in_progress": counts.get("in_progress", 0),
                "done": counts.get("done", 0),
                "failed": counts.get("failed", 0),
                "blocked": counts.get("blocked", 0),
                "skipped": counts.get("skipped", 0),
                "skipped_by_reason": skipped_by_reason,
            }

    async def get_all_skipped(self) -> List[Tuple[str, str]]:
        """Returns all skipped URLs and their reasons."""
        if not self._db:
            await self.initialize()

        assert self._db is not None
        cursor = await self._db.execute(
            """
            SELECT url, skip_reason
            FROM frontier
            WHERE status = 'skipped'
            """
        )
        rows = await cursor.fetchall()
        return [(r["url"], r["skip_reason"] or "unknown") for r in rows]

    async def close(self) -> None:
        """Closes the underlying SQLite connection gracefully."""
        if self._db:
            await self._db.close()
            self._db = None
