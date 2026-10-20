"""Asynchronous HTTP fetcher using httpx with redirect tracking and encoding detection."""

from typing import Dict, List, Optional
import httpx

from crawler.core.constants import DEFAULT_USER_AGENT
from crawler.core.exceptions import FetchTimeoutException
from crawler.core.logging import logger
from crawler.detect.redirect import classify_redirect_hop, detect_meta_refresh
from crawler.domain.enums import RedirectType
from crawler.fetch.interface import Fetcher, FetcherResult


class HttpFetcher(Fetcher):
    """Production async HTTP fetcher with redirect resolution and encoding safety."""

    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = 20.0,
        max_redirects: int = 10,
        max_page_size_bytes: int = 10 * 1024 * 1024,
    ):
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_redirects = max_redirects
        self.max_page_size_bytes = max_page_size_bytes

    async def fetch(self, url: str) -> FetcherResult:
        """Fetches the specified URL over HTTP/1.1 and HTTP/2."""
        redirect_chain: List[str] = [url]
        current_url = url
        final_redirect_type = RedirectType.NONE

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
        }

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                verify=False,
                follow_redirects=True,
                max_redirects=self.max_redirects,
            ) as client:
                response = await client.get(url, headers=headers)

                # Record redirect history
                if response.history:
                    for resp in response.history:
                        redirect_chain.append(str(resp.url))
                    final_url = str(response.url)
                    if final_url != redirect_chain[-1]:
                        redirect_chain.append(final_url)

                    # Classify initial vs final hop
                    final_redirect_type = classify_redirect_hop(
                        initial_url=url,
                        final_url=final_url,
                        status_code=response.history[0].status_code,
                    )
                else:
                    final_url = str(response.url)

                # Detect meta-refresh redirect if body is present
                raw_text = response.text
                meta_res = detect_meta_refresh(raw_text, final_url)
                if meta_res:
                    meta_target, _ = meta_res
                    if meta_target != final_url:
                        redirect_chain.append(meta_target)
                        final_redirect_type = RedirectType.META_REFRESH
                        final_url = meta_target

                resp_headers = {k: v for k, v in response.headers.items()}

                return FetcherResult(
                    url=url,
                    final_url=final_url,
                    status_code=response.status_code,
                    headers=resp_headers,
                    raw_html=raw_text,
                    rendered_html=None,
                    redirect_chain=redirect_chain,
                    redirect_type=final_redirect_type,
                    fetched_with="httpx",
                    xhr_data=[],
                    error=None,
                )

        except httpx.TimeoutException as exc:
            raise FetchTimeoutException(f"HTTP request timed out for {url}: {exc}")
        except Exception as exc:
            logger.debug(f"HttpFetcher error on {url}: {exc}")
            return FetcherResult(
                url=url,
                final_url=url,
                status_code=0,
                headers={},
                raw_html="",
                rendered_html=None,
                redirect_chain=[url],
                redirect_type=RedirectType.NONE,
                fetched_with="httpx",
                xhr_data=[],
                error=str(exc),
            )
