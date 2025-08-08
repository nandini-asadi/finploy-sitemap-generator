"""Static crawler using aiohttp for fast HTTP requests and BeautifulSoup for parsing."""

import asyncio
import logging
import time
from typing import List, Optional, Set
from urllib.parse import urljoin, urlparse
import aiohttp
from bs4 import BeautifulSoup, SoupStrainer
from .types import CrawlResult
from .config import DEFAULT_HEADERS, is_target_domain, should_skip_url
from .utils import (
    normalize_url, 
    deduplicate_urls, 
    RateLimiter, 
    RobotsChecker,
    is_html_content,
    retry_async
)

logger = logging.getLogger(__name__)


class StaticCrawler:
    """Crawls static web pages using aiohttp and extracts links."""
    
    def __init__(
        self,
        session: aiohttp.ClientSession,
        rate_limiter: RateLimiter,
        robots_checker: Optional[RobotsChecker] = None,
        respect_robots: bool = True
    ):
        self.session = session
        self.rate_limiter = rate_limiter
        self.robots_checker = robots_checker
        self.respect_robots = respect_robots
        
        # Only parse link-containing tags for performance
        self.parse_only = SoupStrainer(["a", "link", "area", "base"])
    
    async def crawl_url(self, url: str, depth: int) -> CrawlResult:
        """
        Crawl a single URL and extract links.
        
        Args:
            url: URL to crawl
            depth: Current crawl depth
            
        Returns:
            CrawlResult with discovered URLs and metadata
        """
        start_time = time.time()
        
        try:
            # Check robots.txt if enabled
            if self.respect_robots and self.robots_checker:
                if not await self.robots_checker.can_fetch(url):
                    logger.debug(f"Robots.txt disallows crawling: {url}")
                    return CrawlResult(
                        url=url,
                        status_code=403,
                        discovered_urls=[],
                        error="Disallowed by robots.txt"
                    )
            
            # Apply rate limiting
            await self.rate_limiter.wait()
            
            # Make HTTP request with retry logic
            response_data = await retry_async(
                lambda: self._make_request(url),
                max_retries=3,
                delay=1.0,
                exceptions=(aiohttp.ClientError, asyncio.TimeoutError)
            )
            
            if response_data is None:
                return CrawlResult(
                    url=url,
                    status_code=0,
                    discovered_urls=[],
                    error="Failed to fetch after retries"
                )
            
            status_code, content_type, html_content = response_data
            response_time = time.time() - start_time
            
            # Extract links if content is HTML
            discovered_urls = []
            if is_html_content(content_type) and html_content:
                discovered_urls = self._extract_links(html_content, url)
            
            logger.debug(
                f"Crawled {url} -> {status_code} ({len(discovered_urls)} links, "
                f"{response_time:.2f}s)"
            )
            
            return CrawlResult(
                url=url,
                status_code=status_code,
                discovered_urls=discovered_urls,
                content_type=content_type,
                response_time=response_time
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            logger.error(f"Error crawling {url}: {e}")
            return CrawlResult(
                url=url,
                status_code=0,
                discovered_urls=[],
                error=str(e),
                response_time=response_time
            )
    
    async def _make_request(self, url: str) -> Optional[tuple]:
        """Make HTTP request and return response data."""
        try:
            async with self.session.get(
                url,
                headers=DEFAULT_HEADERS,
                allow_redirects=True,
                max_redirects=5
            ) as response:
                content_type = response.headers.get('content-type', '')
                
                # Only read content if it's HTML
                if is_html_content(content_type):
                    # Limit content size to prevent memory issues
                    content = await response.text(encoding='utf-8', errors='ignore')
                    # Truncate very large pages
                    if len(content) > 1_000_000:  # 1MB limit
                        content = content[:1_000_000]
                        logger.warning(f"Truncated large page: {url}")
                else:
                    content = ""
                
                return response.status, content_type, content
                
        except aiohttp.ClientError as e:
            logger.debug(f"HTTP error for {url}: {e}")
            raise
        except asyncio.TimeoutError:
            logger.debug(f"Timeout for {url}")
            raise
        except Exception as e:
            logger.debug(f"Unexpected error for {url}: {e}")
            raise
    
    def _extract_links(self, html_content: str, base_url: str) -> List[str]:
        """Extract and normalize links from HTML content."""
        try:
            # Parse HTML with BeautifulSoup (only link-containing tags)
            soup = BeautifulSoup(html_content, 'lxml', parse_only=self.parse_only)
            
            discovered_urls: Set[str] = set()
            
            # Extract links from various elements
            self._extract_anchor_links(soup, base_url, discovered_urls)
            self._extract_link_elements(soup, base_url, discovered_urls)
            self._extract_area_links(soup, base_url, discovered_urls)
            
            # Filter and normalize URLs
            valid_urls = []
            for url in discovered_urls:
                normalized_url = normalize_url(url, base_url)
                
                # Skip if not target domain
                if not is_target_domain(normalized_url):
                    continue
                
                # Skip if matches skip patterns
                if should_skip_url(normalized_url):
                    continue
                
                # Skip if same as base URL
                if normalized_url == normalize_url(base_url):
                    continue
                
                valid_urls.append(normalized_url)
            
            return deduplicate_urls(valid_urls)
            
        except Exception as e:
            logger.error(f"Error extracting links from {base_url}: {e}")
            return []
    
    def _extract_anchor_links(self, soup: BeautifulSoup, base_url: str, urls: Set[str]) -> None:
        """Extract links from <a> tags."""
        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()
            if href and not href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                absolute_url = urljoin(base_url, href)
                urls.add(absolute_url)
    
    def _extract_link_elements(self, soup: BeautifulSoup, base_url: str, urls: Set[str]) -> None:
        """Extract links from <link> tags (canonical, alternate, etc.)."""
        for link in soup.find_all('link', href=True):
            rel = link.get('rel', [])
            if isinstance(rel, str):
                rel = [rel]
            
            # Only include certain link types
            if any(r in ['canonical', 'alternate', 'next', 'prev'] for r in rel):
                href = link.get('href', '').strip()
                if href:
                    absolute_url = urljoin(base_url, href)
                    urls.add(absolute_url)
    
    def _extract_area_links(self, soup: BeautifulSoup, base_url: str, urls: Set[str]) -> None:
        """Extract links from <area> tags in image maps."""
        for area in soup.find_all('area', href=True):
            href = area.get('href', '').strip()
            if href and not href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                absolute_url = urljoin(base_url, href)
                urls.add(absolute_url)
    
    def _extract_form_actions(self, soup: BeautifulSoup, base_url: str, urls: Set[str]) -> None:
        """Extract URLs from form actions (for job search forms)."""
        for form in soup.find_all('form', action=True):
            action = form.get('action', '').strip()
            if action and not action.startswith(('#', 'javascript:')):
                # Only include GET forms that might generate job listing URLs
                method = form.get('method', 'get').lower()
                if method == 'get':
                    absolute_url = urljoin(base_url, action)
                    urls.add(absolute_url)
    
    async def crawl_batch(self, urls: List[str], depth: int) -> List[CrawlResult]:
        """
        Crawl multiple URLs concurrently.
        
        Args:
            urls: List of URLs to crawl
            depth: Current crawl depth
            
        Returns:
            List of CrawlResult objects
        """
        if not urls:
            return []
        
        logger.info(f"Crawling batch of {len(urls)} URLs at depth {depth}")
        
        # Create tasks for concurrent crawling
        tasks = [self.crawl_url(url, depth) for url in urls]
        
        # Execute with progress tracking
        results = []
        completed = 0
        
        for coro in asyncio.as_completed(tasks):
            try:
                result = await coro
                results.append(result)
                completed += 1
                
                if completed % 10 == 0 or completed == len(tasks):
                    logger.info(f"Completed {completed}/{len(tasks)} URLs in batch")
                    
            except Exception as e:
                logger.error(f"Error in batch crawling: {e}")
                # Create error result for failed task
                results.append(CrawlResult(
                    url="unknown",
                    status_code=0,
                    discovered_urls=[],
                    error=str(e)
                ))
        
        return results
    
    def get_link_density(self, html_content: str) -> float:
        """Calculate link density (links per KB of content) for analysis."""
        try:
            soup = BeautifulSoup(html_content, 'lxml', parse_only=self.parse_only)
            link_count = len(soup.find_all('a', href=True))
            content_size_kb = len(html_content) / 1024
            return link_count / max(content_size_kb, 1)
        except Exception:
            return 0.0
    
    def extract_page_metadata(self, html_content: str) -> dict:
        """Extract useful metadata from HTML page."""
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            
            metadata = {
                'title': '',
                'description': '',
                'canonical': '',
                'language': '',
                'last_modified': ''
            }
            
            # Title
            title_tag = soup.find('title')
            if title_tag:
                metadata['title'] = title_tag.get_text(strip=True)
            
            # Meta description
            desc_tag = soup.find('meta', attrs={'name': 'description'})
            if desc_tag:
                metadata['description'] = desc_tag.get('content', '')
            
            # Canonical URL
            canonical_tag = soup.find('link', attrs={'rel': 'canonical'})
            if canonical_tag:
                metadata['canonical'] = canonical_tag.get('href', '')
            
            # Language
            html_tag = soup.find('html')
            if html_tag:
                metadata['language'] = html_tag.get('lang', '')
            
            # Last modified (from meta tag)
            modified_tag = soup.find('meta', attrs={'name': 'last-modified'})
            if modified_tag:
                metadata['last_modified'] = modified_tag.get('content', '')
            
            return metadata
            
        except Exception as e:
            logger.debug(f"Error extracting metadata: {e}")
            return {}


async def create_crawler_session(
    timeout: int = 30,
    max_connections: int = 100,
    user_agent: str = DEFAULT_HEADERS.get('User-Agent', '')
) -> aiohttp.ClientSession:
    """Create optimized aiohttp session for crawling."""
    
    # Configure timeouts
    timeout_config = aiohttp.ClientTimeout(
        total=timeout,
        connect=10,
        sock_read=timeout
    )
    
    # Configure connector for connection pooling
    connector = aiohttp.TCPConnector(
        limit=max_connections,
        limit_per_host=20,
        ttl_dns_cache=300,
        use_dns_cache=True,
        keepalive_timeout=30,
        enable_cleanup_closed=True
    )
    
    # Custom headers
    headers = DEFAULT_HEADERS.copy()
    if user_agent:
        headers['User-Agent'] = user_agent
    
    session = aiohttp.ClientSession(
        connector=connector,
        timeout=timeout_config,
        headers=headers,
        raise_for_status=False  # Handle status codes manually
    )
    
    return session
