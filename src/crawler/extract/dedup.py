"""Content hashing, duplicate detection, and boilerplate removal across pages."""

import hashlib
from typing import Dict, Set


def compute_content_hash(text: str) -> str:
    """Computes a SHA-256 hash of normalized text content."""
    if not text:
        return ""
    clean = " ".join(text.split())
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()


class ContentDeduplicator:
    """Tracks seen content hashes and identifies repeating boilerplate lines across a crawl session."""

    def __init__(self):
        self._seen_hashes: Set[str] = set()
        self._line_occurrences: Dict[str, int] = {}

    def is_duplicate_content(self, content_hash: str) -> bool:
        """Checks if exact text content hash has already been encountered."""
        if not content_hash:
            return False
        if content_hash in self._seen_hashes:
            return True
        self._seen_hashes.add(content_hash)
        return False

    def register_page_lines(self, text: str) -> None:
        """Registers non-empty lines to build a site-wide boilerplate frequency map."""
        if not text:
            return
        for line in set(text.split("\n")):
            cleaned = line.strip()
            if len(cleaned) > 10:
                self._line_occurrences[cleaned] = self._line_occurrences.get(cleaned, 0) + 1

    def strip_site_boilerplate(self, text: str, threshold: int = 4) -> str:
        """Filters out lines that appear repeatedly on more than `threshold` pages (e.g. repeated footer/header)."""
        if not text:
            return ""
        retained = []
        for line in text.split("\n"):
            cleaned = line.strip()
            if self._line_occurrences.get(cleaned, 0) < threshold:
                retained.append(line)
        return "\n".join(retained)
