"""Type definitions for the sitemap generator."""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from enum import Enum


class CrawlStatus(Enum):
    """Status of URL crawling."""
    PENDING = "pending"
    CRAWLING = "crawling"
    SUCCESS = "success"
    ERROR = "error"
    SKIPPED = "skipped"


class ChangeFrequency(Enum):
    """Sitemap change frequency values."""
    ALWAYS = "always"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    NEVER = "never"


@dataclass
class URLRecord:
    """Represents a URL record in the database."""
    url: str
    discovered_at: datetime
    last_crawled: Optional[datetime] = None
    status_code: Optional[int] = None
    content_type: Optional[str] = None
    is_dynamic: bool = False
    depth: int = 0
    parent_url: Optional[str] = None
    crawl_status: CrawlStatus = CrawlStatus.PENDING
    error_message: Optional[str] = None


@dataclass
class CrawlResult:
    """Result of crawling a single URL."""
    url: str
    status_code: int
    discovered_urls: List[str]
    is_dynamic_content: bool = False
    error: Optional[str] = None
    content_type: Optional[str] = None
    response_time: float = 0.0


@dataclass
class SitemapEntry:
    """Entry in a sitemap XML file."""
    loc: str
    lastmod: Optional[str] = None
    changefreq: Optional[ChangeFrequency] = None
    priority: Optional[float] = None


@dataclass
class CrawlConfig:
    """Configuration for the crawler."""
    base_urls: List[str]
    max_depth: int = 5
    max_concurrent_requests: int = 10
    crawl_delay: float = 1.0
    request_timeout: int = 30
    max_urls_per_sitemap: int = 50000
    database_path: str = "data/urls.db"
    sitemap_output_dir: str = "data/sitemap/"
    user_agent: str = "Finploy-Sitemap-Generator/1.0"
    respect_robots_txt: bool = True
    enable_dynamic_crawling: bool = True


@dataclass
class CrawlStatistics:
    """Statistics about the crawling process."""
    total_urls_discovered: int = 0
    total_urls_crawled: int = 0
    successful_crawls: int = 0
    failed_crawls: int = 0
    skipped_urls: int = 0
    dynamic_pages_crawled: int = 0
    static_pages_crawled: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    @property
    def duration_seconds(self) -> float:
        """Calculate crawling duration in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_urls_crawled == 0:
            return 0.0
        return (self.successful_crawls / self.total_urls_crawled) * 100
