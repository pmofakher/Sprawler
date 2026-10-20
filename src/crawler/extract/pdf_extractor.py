"""PDF document downloading, text extraction, and OCR fallback."""

import io
from pathlib import Path
from typing import Optional
import httpx
from pypdf import PdfReader

from crawler.core.constants import DEFAULT_USER_AGENT
from crawler.core.logging import logger
from crawler.domain.enums import SourceType
from crawler.domain.models import DocumentItem
from crawler.text.persian import normalize_persian_text


class PdfExtractor:
    """Extracts textual content from linked PDF documents, falling back to OCR when scanned."""

    def __init__(
        self,
        max_size_bytes: int = 15 * 1024 * 1024,
        ocr_enabled: bool = True,
        ocr_languages: str = "fas+eng",
        user_agent: str = DEFAULT_USER_AGENT,
    ):
        self.max_size_bytes = max_size_bytes
        self.ocr_enabled = ocr_enabled
        self.ocr_languages = ocr_languages
        self.user_agent = user_agent

    async def process_pdf(self, url: str, timeout: float = 20.0) -> Optional[DocumentItem]:
        """Downloads PDF within size limits and extracts text (native or OCR)."""
        filename = Path(url.split("?")[0]).name or "document.pdf"

        try:
            async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
                resp = await client.get(url, headers={"User-Agent": self.user_agent})
                if resp.status_code != 200 or not resp.content:
                    return None

                content_len = len(resp.content)
                if content_len > self.max_size_bytes:
                    logger.warning(f"PDF {url} exceeds max size {self.max_size_bytes} bytes. Skipping.")
                    return None

                # 1. Native PDF text extraction
                extracted_pages = []
                try:
                    pdf_stream = io.BytesIO(resp.content)
                    reader = PdfReader(pdf_stream)
                    for page in reader.pages:
                        page_text = page.extract_text()
                        if page_text:
                            extracted_pages.append(page_text.strip())
                except Exception as exc:
                    logger.debug(f"Native PDF extraction failed for {url}: {exc}")

                combined_text = "\n".join(extracted_pages).strip()
                source_type = SourceType.PDF

                # 2. Scanned PDF fallback -> OCR
                if not combined_text and self.ocr_enabled:
                    try:
                        import pytesseract
                        from PIL import Image

                        # Extract images from PDF pages and OCR
                        pdf_stream.seek(0)
                        reader = PdfReader(pdf_stream)
                        ocr_chunks = []
                        for page in reader.pages:
                            for img_obj in page.images:
                                img = Image.open(io.BytesIO(img_obj.data))
                                ocr_text = pytesseract.image_to_string(img, lang=self.ocr_languages)
                                if ocr_text.strip():
                                    ocr_chunks.append(ocr_text.strip())

                        if ocr_chunks:
                            combined_text = "\n".join(ocr_chunks).strip()
                            source_type = SourceType.OCR
                    except Exception as ocr_exc:
                        logger.debug(f"OCR fallback failed or Tesseract unavailable for {url}: {ocr_exc}")

                if not combined_text:
                    return None

                norm_text = normalize_persian_text(combined_text)

                return DocumentItem(
                    url=url,
                    filename=filename,
                    source_type=source_type,
                    text_raw=combined_text,
                    text_normalized=norm_text,
                )

        except Exception as exc:
            logger.debug(f"Error fetching or parsing PDF {url}: {exc}")
            return None
