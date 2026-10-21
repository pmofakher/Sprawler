"""Unit and functional tests for the FastAPI HTTP endpoints."""

from unittest.mock import AsyncMock
import pytest
from httpx import ASGITransport, AsyncClient

from crawler.api.app import app
from crawler.core.config import settings
from crawler.domain.models import BusinessInfo, SiteInfo, SiteKnowledge


@pytest.mark.asyncio
async def test_api_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "sprawler"


@pytest.mark.asyncio
async def test_api_sprawl_ssrf_protection_loopback():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/sprawl", params={"url": "http://127.0.0.1:8080/"})
        assert resp.status_code == 400
        assert "Security violation" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_api_sprawl_ssrf_protection_private_ip():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/sprawl", params={"url": "http://192.168.1.1/"})
        assert resp.status_code == 400
        assert "Security violation" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_api_sprawl_missing_required_url():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # url is required parameter
        resp = await client.post("/sprawl")
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_api_sprawl_invalid_scheme():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/sprawl", params={"url": "ftp://example.com/"})
        assert resp.status_code == 400
        assert "Invalid URL" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_api_sprawl_success_only_url(monkeypatch, tmp_path):
    """Verifies that sprawl works with ONLY `url` provided, auto-deriving domain and defaults."""
    monkeypatch.setattr(settings, "data_dir", tmp_path)

    mock_knowledge = SiteKnowledge(
        site=SiteInfo(root_url="https://example.com", domain="example.com"),
        business=BusinessInfo(),
        pages=[],
        skipped=[],
    )

    captured_orchestrator = {}

    def mock_init(self, root_url, job_id, max_pages=None, max_depth=None, allow_subdomains=None, use_crtsh=None, force_browser=None):
        captured_orchestrator["root_url"] = root_url
        captured_orchestrator["max_pages"] = max_pages
        captured_orchestrator["max_depth"] = max_depth
        captured_orchestrator["allow_subdomains"] = allow_subdomains
        captured_orchestrator["force_browser"] = force_browser
        captured_orchestrator["use_crtsh"] = use_crtsh

    monkeypatch.setattr("crawler.api.routes.CrawlOrchestrator.__init__", mock_init)
    monkeypatch.setattr("crawler.api.routes.CrawlOrchestrator.run", AsyncMock(return_value=mock_knowledge))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # ONLY url is provided
        resp = await client.post("/sprawl", params={"url": "https://example.com"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["domain"] == "example.com"
        assert data["url"] == "https://example.com/"
        assert "site.json" in data["output_file"]
        assert "report.json" in data["report_file"]
        assert data["pages_crawled"] == 0

        # Verify defaults were passed correctly
        assert captured_orchestrator["max_pages"] == 50
        assert captured_orchestrator["max_depth"] == 3
        assert captured_orchestrator["allow_subdomains"] is True
        assert captured_orchestrator["force_browser"] is False
        assert captured_orchestrator["use_crtsh"] is False
