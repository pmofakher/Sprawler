"""Unit and functional tests for the FastAPI HTTP endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from crawler.api.app import app


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
async def test_api_crawl_ssrf_protection():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Private loopback should be blocked by SSRF guard
        resp = await client.post("/crawl", json={"url": "http://127.0.0.1:8080/"})
        assert resp.status_code == 400
        assert "Security violation" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_api_analyze_url_ssrf_protection():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/analyze/url", json={"url": "http://192.168.1.1/"})
        assert resp.status_code == 400
        assert "private/loopback" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_api_get_nonexistent_job():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/crawl/non-existent-id")
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_cancel_nonexistent_job():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/crawl/non-existent-id/cancel")
        assert resp.status_code == 404
