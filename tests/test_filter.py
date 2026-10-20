"""Unit tests for URL filtering rules and priority calculations."""

import pytest
from crawler.domain.enums import SkipReason
from crawler.frontier.filter import (
    calculate_url_priority,
    is_pagination_url,
    is_product_centric_url,
    should_skip_url,
)


def test_pagination_detection():
    # Query param based
    assert is_pagination_url("https://example.com/blog?page=2")
    assert is_pagination_url("https://example.com/news?p=3")
    assert is_pagination_url("https://example.com/list?offset=20")

    # Path based
    assert is_pagination_url("https://example.com/blog/page/2/")
    assert is_pagination_url("https://example.com/articles/p/4")

    # Non-pagination
    assert not is_pagination_url("https://example.com/about-us")
    assert not is_pagination_url("https://example.com/contact")


def test_product_detection():
    # Product detail / shop / cart / checkout
    assert is_product_centric_url("https://example.com/product/wooden-chair")
    assert is_product_centric_url("https://example.com/shop/category/indoor")
    assert is_product_centric_url("https://example.com/cart")
    assert is_product_centric_url("https://example.com/checkout")
    assert is_product_centric_url("https://example.com/shop?orderby=price")

    # Informational business pages
    assert not is_product_centric_url("https://example.com/about")
    assert not is_product_centric_url("https://example.com/services")
    assert not is_product_centric_url("https://example.com/faq")


def test_should_skip_url():
    # Skip pagination
    skip, reason = should_skip_url("https://example.com/blog?page=3")
    assert skip is True
    assert reason == SkipReason.PAGINATION

    # Skip product
    skip, reason = should_skip_url("https://example.com/product/123")
    assert skip is True
    assert reason == SkipReason.PRODUCT

    # Skip max depth
    skip, reason = should_skip_url("https://example.com/some/deep/page", max_depth=3, depth=4)
    assert skip is True
    assert reason == SkipReason.MAX_DEPTH_EXCEEDED

    # Keep valid business page
    skip, reason = should_skip_url("https://example.com/about-us", max_depth=4, depth=1)
    assert skip is False
    assert reason is None


def test_url_priority_scoring():
    # Home gets highest score
    assert calculate_url_priority("https://example.com/") == 100

    # Business pages get high score
    about_score = calculate_url_priority("https://example.com/about-us", depth=1)
    contact_score = calculate_url_priority("https://example.com/contact-us", depth=1)
    generic_score = calculate_url_priority("https://example.com/random-topic", depth=1)

    assert about_score > generic_score
    assert contact_score > generic_score
