"""Render type classification (Static vs. SSR vs. CSR) and SPA detection."""

from typing import Dict, Tuple
from bs4 import BeautifulSoup

from crawler.domain.enums import RenderType
from crawler.frontier.normalizer import get_registrable_domain


def detect_render_type_from_html(raw_html: str) -> Tuple[RenderType, float]:
    """Heuristic classifier evaluating raw HTML for SPA / CSR markers vs Static / SSR.

    Returns:
      (RenderType, confidence_score_between_0_and_1)
    """
    if not raw_html:
        return RenderType.CSR, 0.5

    soup = BeautifulSoup(raw_html, "html.parser")

    # 1. Inspect presence of text and meaningful tags
    body = soup.body
    if not body:
        return RenderType.CSR, 0.9

    meaningful_tags = body.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "a", "article", "section"])
    tag_count = len(meaningful_tags)
    body_text = body.get_text(strip=True)
    text_len = len(body_text)

    # 2. Check SPA Container roots
    has_empty_spa_root = False
    for root_id in ["root", "app", "__next", "__nuxt"]:
        elem = soup.find(id=root_id)
        if elem:
            # If the container element is completely empty or has no text
            if len(elem.get_text(strip=True)) < 30:
                has_empty_spa_root = True
                break

    # 3. Check framework markers
    has_next_data = bool(soup.find("script", id="__NEXT_DATA__"))
    has_nuxt_data = "__NUXT__" in raw_html
    has_react_marker = bool(soup.find(attrs={"data-reactroot": True})) or "react" in raw_html.lower()

    # Rule A: Empty container with minimal content and scripts -> CSR
    if has_empty_spa_root and text_len < 300:
        return RenderType.CSR, 0.95

    # Rule B: Next.js or Nuxt with pre-rendered content -> SSR
    if (has_next_data or has_nuxt_data) and (text_len > 400 or tag_count > 10):
        return RenderType.SSR, 0.90

    # Rule C: Significant text and tags present in raw HTML -> STATIC or SSR
    if text_len > 1000 and tag_count > 15:
        if has_next_data or has_nuxt_data or has_react_marker:
            return RenderType.SSR, 0.85
        return RenderType.STATIC, 0.85

    if text_len > 400 and tag_count > 8:
        return RenderType.STATIC, 0.70

    # Rule D: Minimal text with scripts -> likely CSR
    if text_len < 200:
        return RenderType.CSR, 0.80

    return RenderType.STATIC, 0.60


class RenderTypeCache:
    """Thread-safe cache holding detected render type per registrable domain."""

    def __init__(self):
        self._cache: Dict[str, Tuple[RenderType, float]] = {}

    def get(self, domain_or_url: str) -> Tuple[RenderType, float]:
        reg_domain = get_registrable_domain(domain_or_url)
        return self._cache.get(reg_domain, (RenderType.STATIC, 0.5))

    def set(self, domain_or_url: str, render_type: RenderType, confidence: float) -> None:
        reg_domain = get_registrable_domain(domain_or_url)
        self._cache[reg_domain] = (render_type, confidence)

    def contains(self, domain_or_url: str) -> bool:
        reg_domain = get_registrable_domain(domain_or_url)
        return reg_domain in self._cache


# Global render detector cache instance
render_cache = RenderTypeCache()
