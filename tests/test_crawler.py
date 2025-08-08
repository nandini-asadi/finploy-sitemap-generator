"""Tests for crawler functionality."""

import asyncio
import tempfile
import os
from unittest.mock import Mock, AsyncMock, patch
import pytest
import aiohttp
from src.sitemap_generator.crawler import SitemapCrawler
from src.sitemap_generator.types import CrawlConfig, CrawlResult
from src.sitemap_generator.static_crawler import StaticCrawler
from src.sitemap_generator.utils import RateLimiter


@pytest.fixture
def test_config():
    """Create test configuration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield CrawlConfig(
            base_urls=["https://www.finploy.com"],
            max_depth=2,
            max_concurrent_requests=2,
            crawl_delay=0.1,
            request_timeout=5,
            database_path=os.path.join(tmpdir, "test.db"),
            sitemap_output_dir=os.path.join(tmpdir, "sitemaps"),
            enable_dynamic_crawling=False  # Disable for faster tests
        )


@pytest.mark.asyncio
async def test_crawler_initialization(test_config):
    """Test crawler initialization."""
    crawler = SitemapCrawler(test_config)
    
    await crawler.initialize()
    
    assert crawler.url_manager is not None
    assert crawler.static_crawler is not None
    assert crawler.sitemap_writer is not None
    assert crawler.session is not None
    
    await crawler.cleanup()


@pytest.mark.asyncio
async def test_add_base_urls(test_config):
    """Test adding base URLs to crawl queue."""
    crawler = SitemapCrawler(test_config)
    await crawler.initialize()
    
    try:
        await crawler._add_base_urls()
        
        # Check that base URLs were added
        stats = await crawler.url_manager.get_statistics()
        assert stats.total_urls_discovered == len(test_config.base_urls)
        
        # Check queue size
        queue_size = await crawler.url_manager.get_queue_size()
        assert queue_size == len(test_config.base_urls)
    
    finally:
        await crawler.cleanup()


@pytest.mark.asyncio
async def test_static_crawler_basic():
    """Test basic static crawler functionality."""
    # Mock HTML content
    mock_html = """
    <html>
        <body>
            <a href="/page1">Page 1</a>
            <a href="/page2">Page 2</a>
            <a href="https://external.com/page">External</a>
        </body>
    </html>
    """
    
    # Create mock session
    mock_response = Mock()
    mock_response.status = 200
    mock_response.headers = {'content-type': 'text/html'}
    mock_response.text = AsyncMock(return_value=mock_html)
    
    mock_session = Mock()
    mock_session.get = AsyncMock()
    mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
    mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)
    
    # Create crawler
    rate_limiter = RateLimiter(0.1)
    crawler = StaticCrawler(mock_session, rate_limiter)
    
    # Test crawling
    result = await crawler.crawl_url("https://www.finploy.com/test", 1)
    
    assert result.status_code == 200
    assert len(result.discovered_urls) >= 2  # Should find internal links
    
    # Check that external URLs are filtered out
    internal_urls = [url for url in result.discovered_urls if "finploy.com" in url]
    assert len(internal_urls) >= 2


@pytest.mark.asyncio
async def test_crawl_result_processing(test_config):
    """Test processing of crawl results."""
    crawler = SitemapCrawler(test_config)
    await crawler.initialize()
    
    try:
        # Create mock crawl results
        results = [
            CrawlResult(
                url="https://www.finploy.com/page1",
                status_code=200,
                discovered_urls=[
                    "https://www.finploy.com/page2",
                    "https://www.finploy.com/page3"
                ]
            ),
            CrawlResult(
                url="https://www.finploy.com/error",
                status_code=404,
                discovered_urls=[],
                error="Not found"
            )
        ]
        
        # Process results
        await crawler._process_crawl_results(results, depth=1)
        
        # Check statistics
        assert crawler.statistics.successful_crawls == 1
        assert crawler.statistics.failed_crawls == 1
        assert crawler.statistics.total_urls_crawled == 2
        
        # Check that new URLs were added
        stats = await crawler.url_manager.get_statistics()
        assert stats.total_urls_discovered >= 2  # At least the discovered URLs
    
    finally:
        await crawler.cleanup()


def test_url_classification():
    """Test URL classification for dynamic vs static crawling."""
    from src.sitemap_generator.config import is_dynamic_url, classify_url_type
    
    # Test dynamic URL detection
    assert is_dynamic_url("https://www.finploy.com/jobs") is True
    assert is_dynamic_url("https://www.finploy.com/jobs-in-london") is True
    assert is_dynamic_url("https://www.finploy.com/search?q=developer") is True
    assert is_dynamic_url("https://www.finploy.com/about") is False
    
    # Test URL type classification
    assert classify_url_type("https://www.finploy.com") == "homepage"
    assert classify_url_type("https://www.finploy.com/jobs") == "job_listing"
    assert classify_url_type("https://www.finploy.com/jobs/123") == "individual_job"
    assert classify_url_type("https://www.finploy.com/jobs-in-london") == "location_page"
    assert classify_url_type("https://www.finploy.com/company/abc") == "company_page"


def test_url_filtering():
    """Test URL filtering and validation."""
    from src.sitemap_generator.config import should_skip_url, is_target_domain
    
    # Test skip patterns
    assert should_skip_url("https://www.finploy.com/image.jpg") is True
    assert should_skip_url("https://www.finploy.com/document.pdf") is True
    assert should_skip_url("https://www.finploy.com/style.css") is True
    assert should_skip_url("mailto:test@example.com") is True
    assert should_skip_url("https://www.finploy.com/page") is False
    
    # Test domain filtering
    assert is_target_domain("https://www.finploy.com/page") is True
    assert is_target_domain("https://finploy.co.uk/page") is True
    assert is_target_domain("https://external.com/page") is False


@pytest.mark.asyncio
async def test_crawler_statistics(test_config):
    """Test crawler statistics tracking."""
    crawler = SitemapCrawler(test_config)
    await crawler.initialize()
    
    try:
        # Simulate some crawling activity
        crawler.statistics.total_urls_discovered = 100
        crawler.statistics.total_urls_crawled = 80
        crawler.statistics.successful_crawls = 70
        crawler.statistics.failed_crawls = 10
        crawler.statistics.static_pages_crawled = 60
        crawler.statistics.dynamic_pages_crawled = 10
        
        # Test success rate calculation
        assert crawler.statistics.success_rate == 87.5  # 70/80 * 100
        
        # Test statistics display (should not raise errors)
        crawler.print_statistics()
    
    finally:
        await crawler.cleanup()


def test_url_normalization():
    """Test URL normalization functionality."""
    from src.sitemap_generator.utils import normalize_url, deduplicate_urls
    
    # Test normalization
    assert normalize_url("https://example.com/page/") == "https://example.com/page"
    assert normalize_url("https://example.com/page#fragment") == "https://example.com/page"
    assert normalize_url("https://example.com/page?b=2&a=1") == "https://example.com/page?a=1&b=2"
    
    # Test deduplication
    urls = [
        "https://example.com/page1",
        "https://example.com/page2",
        "https://example.com/page1",  # Duplicate
        "https://example.com/page1/",  # Normalized duplicate
        "invalid-url",  # Invalid
    ]
    
    deduplicated = deduplicate_urls(urls)
    assert len(deduplicated) == 2
    assert "https://example.com/page1" in deduplicated
    assert "https://example.com/page2" in deduplicated


@pytest.mark.asyncio
async def test_rate_limiting():
    """Test rate limiting functionality."""
    import time
    
    rate_limiter = RateLimiter(0.1)  # 100ms delay
    
    start_time = time.time()
    
    # First request should be immediate
    await rate_limiter.wait()
    first_time = time.time()
    
    # Second request should be delayed
    await rate_limiter.wait()
    second_time = time.time()
    
    # Check that delay was applied
    delay = second_time - first_time
    assert delay >= 0.09  # Allow for small timing variations


@pytest.mark.asyncio
async def test_crawler_shutdown_handling(test_config):
    """Test graceful shutdown handling."""
    crawler = SitemapCrawler(test_config)
    await crawler.initialize()
    
    try:
        # Simulate shutdown request
        crawler._shutdown_requested = True
        
        # Crawl loop should exit early
        await crawler._crawl_loop()
        
        # Should complete without errors
        assert crawler._shutdown_requested is True
    
    finally:
        await crawler.cleanup()
