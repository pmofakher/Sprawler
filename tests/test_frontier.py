"""Unit tests for the persistent SQLite queue frontier and crash recovery."""

import tempfile
from pathlib import Path
import pytest
from crawler.domain.enums import FrontierStatus, SkipReason
from crawler.frontier.sqlite_frontier import SqliteFrontier


@pytest.mark.asyncio
async def test_frontier_lifecycle_and_priority():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_frontier.db"
        frontier = SqliteFrontier(db_path)
        await frontier.initialize()

        # Add URLs with different priorities
        await frontier.add_url("https://example.com/low", depth=2, priority=20)
        await frontier.add_url("https://example.com/high", depth=1, priority=90)
        await frontier.add_url("https://example.com/medium", depth=1, priority=50)

        # High priority should be returned first
        item1 = await frontier.get_next_url()
        assert item1 is not None
        assert item1.url == "https://example.com/high"
        assert item1.status == FrontierStatus.IN_PROGRESS

        # Medium priority second
        item2 = await frontier.get_next_url()
        assert item2 is not None
        assert item2.url == "https://example.com/medium"

        # Mark done
        await frontier.mark_status(item1.url, FrontierStatus.DONE)
        stats = await frontier.get_stats()
        assert stats["done"] == 1
        assert stats["in_progress"] == 1
        assert stats["pending"] == 1

        await frontier.close()


@pytest.mark.asyncio
async def test_frontier_crash_recovery():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "crash_test.db"

        # Session 1: fetch an item to leave it 'in_progress' and simulate a crash
        frontier = SqliteFrontier(db_path)
        await frontier.initialize()
        await frontier.add_url("https://example.com/task-1", priority=50)
        item = await frontier.get_next_url()
        assert item.status == FrontierStatus.IN_PROGRESS
        await frontier.close()

        # Session 2: re-initialize after crash
        recovered_frontier = SqliteFrontier(db_path)
        await recovered_frontier.initialize()

        # Item should be automatically reset to 'pending'
        next_item = await recovered_frontier.get_next_url()
        assert next_item is not None
        assert next_item.url == "https://example.com/task-1"

        await recovered_frontier.close()
