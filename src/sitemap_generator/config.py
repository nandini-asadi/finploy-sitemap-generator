"""Configuration and constants for the sitemap generator."""

import os
from typing import List, Pattern
import re
from .types import CrawlConfig, ChangeFrequency

# Base URLs to crawl
DEFAULT_BASE_URLS = [
    "https://www.finploy.com",
    "https://finploy.co.uk"
]

# Crawling configuration
DEFAULT_MAX_DEPTH = 5
DEFAULT_MAX_CONCURRENT_REQUESTS = 10
DEFAULT_CRAWL_DELAY = 1.0  # seconds
DEFAULT_REQUEST_TIMEOUT = 30  # seconds
DEFAULT_MAX_URLS_PER_SITEMAP = 50000  # sitemaps.org limit

# File paths
DEFAULT_DATABASE_PATH = "data/urls.db"
DEFAULT_SITEMAP_OUTPUT_DIR = "data/sitemap/"

# HTTP configuration
DEFAULT_USER_AGENT = "Finploy-Sitemap-Generator/1.0 (+https://www.finploy.com)"
DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# URL patterns that typically contain dynamic content
DYNAMIC_URL_PATTERNS: List[Pattern[str]] = [
    re.compile(r"/jobs", re.IGNORECASE),
    re.compile(r"/search", re.IGNORECASE),
    re.compile(r"/filter", re.IGNORECASE),
    re.compile(r"/category", re.IGNORECASE),
    re.compile(r"/location", re.IGNORECASE),
    re.compile(r"jobs-in-", re.IGNORECASE),
    re.compile(r"-jobs-in-", re.IGNORECASE),
]

# URL patterns to skip
SKIP_URL_PATTERNS: List[Pattern[str]] = [
    re.compile(r"\.(pdf|doc|docx|xls|xlsx|ppt|pptx|zip|rar|tar|gz)$", re.IGNORECASE),
    re.compile(r"\.(jpg|jpeg|png|gif|bmp|svg|ico|webp)$", re.IGNORECASE),
    re.compile(r"\.(css|js|json|xml|txt)$", re.IGNORECASE),
    re.compile(r"mailto:", re.IGNORECASE),
    re.compile(r"tel:", re.IGNORECASE),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"#", re.IGNORECASE),  # Fragment-only URLs
]

# Priority mapping for different URL types
URL_PRIORITY_MAP = {
    "homepage": 1.0,
    "main_category": 0.9,
    "job_listing": 0.8,
    "location_page": 0.7,
    "individual_job": 0.6,
    "company_page": 0.7,
    "blog_post": 0.5,
    "static_page": 0.5,
    "default": 0.5,
}

# Change frequency mapping for different URL types
URL_CHANGEFREQ_MAP = {
    "homepage": ChangeFrequency.DAILY,
    "main_category": ChangeFrequency.DAILY,
    "job_listing": ChangeFrequency.DAILY,
    "location_page": ChangeFrequency.WEEKLY,
    "individual_job": ChangeFrequency.DAILY,
    "company_page": ChangeFrequency.WEEKLY,
    "blog_post": ChangeFrequency.MONTHLY,
    "static_page": ChangeFrequency.MONTHLY,
    "default": ChangeFrequency.WEEKLY,
}

# Selectors for dynamic content
DYNAMIC_CONTENT_SELECTORS = {
    "view_more_buttons": [
        "button:contains('View More')",
        "a:contains('View More')",
        "button:contains('Load More')",
        "a:contains('Load More')",
        ".load-more",
        ".view-more",
        "[data-action='load-more']",
    ],
    "pagination": [
        ".pagination a",
        ".pager a",
        "a[rel='next']",
        ".next-page",
        "[data-page]",
    ],
    "job_filters": [
        ".job-filter select",
        ".location-filter select",
        ".category-filter select",
        "form[action*='job']",
    ],
}

# Playwright configuration
PLAYWRIGHT_CONFIG = {
    "headless": True,
    "timeout": 30000,  # 30 seconds
    "wait_for_load_state": "networkidle",
    "viewport": {"width": 1920, "height": 1080},
    "user_agent": DEFAULT_USER_AGENT,
}


