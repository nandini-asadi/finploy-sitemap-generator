"""Utility functions for the sitemap generator."""

import asyncio
import logging
import re
from datetime import datetime
from typing import List, Optional, Set
from urllib.parse import urljoin, urlparse, urlunparse, parse_qs, urlencode
from urllib.robotparser import RobotFileParser

logger = logging.getLogger(__name__)


def normalize_url(url: str, base_url: Optional[str] = None) -> str:
    """
    Normalize URL by removing fragments, sorting query parameters,
    and converting to absolute URL if base_url is provided.
    """
    if base_url:
        url = urljoin(base_url, url)
    
    parsed = urlparse(url)
    
    # Remove fragment
    parsed = parsed._replace(fragment="")
    
    # Sort query parameters for consistency
    if parsed.query:
        query_params = parse_qs(parsed.query, keep_blank_values=True)
        sorted_params = sorted(query_params.items())
        normalized_query = urlencode(sorted_params, doseq=True)
        parsed = parsed._replace(query=normalized_query)
    
    # Remove trailing slash from path (except for root)
    path = parsed.path
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
        parsed = parsed._replace(path=path)
    
    return urlunparse(parsed)


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    parsed = urlparse(url)
    return parsed.netloc.lower()


def is_valid_url(url: str) -> bool:
    """Check if URL is valid and uses HTTP/HTTPS scheme."""
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def deduplicate_urls(urls: List[str]) -> List[str]:
    """Remove duplicate URLs while preserving order."""
    seen: Set[str] = set()
    result = []
    
    for url in urls:
        normalized = normalize_url(url)
        if normalized not in seen and is_valid_url(normalized):
            seen.add(normalized)
            result.append(normalized)
    
    return result


def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> None:
    """Set up logging configuration."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("playwright").setLevel(logging.WARNING)


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def format_number(number: int) -> str:
    """Format number with thousands separators."""
    return f"{number:,}"


class RateLimiter:
    """Simple rate limiter for controlling request frequency."""
    
    def __init__(self, delay: float):
        self.delay = delay
        self.last_request_time = 0.0
    
    async def wait(self) -> None:
        """Wait if necessary to respect rate limit."""
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.delay:
            wait_time = self.delay - time_since_last
            await asyncio.sleep(wait_time)
        
        self.last_request_time = asyncio.get_event_loop().time()


class RobotsChecker:
    """Check robots.txt compliance for URLs."""
    
    def __init__(self, user_agent: str = "*"):
        self.user_agent = user_agent
        self._robots_cache: dict[str, RobotFileParser] = {}
    
    async def can_fetch(self, url: str) -> bool:
        """Check if URL can be fetched according to robots.txt."""
        try:
            parsed = urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            robots_url = urljoin(base_url, "/robots.txt")
            
            if base_url not in self._robots_cache:
                rp = RobotFileParser()
                rp.set_url(robots_url)
                try:
                    rp.read()
                    self._robots_cache[base_url] = rp
                except Exception as e:
                    logger.debug(f"Could not read robots.txt for {base_url}: {e}")
                    # If we can't read robots.txt, assume we can fetch
                    return True
            
            rp = self._robots_cache[base_url]
            return rp.can_fetch(self.user_agent, url)
            
        except Exception as e:
            logger.debug(f"Error checking robots.txt for {url}: {e}")
            return True  # Default to allowing if check fails


def clean_text(text: str) -> str:
    """Clean and normalize text content."""
    if not text:
        return ""
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text.strip())
    
    # Remove control characters
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    
    return text


def get_current_timestamp() -> str:
    """Get current timestamp in ISO format for sitemaps."""
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00")


def parse_content_type(content_type: str) -> str:
    """Parse content type header to extract main type."""
    if not content_type:
        return "unknown"
    
    # Split on semicolon to remove charset and other parameters
    main_type = content_type.split(";")[0].strip().lower()
    return main_type


def is_html_content(content_type: str) -> bool:
    """Check if content type indicates HTML content."""
    main_type = parse_content_type(content_type)
    return main_type in ("text/html", "application/xhtml+xml")


def create_directory_if_not_exists(directory: str) -> None:
    """Create directory if it doesn't exist."""
    import os
    os.makedirs(directory, exist_ok=True)


def get_file_size_mb(file_path: str) -> float:
    """Get file size in megabytes."""
    import os
    try:
        size_bytes = os.path.getsize(file_path)
        return size_bytes / (1024 * 1024)
    except OSError:
        return 0.0


async def retry_async(
    func,
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,)
) -> any:
    """Retry an async function with exponential backoff."""
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return await func()
        except exceptions as e:
            last_exception = e
            if attempt == max_retries:
                break
            
            wait_time = delay * (backoff_factor ** attempt)
            logger.debug(f"Attempt {attempt + 1} failed, retrying in {wait_time:.1f}s: {e}")
            await asyncio.sleep(wait_time)
    
    raise last_exception
