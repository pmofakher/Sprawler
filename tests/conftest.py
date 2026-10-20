"""Pytest test configuration and fixtures."""

import sys
from pathlib import Path
import pytest

# Add src to python path for testing
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


@pytest.fixture
def sample_persian_raw_text():
    return "شركت ما با شماره تلفن ۰۲۱-۸۸۷۷۶۶۵۵ و ایمیل info@example.com در حال فعاليت مي‌باشد.   \n\n\n  آدرس: خيابان وليعصر."


@pytest.fixture
def sample_html_with_entities():
    return """
    <!DOCTYPE html>
    <html lang="fa">
    <head>
        <title>فروشگاه گل و گیاه لند | درباره ما</title>
        <meta name="description" content="مرکز ارائه خدمات گیاهان آپارتمانی و مشاوره نگهداری">
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "LocalBusiness",
            "name": "پلنت لند تهران",
            "telephone": "+98-21-22334455"
        }
        </script>
    </head>
    <body>
        <header>
            <nav>
                <a href="/about-us">درباره ما</a>
                <a href="/contact">تماس با ما</a>
                <a href="/faq">سوالات متداول</a>
                <a href="/shop/product/123">خرید گلدان</a>
                <a href="/blog/care-tips">راهنمای نگهداری گیاهان</a>
            </nav>
        </header>
        <main>
            <h1>خدمات نگهداری گیاهان آپارتمانی</h1>
            <p>پلنت لند با ۱۰ سال سابقه درخشان در زمینه طراحی فضای سبز فعال است.</p>
            <p>شماره تماس مستقیم: 09121112233 یا ۰۲۱-۸۸۹۹۰۰۱۱</p>
            <p>ایمیل رسمی: support@plantlandtehran.com</p>
            <p>ساعات کاری: شنبه تا چهارشنبه ۹ الی ۱۸</p>
            <p><a href="https://maps.google.com/?q=35.7219,51.3347">مشاهده نقشه ما</a></p>
            <a href="https://instagram.com/plantlandtehran">اینستاگرام ما</a>
        </main>
        <footer>
            <p>آدرس: تهران، خیابان ولیعصر، پلاک ۱۰۰</p>
        </footer>
    </body>
    </html>
    """
