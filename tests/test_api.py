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
        # Private loopback should be blocked by SSRF guard
        resp = await client.post("/sprawl", json={"url": "http://127.0.0.1:8080/"})
        assert resp.status_code == 400
        assert "Security violation" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_api_sprawl_ssrf_protection_private_ip():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/sprawl", json={"url": "http://192.168.1.1/"})
        assert resp.status_code == 400
        assert "Security violation" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_api_sprawl_missing_target():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/sprawl", json={})
        assert resp.status_code == 400
        assert "Either 'url' or 'domain' must be provided" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_api_sprawl_invalid_scheme():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/sprawl", json={"url": "ftp://example.com/"})
        assert resp.status_code == 400
        assert "Invalid URL" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_api_sprawl_success(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "data_dir", tmp_path)

    mock_knowledge = SiteKnowledge(
        site=SiteInfo(root_url="https://example.com", domain="example.com"),
        business=BusinessInfo(),
        pages=[],
        skipped=[],
    )

    monkeypatch.setattr(
        "crawler.api.routes.CrawlOrchestrator.run",
        AsyncMock(return_value=mock_knowledge),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/sprawl", json={"domain": "example.com"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["domain"] == "example.com"
        assert data["url"] == "https://example.com/"
        assert "site.json" in data["output_file"]
        assert "report.json" in data["report_file"]
        assert data["pages_crawled"] == 0
