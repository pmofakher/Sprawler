"""XHR/fetch JSON payload analyzer for API content and link extraction."""

from typing import Any, List, Set, Tuple
from urllib.parse import urlparse

from crawler.frontier.filter import should_skip_url
from crawler.frontier.normalizer import is_in_domain_scope, normalize_url


def analyze_xhr_payload(
    data: Any,
    base_url: str,
    registrable_domain: str,
    allow_subdomains: bool = True,
) -> Tuple[str, List[str]]:
    """Recursively walks JSON structures to extract textual business content and discovered URLs.

    Returns:
      (aggregated_text, discovered_urls)
    """
    text_chunks: List[str] = []
    found_urls: Set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                # Check for common text keys
                if isinstance(k, str) and any(
                    token in k.lower() for token in ("title", "content", "desc", "text", "body", "about", "address", "phone")
                ):
                    if isinstance(v, str) and len(v.strip()) > 3:
                        text_chunks.append(v.strip())

                # Check for URL keys
                if isinstance(k, str) and any(token in k.lower() for token in ("url", "href", "link")):
                    if isinstance(v, str) and (v.startswith("http") or v.startswith("/")):
                        try:
                            norm = normalize_url(v, base_url=base_url)
                            if is_in_domain_scope(norm, registrable_domain, allow_subdomains):
                                skip, _ = should_skip_url(norm)
                                if not skip:
                                    found_urls.add(norm)
                        except Exception:
                            pass

                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, str):
            # If string looks like a full URL
            if node.startswith("http://") or node.startswith("https://"):
                try:
                    norm = normalize_url(node)
                    if is_in_domain_scope(norm, registrable_domain, allow_subdomains):
                        skip, _ = should_skip_url(norm)
                        if not skip:
                            found_urls.add(norm)
                except Exception:
                    pass

    walk(data)
    aggregated_text = "\n".join(text_chunks)
    return aggregated_text, list(found_urls)
