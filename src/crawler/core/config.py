"""Configuration management using Pydantic Settings."""

from pathlib import Path
from typing import List, Literal, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from crawler.core.constants import DEFAULT_USER_AGENT


class Settings(BaseSettings):
    """Central configuration for Sprawler crawler service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="SPRAWLER_",
        extra="ignore",
    )

    # General & Network
    app_name: str = "sprawler"
    debug: bool = False
    data_dir: Path = Field(default=Path("./data"))
    user_agent: str = Field(default=DEFAULT_USER_AGENT)
    request_timeout: float = Field(default=20.0, description="General HTTP timeout in seconds")
    connect_timeout: float = Field(default=10.0, description="HTTP connection timeout in seconds")

    # Frontier & Limits
    max_concurrency: int = Field(default=5, ge=1, le=50, description="Global concurrency semaphore")
    max_pages_per_site: int = Field(default=200, ge=1, description="Upper bound of pages per crawl job")
    max_depth: int = Field(default=4, ge=0, description="Maximum crawl depth from root URL")
    max_page_size_bytes: int = Field(default=10 * 1024 * 1024, description="10MB max response size")
    politeness_delay_seconds: float = Field(default=0.5, ge=0.0, description="Delay between requests to the same domain")
    honor_crawl_delay: bool = Field(default=True, description="Respect robots.txt Crawl-delay directive if present")

    # Domain Scope & Discovery
    allow_subdomains: bool = Field(default=True, description="Whether subdomains of the root are in-scope")
    use_crtsh: bool = Field(default=False, description="Query crt.sh for certificate transparency subdomains")
    crtsh_timeout_seconds: float = Field(default=10.0, description="Timeout for crt.sh queries")

    # Browser & Playwright
    force_browser: bool = Field(default=False, description="Always use browser fetcher regardless of static/SSR detection")
    browser_headless: bool = Field(default=True, description="Run Chromium in headless mode")
    browser_timeout_ms: int = Field(default=30000, description="Browser navigation timeout in ms")
    networkidle_timeout_ms: int = Field(default=10000, description="Wait timeout for networkidle in ms")
    dom_quiet_window_ms: int = Field(default=500, description="MutationObserver quiet window wait in ms")
    dismiss_consent_walls: bool = Field(default=True, description="Auto-dismiss common cookie/consent banners")

    # Circuit Breaker & Resilience
    circuit_breaker_failure_threshold: int = Field(default=5, description="Consecutive errors to trip circuit to OPEN")
    circuit_breaker_recovery_timeout: float = Field(default=60.0, description="Seconds before testing half-open")
    circuit_breaker_half_open_success_threshold: int = Field(default=2, description="Consecutive successes to reset circuit")
    retry_max_attempts: int = Field(default=3, description="Max retries for transient HTTP errors")
    retry_min_wait_seconds: float = Field(default=1.0, description="Min backoff wait")
    retry_max_wait_seconds: float = Field(default=10.0, description="Max backoff wait with jitter")

    # Content & Persian Normalization
    persian_normalize_digits: Literal["latin", "persian", "keep"] = Field(
        default="latin",
        description="Target script for numeric digits: 'latin' converts to 0-9, 'persian' converts to ۰-۹",
    )
    unify_zwnj: bool = Field(default=True, description="Unify zero-width non-joiners (half-spaces)")

    # OCR & PDF Processing
    max_pdf_size_bytes: int = Field(default=15 * 1024 * 1024, description="15MB max PDF file size")
    ocr_enabled_for_pdf: bool = Field(default=True, description="OCR scanned PDFs when text extraction is blank")
    ocr_enabled_for_images: bool = Field(default=False, description="Optional OCR on informational image banners")
    ocr_languages: str = Field(default="fas+eng", description="Tesseract language string")

    # Server API
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)

    @field_validator("data_dir", mode="before")
    @classmethod
    def parse_data_dir(cls, v: object) -> Path:
        return Path(str(v)).resolve()


# Singleton config instance
settings = Settings()