def get_config_from_env() -> CrawlConfig:
    """Create configuration from environment variables with defaults."""
    base_urls_str = os.getenv("FINPLOY_BASE_URLS", ",".join(DEFAULT_BASE_URLS))
    base_urls = [url.strip() for url in base_urls_str.split(",") if url.strip()]
    
    return CrawlConfig(
        base_urls=base_urls,
        max_depth=int(os.getenv("FINPLOY_MAX_DEPTH", DEFAULT_MAX_DEPTH)),
        max_concurrent_requests=int(
            os.getenv("FINPLOY_MAX_CONCURRENT", DEFAULT_MAX_CONCURRENT_REQUESTS)
        ),
        crawl_delay=float(os.getenv("FINPLOY_CRAWL_DELAY", DEFAULT_CRAWL_DELAY)),
        request_timeout=int(os.getenv("FINPLOY_TIMEOUT", DEFAULT_REQUEST_TIMEOUT)),
        max_urls_per_sitemap=int(
            os.getenv("FINPLOY_MAX_URLS_PER_SITEMAP", DEFAULT_MAX_URLS_PER_SITEMAP)
        ),
        database_path=os.getenv("FINPLOY_DATABASE_PATH", DEFAULT_DATABASE_PATH),
        sitemap_output_dir=os.getenv(
            "FINPLOY_SITEMAP_DIR", DEFAULT_SITEMAP_OUTPUT_DIR
        ),
        user_agent=os.getenv("FINPLOY_USER_AGENT", DEFAULT_USER_AGENT),
        respect_robots_txt=os.getenv("FINPLOY_RESPECT_ROBOTS", "true").lower() == "true",
        enable_dynamic_crawling=os.getenv("FINPLOY_ENABLE_DYNAMIC", "true").lower() == "true",
    )


def classify_url_type(url: str) -> str:
    """Classify URL type for priority and change frequency assignment."""
    url_lower = url.lower()
    
    # Homepage
    if url_lower.rstrip("/") in [base.rstrip("/") for base in DEFAULT_BASE_URLS]:
        return "homepage"
    
    # Job-related pages
    if "/jobs" in url_lower:
        if re.search(r"/jobs/\d+", url_lower):  # Individual job
            return "individual_job"
        elif "jobs-in-" in url_lower or "-jobs-in-" in url_lower:
            return "location_page"
        else:
            return "job_listing"
    
    # Company pages
    if "/company" in url_lower or "/companies" in url_lower:
        return "company_page"
    
    # Blog posts
    if "/blog" in url_lower or "/news" in url_lower or "/article" in url_lower:
        return "blog_post"
    
    # Main category pages
    if any(cat in url_lower for cat in ["/category", "/sector", "/industry"]):
        return "main_category"
    
    return "default"


def get_url_priority(url: str) -> float:
    """Get priority for URL based on its type."""
    url_type = classify_url_type(url)
    return URL_PRIORITY_MAP.get(url_type, URL_PRIORITY_MAP["default"])


def get_url_changefreq(url: str) -> ChangeFrequency:
    """Get change frequency for URL based on its type."""
    url_type = classify_url_type(url)
    return URL_CHANGEFREQ_MAP.get(url_type, URL_CHANGEFREQ_MAP["default"])


def should_skip_url(url: str) -> bool:
    """Check if URL should be skipped based on patterns."""
    return any(pattern.search(url) for pattern in SKIP_URL_PATTERNS)


def is_dynamic_url(url: str) -> bool:
    """Check if URL likely contains dynamic content."""
    return any(pattern.search(url) for pattern in DYNAMIC_URL_PATTERNS)


def is_target_domain(url: str) -> bool:
    """Check if URL belongs to target domains."""
    from urllib.parse import urlparse
    
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    
    target_domains = ["finploy.com", "www.finploy.com", "finploy.co.uk", "www.finploy.co.uk"]
    return domain in target_domains
