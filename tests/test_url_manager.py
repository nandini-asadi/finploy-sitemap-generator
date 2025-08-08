"""Tests for URL manager functionality."""

import asyncio
import os
import tempfile
from datetime import datetime
import pytest
from src.sitemap_generator.url_manager import URLManager
from src.sitemap_generator.types import CrawlStatus


import pytest_asyncio

@pytest_asyncio.fixture
async def url_manager():
    """Create a temporary URL manager for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    manager = URLManager(db_path)
    await manager.initialize()
    
    yield manager
    
    await manager.close()
    os.unlink(db_path)


@pytest.mark.asyncio
async def test_add_url(url_manager):
    """Test adding URLs to the manager."""
    url = "https://www.finploy.com/test"
    
    # Add URL
    result = await url_manager.add_url(url, depth=1, is_dynamic=False)
    assert result is True
    
    # Adding same URL again should return False
    result = await url_manager.add_url(url, depth=1, is_dynamic=False)
    assert result is False


@pytest.mark.asyncio
async def test_add_urls_batch(url_manager):
    """Test batch URL addition."""
    urls = [
        ("https://www.finploy.com/test1", None, 1, False, 10),
        ("https://www.finploy.com/test2", None, 1, True, 20),
        ("https://www.finploy.com/test3", None, 2, False, 5),
    ]
    
    added_count = await url_manager.add_urls_batch(urls)
    assert added_count == 3
    
    # Adding same URLs again should return 0
    added_count = await url_manager.add_urls_batch(urls)
    assert added_count == 0


@pytest.mark.asyncio
async def test_get_next_urls_to_crawl(url_manager):
    """Test getting URLs from crawl queue."""
    # Add some URLs
    await url_manager.add_url("https://www.finploy.com/test1", priority=10)
    await url_manager.add_url("https://www.finploy.com/test2", priority=20)
    await url_manager.add_url("https://www.finploy.com/test3", priority=5)
    
    # Get URLs (should be ordered by priority)
    urls = await url_manager.get_next_urls_to_crawl(2)
    assert len(urls) == 2
    assert "test2" in urls[0]  # Highest priority first


@pytest.mark.asyncio
async def test_mark_crawled(url_manager):
    """Test marking URLs as crawled."""
    url = "https://www.finploy.com/test"
    
    # Add URL
    await url_manager.add_url(url)
    
    # Mark as crawled
    await url_manager.mark_crawled(url, 200, "text/html")
    
    # URL should no longer be in queue
    queue_urls = await url_manager.get_next_urls_to_crawl(10)
    assert url not in queue_urls


@pytest.mark.asyncio
async def test_get_statistics(url_manager):
    """Test getting crawl statistics."""
    # Add and crawl some URLs
    await url_manager.add_url("https://www.finploy.com/test1")
    await url_manager.add_url("https://www.finploy.com/test2")
    
    await url_manager.mark_crawled("https://www.finploy.com/test1", 200)
    await url_manager.mark_crawled("https://www.finploy.com/test2", 404)
    
    stats = await url_manager.get_statistics()
    assert stats.total_urls_discovered == 2
    assert stats.total_urls_crawled == 2
    assert stats.successful_crawls == 1
    assert stats.failed_crawls == 1


@pytest.mark.asyncio
async def test_get_all_valid_urls(url_manager):
    """Test getting valid URLs for sitemap generation."""
    # Add and crawl URLs with different status codes
    await url_manager.add_url("https://www.finploy.com/valid1")
    await url_manager.add_url("https://www.finploy.com/valid2")
    await url_manager.add_url("https://www.finploy.com/invalid")
    
    await url_manager.mark_crawled("https://www.finploy.com/valid1", 200)
    await url_manager.mark_crawled("https://www.finploy.com/valid2", 301)
    await url_manager.mark_crawled("https://www.finploy.com/invalid", 404)
    
    valid_urls = await url_manager.get_all_valid_urls()
    assert len(valid_urls) == 2
    
    valid_url_strings = [record.url for record in valid_urls]
    assert "https://www.finploy.com/valid1" in valid_url_strings
    assert "https://www.finploy.com/valid2" in valid_url_strings
    assert "https://www.finploy.com/invalid" not in valid_url_strings


@pytest.mark.asyncio
async def test_queue_size(url_manager):
    """Test getting queue size."""
    assert await url_manager.get_queue_size() == 0
    
    await url_manager.add_url("https://www.finploy.com/test1")
    await url_manager.add_url("https://www.finploy.com/test2")
    
    assert await url_manager.get_queue_size() == 2
    
    await url_manager.mark_crawled("https://www.finploy.com/test1", 200)
    
    assert await url_manager.get_queue_size() == 1


@pytest.mark.asyncio
async def test_clear_processing_flags(url_manager):
    """Test clearing processing flags."""
    await url_manager.add_url("https://www.finploy.com/test")
    
    # Get URL (marks as processing)
    urls = await url_manager.get_next_urls_to_crawl(1)
    assert len(urls) == 1
    
    # Clear processing flags
    await url_manager.clear_processing_flags()
    
    # Should be able to get URL again
    urls = await url_manager.get_next_urls_to_crawl(1)
    assert len(urls) == 1


@pytest.mark.asyncio
async def test_reset_database(url_manager):
    """Test database reset functionality."""
    # Add some data
    await url_manager.add_url("https://www.finploy.com/test")
    
    stats_before = await url_manager.get_statistics()
    assert stats_before.total_urls_discovered > 0
    
    # Reset database
    await url_manager.reset_database()
    
    stats_after = await url_manager.get_statistics()
    assert stats_after.total_urls_discovered == 0


@pytest.mark.asyncio
async def test_export_urls_to_file(url_manager):
    """Test exporting URLs to file."""
    # Add and crawl some URLs
    await url_manager.add_url("https://www.finploy.com/test1", depth=1, is_dynamic=False)
    await url_manager.add_url("https://www.finploy.com/test2", depth=2, is_dynamic=True)
    
    await url_manager.mark_crawled("https://www.finploy.com/test1", 200)
    await url_manager.mark_crawled("https://www.finploy.com/test2", 404)
    
    # Export to temporary file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tmp:
        export_file = tmp.name
    
    try:
        await url_manager.export_urls_to_file(export_file)
        
        # Check file contents
        with open(export_file, 'r') as f:
            content = f.read()
            assert "https://www.finploy.com/test1" in content
            assert "https://www.finploy.com/test2" in content
            assert "success" in content
            assert "error" in content
    
    finally:
        os.unlink(export_file)
