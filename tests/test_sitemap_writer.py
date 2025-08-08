"""Tests for sitemap writer functionality."""

import os
import tempfile
from datetime import datetime
from lxml import etree
import pytest
from src.sitemap_generator.sitemap_writer import SitemapWriter
from src.sitemap_generator.types import URLRecord, ChangeFrequency


@pytest.fixture
def sample_urls():
    """Create sample URL records for testing."""
    now = datetime.utcnow()
    
    return [
        URLRecord(
            url="https://www.finploy.com",
            discovered_at=now,
            last_crawled=now,
            status_code=200,
            content_type="text/html",
            depth=0
        ),
        URLRecord(
            url="https://www.finploy.com/jobs",
            discovered_at=now,
            last_crawled=now,
            status_code=200,
            content_type="text/html",
            depth=1
        ),
        URLRecord(
            url="https://www.finploy.com/jobs/123",
            discovered_at=now,
            last_crawled=now,
            status_code=200,
            content_type="text/html",
            depth=2
        ),
    ]


@pytest.fixture
def sitemap_writer():
    """Create sitemap writer with temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield SitemapWriter(tmpdir, max_urls_per_sitemap=2)


def test_create_sitemap_entry(sitemap_writer, sample_urls):
    """Test creating sitemap entries from URL records."""
    url_record = sample_urls[0]  # Homepage
    entry = sitemap_writer._create_sitemap_entry(url_record)
    
    assert entry.loc == url_record.url
    assert entry.lastmod is not None
    assert entry.priority == 1.0  # Homepage should have highest priority
    assert entry.changefreq == ChangeFrequency.DAILY


def test_single_sitemap_generation(sitemap_writer, sample_urls):
    """Test generating a single sitemap file."""
    # Use only 2 URLs to stay within limit
    urls = sample_urls[:2]
    
    sitemap_files = sitemap_writer.generate_sitemaps(urls)
    
    assert len(sitemap_files) == 1
    assert os.path.exists(sitemap_files[0])
    assert sitemap_files[0].endswith('sitemap.xml')


def test_multiple_sitemap_generation(sitemap_writer, sample_urls):
    """Test generating multiple sitemap files when URL limit is exceeded."""
    # Add more URLs to exceed the limit (set to 2 in fixture)
    extended_urls = sample_urls * 2  # 6 URLs total, limit is 2
    
    sitemap_files = sitemap_writer.generate_sitemaps(extended_urls)
    
    # Should create multiple files
    assert len(sitemap_files) > 1
    
    # Should create sitemap index
    index_file = os.path.join(sitemap_writer.output_dir, "sitemap_index.xml")
    assert os.path.exists(index_file)


def test_sitemap_xml_structure(sitemap_writer, sample_urls):
    """Test the structure of generated XML sitemap."""
    sitemap_files = sitemap_writer.generate_sitemaps(sample_urls[:1])
    sitemap_file = sitemap_files[0]
    
    # Parse XML
    tree = etree.parse(sitemap_file)
    root = tree.getroot()
    
    # Check namespace
    assert root.tag == "{http://www.sitemaps.org/schemas/sitemap/0.9}urlset"
    
    # Check URL elements
    urls = root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}url")
    assert len(urls) == 1
    
    url_elem = urls[0]
    
    # Check required elements
    loc = url_elem.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
    assert loc is not None
    assert loc.text == sample_urls[0].url
    
    # Check optional elements
    lastmod = url_elem.find("{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod")
    assert lastmod is not None
    
    changefreq = url_elem.find("{http://www.sitemaps.org/schemas/sitemap/0.9}changefreq")
    assert changefreq is not None
    
    priority = url_elem.find("{http://www.sitemaps.org/schemas/sitemap/0.9}priority")
    assert priority is not None


def test_sitemap_validation(sitemap_writer, sample_urls):
    """Test sitemap validation functionality."""
    sitemap_files = sitemap_writer.generate_sitemaps(sample_urls[:1])
    sitemap_file = sitemap_files[0]
    
    # Validate the generated sitemap
    is_valid = sitemap_writer.validate_sitemap(sitemap_file)
    assert is_valid is True


def test_sitemap_stats(sitemap_writer, sample_urls):
    """Test getting sitemap statistics."""
    sitemap_files = sitemap_writer.generate_sitemaps(sample_urls)
    sitemap_file = sitemap_files[0]
    
    stats = sitemap_writer.get_sitemap_stats(sitemap_file)
    
    assert 'total_urls' in stats
    assert 'file_size_mb' in stats
    assert 'has_lastmod' in stats
    assert 'has_changefreq' in stats
    assert 'has_priority' in stats
    assert stats['total_urls'] > 0


def test_robots_txt_generation(sitemap_writer, sample_urls):
    """Test robots.txt generation."""
    sitemap_files = sitemap_writer.generate_sitemaps(sample_urls[:1])
    
    robots_file = sitemap_writer.generate_robots_txt(
        "https://www.finploy.com",
        sitemap_files
    )
    
    assert os.path.exists(robots_file)
    
    # Check content
    with open(robots_file, 'r') as f:
        content = f.read()
        assert "User-agent: *" in content
        assert "Allow: /" in content
        assert "Sitemap:" in content


def test_sitemap_index_generation(sitemap_writer):
    """Test sitemap index generation."""
    # Create multiple sitemap files
    sample_files = [
        os.path.join(sitemap_writer.output_dir, "sitemap_001.xml"),
        os.path.join(sitemap_writer.output_dir, "sitemap_002.xml"),
    ]
    
    # Create dummy files
    for file_path in sample_files:
        with open(file_path, 'w') as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?><urlset></urlset>')
    
    # Generate index
    index_file = sitemap_writer._generate_sitemap_index(
        sample_files,
        "https://www.finploy.com"
    )
    
    assert os.path.exists(index_file)
    
    # Parse and validate index
    tree = etree.parse(index_file)
    root = tree.getroot()
    
    assert root.tag == "{http://www.sitemaps.org/schemas/sitemap/0.9}sitemapindex"
    
    sitemaps = root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap")
    assert len(sitemaps) == 2


def test_empty_url_list(sitemap_writer):
    """Test handling of empty URL list."""
    sitemap_files = sitemap_writer.generate_sitemaps([])
    assert len(sitemap_files) == 0


def test_url_priority_calculation():
    """Test URL priority calculation."""
    from src.sitemap_generator.config import get_url_priority
    
    # Test different URL types
    assert get_url_priority("https://www.finploy.com") == 1.0  # Homepage
    assert get_url_priority("https://www.finploy.com/jobs") == 0.8  # Job listing
    assert get_url_priority("https://www.finploy.com/jobs/123") == 0.6  # Individual job
    assert get_url_priority("https://www.finploy.com/jobs-in-london") == 0.7  # Location page
    assert get_url_priority("https://www.finploy.com/company/abc") == 0.7  # Company page
    assert get_url_priority("https://www.finploy.com/about") == 0.5  # Default


def test_change_frequency_calculation():
    """Test change frequency calculation."""
    from src.sitemap_generator.config import get_url_changefreq
    
    # Test different URL types
    assert get_url_changefreq("https://www.finploy.com") == ChangeFrequency.DAILY
    assert get_url_changefreq("https://www.finploy.com/jobs") == ChangeFrequency.DAILY
    assert get_url_changefreq("https://www.finploy.com/jobs/123") == ChangeFrequency.DAILY
    assert get_url_changefreq("https://www.finploy.com/jobs-in-london") == ChangeFrequency.WEEKLY
    assert get_url_changefreq("https://www.finploy.com/about") == ChangeFrequency.WEEKLY


def test_sitemap_compression(sitemap_writer, sample_urls):
    """Test sitemap compression functionality."""
    sitemap_files = sitemap_writer.generate_sitemaps(sample_urls[:1])
    
    compressed_files = sitemap_writer.compress_sitemaps(sitemap_files)
    
    assert len(compressed_files) == len(sitemap_files)
    
    for compressed_file in compressed_files:
        assert os.path.exists(compressed_file)
        assert compressed_file.endswith('.gz')
        
        # Compressed file should be smaller
        original_size = os.path.getsize(compressed_file.replace('.gz', ''))
        compressed_size = os.path.getsize(compressed_file)
        assert compressed_size < original_size


def test_cleanup_old_sitemaps(sitemap_writer):
    """Test cleanup of old sitemap files."""
    # Create some old sitemap files
    old_files = [
        os.path.join(sitemap_writer.output_dir, "sitemap_old.xml"),
        os.path.join(sitemap_writer.output_dir, "sitemap_index_old.xml"),
        os.path.join(sitemap_writer.output_dir, "other_file.txt"),  # Should not be removed
    ]
    
    for file_path in old_files:
        with open(file_path, 'w') as f:
            f.write("test content")
    
    # Cleanup
    sitemap_writer.cleanup_old_sitemaps()
    
    # Check that sitemap files were removed but other files remain
    assert not os.path.exists(old_files[0])
    assert not os.path.exists(old_files[1])
    assert os.path.exists(old_files[2])  # Non-sitemap file should remain


def test_large_sitemap_handling(sitemap_writer):
    """Test handling of large numbers of URLs."""
    # Create many URL records
    large_url_list = []
    base_time = datetime.utcnow()
    
    for i in range(100):
        url_record = URLRecord(
            url=f"https://www.finploy.com/page{i}",
            discovered_at=base_time,
            last_crawled=base_time,
            status_code=200,
            content_type="text/html",
            depth=1
        )
        large_url_list.append(url_record)
    
    # Generate sitemaps (should split into multiple files)
    sitemap_files = sitemap_writer.generate_sitemaps(large_url_list)
    
    # Should create multiple files due to max_urls_per_sitemap=2 in fixture
    assert len(sitemap_files) > 1
    
    # Validate all files
    for sitemap_file in sitemap_files:
        assert sitemap_writer.validate_sitemap(sitemap_file)
        stats = sitemap_writer.get_sitemap_stats(sitemap_file)
        assert stats['total_urls'] <= sitemap_writer.max_urls_per_sitemap
