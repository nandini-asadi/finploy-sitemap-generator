"""
Finploy Sitemap Generator

A production-ready sitemap generator for Finploy websites that handles both
static and dynamic content to create comprehensive XML sitemaps.

Key Features:
- Crawls static pages with aiohttp for performance
- Handles dynamic content with Playwright for JavaScript-heavy pages
- Discovers URLs behind "View More" buttons and pagination
- Generates sitemaps.org compliant XML files
- Supports multiple base URLs and configurable crawl depth
- Includes rate limiting and robots.txt compliance
- SQLite database for URL management and deduplication
"""

__version__ = "1.0.0"
__author__ = "Finploy Team"
__email__ = "tech@finploy.com"

from .types import CrawlConfig, CrawlResult, URLRecord, CrawlStatistics
from .crawler import SitemapCrawler, run_crawler
from .config import get_config_from_env
from .main import main

__all__ = [
    "CrawlConfig",
    "CrawlResult", 
    "URLRecord",
    "CrawlStatistics",
    "SitemapCrawler",
    "run_crawler",
    "get_config_from_env",
    "main"
]
