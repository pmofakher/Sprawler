"""Headless Chromium browser fetcher using Playwright with XHR sniffing and DOM stabilization."""

import asyncio
import json
from typing import List, Optional
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from crawler.core.constants import CONSENT_SELECTORS, DEFAULT_USER_AGENT
from crawler.core.logging import logger
from crawler.detect.redirect import classify_redirect_hop
from crawler.domain.enums import RedirectType
from crawler.domain.models import XhrData
from crawler.fetch.interface import Fetcher, FetcherResult

# DOM mutation observer script to ensure DOM stability
DOM_STABILITY_SCRIPT = """
() => new Promise((resolve) => {
    let timer;
    const observer = new MutationObserver(() => {
        clearTimeout(timer);
        timer = setTimeout(() => {
            observer.disconnect();
            resolve(true);
        }, 500);
    });
    observer.observe(document.body, { childList: true, subtree: true, attributes: true });
    // Safety fallback timeout
    setTimeout(() => {
        observer.disconnect();
        resolve(true);
    }, 3000);
})
"""


class BrowserFetcher(Fetcher):
    """Manages an async Playwright Chromium browser pool with per-request isolation."""

    def __init__(
        self,
        headless: bool = True,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout_ms: int = 30000,
        networkidle_timeout_ms: int = 10000,
        dismiss_consent_walls: bool = True,
    ):
        self.headless = headless
        self.user_agent = user_agent
        self.timeout_ms = timeout_ms
        self.networkidle_timeout_ms = networkidle_timeout_ms
        self.dismiss_consent_walls = dismiss_consent_walls

        self._playwright = None
        self._browser: Optional[Browser] = None
        self._lock = asyncio.Lock()

    async def _ensure_browser(self) -> Browser:
        """Starts Playwright and launches Chromium if not active or after a crash."""
        async with self._lock:
            if self._browser is None or not self._browser.is_connected():
                if self._playwright is None:
                    self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    headless=self.headless,
                    args=[
                        "--disable-gpu",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-setuid-sandbox",
                    ],
                )
            return self._browser

    async def fetch(self, url: str) -> FetcherResult:
        """Navigates to URL in an isolated context, listens to XHR, waits for stability, and dumps DOM."""
        browser = await self._ensure_browser()

        context: Optional[BrowserContext] = None
        page: Optional[Page] = None
        captured_xhr: List[XhrData] = []
        redirect_chain: List[str] = [url]

        try:
            # Create fresh context with Persian locale and Tehran timezone
            context = await browser.new_context(
                user_agent=self.user_agent,
                locale="fa-IR",
                timezone_id="Asia/Tehran",
                extra_http_headers={"Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8"},
                ignore_https_errors=True,
            )
            page = await context.new_page()

            # Track frame navigations (e.g. JS location changes)
            def on_frame_navigated(frame):
                if frame == page.main_frame:
                    current_nav = frame.url
                    if current_nav not in redirect_chain:
                        redirect_chain.append(current_nav)

            page.on("framenavigated", on_frame_navigated)

            # XHR / fetch response sniffer
            async def on_response(response):
                try:
                    c_type = response.headers.get("content-type", "")
                    if "application/json" in c_type:
                        body_text = await response.text()
                        if body_text and len(body_text) < 1024 * 1024:  # 1MB limit for XHR captures
                            try:
                                json_val = json.loads(body_text)
                                captured_xhr.append(
                                    XhrData(
                                        url=response.url,
                                        method=response.request.method,
                                        status=response.status,
                                        content_type=c_type,
                                        data=json_val,
                                    )
                                )
                            except Exception:
                                pass
                except Exception:
                    pass

            page.on("response", on_response)

            # Navigate to the target page
            resp = await page.goto(
                url,
                timeout=self.timeout_ms,
                wait_until="domcontentloaded",
            )

            # Wait for network idle
            try:
                await page.wait_for_load_state("networkidle", timeout=self.networkidle_timeout_ms)
            except Exception:
                # Networkidle timeout is non-fatal if DOM is already populated
                pass

            # Safe auto-dismiss cookie and consent popups
            if self.dismiss_consent_walls:
                for selector in CONSENT_SELECTORS:
                    try:
                        elem = await page.query_selector(selector)
                        if elem and await elem.is_visible():
                            await elem.click(timeout=1000)
                            await asyncio.sleep(0.3)
                    except Exception:
                        pass

            # Check for transitional loading pages (e.g. "Redirecting...", "Loading...")
            for _ in range(3):
                title = (await page.title()).lower()
                body_sample = (await page.content())[:2000].lower()
                if any(w in title or w in body_sample for w in ["redirecting", "لطفا صبر کنید", "loading...", "در حال بارگذاری"]):
                    await asyncio.sleep(1.0)
                else:
                    break

            # Execute DOM quiet-window observer
            try:
                await page.evaluate(DOM_STABILITY_SCRIPT)
            except Exception:
                pass

            final_url = page.url
            if final_url not in redirect_chain:
                redirect_chain.append(final_url)

            rendered_html = await page.content()
            status_code = resp.status if resp else 200

            # Determine redirect type
            redirect_type = classify_redirect_hop(
                initial_url=url,
                final_url=final_url,
                status_code=status_code,
                is_js=len(redirect_chain) > 2,
            )

            return FetcherResult(
                url=url,
                final_url=final_url,
                status_code=status_code,
                headers={},
                raw_html=rendered_html,
                rendered_html=rendered_html,
                redirect_chain=redirect_chain,
                redirect_type=redirect_type,
                fetched_with="playwright",
                xhr_data=captured_xhr,
                error=None,
            )

        except Exception as exc:
            logger.debug(f"BrowserFetcher execution error on {url}: {exc}")
            return FetcherResult(
                url=url,
                final_url=url,
                status_code=0,
                headers={},
                raw_html="",
                rendered_html=None,
                redirect_chain=[url],
                redirect_type=RedirectType.NONE,
                fetched_with="playwright",
                xhr_data=[],
                error=str(exc),
            )
        finally:
            # Always cleanly close page and context to avoid resource leaks
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
            if context:
                try:
                    await context.close()
                except Exception:
                    pass

    async def close(self) -> None:
        """Closes the browser instance and Playwright runtime."""
        async with self._lock:
            if self._browser:
                try:
                    await self._browser.close()
                except Exception:
                    pass
                self._browser = None
            if self._playwright:
                try:
                    await self._playwright.stop()
                except Exception:
                    pass
                self._playwright = None
