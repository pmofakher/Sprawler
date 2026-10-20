"""Semantic page type classifier (home, about, contact, faq, blog, services, policies)."""

from urllib.parse import urlparse
from crawler.domain.enums import PageType


def classify_page_type(url: str, title: str = "", text_snippet: str = "") -> PageType:
    """Infers the functional business page category from URL tokens, title, and headings."""
    parsed = urlparse(url)
    path = parsed.path.lower().strip("/")
    title_lower = title.lower()
    combined = f"{path} {title_lower} {text_snippet[:300].lower()}"

    # 1. Home page
    if not path or path == "":
        return PageType.HOME

    # 2. Contact page
    if any(token in combined for token in ["contact", "contact-us", "tamas", "تماس", "ارتباط با ما", "شماره تماس"]):
        return PageType.CONTACT

    # 3. About page
    if any(token in combined for token in ["about", "about-us", "darbare", "درباره", "درباره ما", "تاریخچه", "تیم ما"]):
        return PageType.ABOUT

    # 4. FAQ page
    if any(token in combined for token in ["faq", "faqs", "سوالات متداول", "پرسش های متداول", "راهنما"]):
        return PageType.FAQ

    # 5. Policies & Terms
    if any(token in combined for token in ["policy", "privacy", "terms", "rules", "قوانین", "حریم خصوصی", "شرایط استفاده", "مرجوعی"]):
        return PageType.POLICIES

    # 6. Services & Portfolio
    if any(token in combined for token in ["service", "services", "khadamat", "خدمات", "سرویس‌ها", "نمونه کار"]):
        return PageType.SERVICES

    # 7. Blog & Articles
    if any(token in combined for token in ["blog", "article", "articles", "news", "mag", "بلاگ", "مقالات", "اخبار"]):
        return PageType.BLOG

    return PageType.OTHER
