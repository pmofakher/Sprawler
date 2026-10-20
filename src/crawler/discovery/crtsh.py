"""Certificate transparency discovery via crt.sh."""

from typing import List, Set
import httpx

from crawler.core.constants import DEFAULT_USER_AGENT
from crawler.core.logging import logger
from crawler.detect.site_down import check_dns
from crawler.frontier.normalizer import get_registrable_domain


async def discover_crtsh_subdomains(
    domain: str,
    timeout: float = 10.0,
    user_agent: str = DEFAULT_USER_AGENT,
) -> List[str]:
    """Queries crt.sh for known subdomains belonging to the target domain."""
    clean_domain = get_registrable_domain(domain)
    url = f"https://crt.sh/?q=%.{clean_domain}&output=json"

    found_hosts: Set[str] = set()

    try:
        async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
            resp = await client.get(url, headers={"User-Agent": user_agent})
            if resp.status_code == 200:
                entries = resp.json()
                for entry in entries:
                    name_value = entry.get("name_value", "")
                    for candidate in name_value.split("\n"):
                        candidate = candidate.strip().lower()
                        # Exclude wildcards
                        if candidate.startswith("*."):
                            candidate = candidate[2:]
                        if candidate.endswith(clean_domain):
                            found_hosts.add(candidate)
    except Exception as exc:
        logger.debug(f"crt.sh query for {clean_domain} failed or timed out: {exc}")
        return []

    # Validate that discovered subdomains actively resolve via DNS
    active_subdomains: List[str] = []
    for host in found_hosts:
        if await check_dns(host):
            active_subdomains.append(f"https://{host}/")

    logger.info(
        f"Discovered {len(active_subdomains)} active resolving subdomains via crt.sh for {clean_domain}",
        extra={"domain": clean_domain},
    )
    return active_subdomains
