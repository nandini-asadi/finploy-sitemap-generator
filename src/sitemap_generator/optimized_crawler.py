"""
High-performance optimized crawler for Finploy sitemap generation.
Targets 5-7 minute execution time for ~1900 URLs.
"""

import asyncio
import logging
import time
import json
from datetime import datetime
from typing import List, Set, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse, parse_qs, urlencode
from dataclasses import dataclass
import aiohttp
from bs4 import BeautifulSoup, SoupStrainer
from playwright.async_api import async_playwright, Browser, Page
import re

logger = logging.getLogger(__name__)

@dataclass
class CrawlResult:
    url: str
    status_code: int
    discovered_urls: List[str]
    content_type: str = ""
    error: Optional[str] = None
    response_time: float = 0.0
    is_dynamic: bool = False

@dataclass
class OptimizedConfig:
    base_urls: List[str]
    max_depth: int = 4
    max_concurrent_static: int = 50  # High concurrency for static
    max_concurrent_dynamic: int = 8   # Limited for dynamic
    static_timeout: int = 5          # Fast timeout for static
    dynamic_timeout: int = 10        # Reasonable timeout for dynamic
    crawl_delay: float = 0.1         # Minimal delay
    max_urls_per_sitemap: int = 50000
    output_dir: str = "data/sitemap/"

class HighPerformanceCrawler:
    """Optimized crawler designed for speed and completeness."""
    
    def __init__(self, config: OptimizedConfig):
        self.config = config
        self.discovered_urls: Set[str] = set()
        self.crawled_urls: Set[str] = set()
        self.failed_urls: Set[str] = set()
        self.url_queue: asyncio.Queue = asyncio.Queue()
        self.results: List[CrawlResult] = []
        
        # Performance tracking
        self.start_time = time.time()
        self.static_session: Optional[aiohttp.ClientSession] = None
        self.browser: Optional[Browser] = None
        self.playwright = None
        
        # URL classification patterns
        self.dynamic_patterns = [
            r'/jobs-in-',
            r'/search',
            r'/filter',
            r'/jobs\?',
            r'/category',
            r'/location'
        ]
        
        # Skip patterns
        self.skip_patterns = [
            r'\.(pdf|doc|docx|xls|xlsx|ppt|pptx|zip|rar|tar|gz)$',
            r'\.(jpg|jpeg|png|gif|bmp|svg|ico|webp|css|js)$',
            r'mailto:|tel:|javascript:|#$'
        ]
    
    async def initialize(self):
        """Initialize crawler components."""
        logger.info("Initializing high-performance crawler...")
        
        # Initialize HTTP session with optimized settings
        connector = aiohttp.TCPConnector(
            limit=self.config.max_concurrent_static * 2,
            limit_per_host=30,
            ttl_dns_cache=300,
            use_dns_cache=True,
            keepalive_timeout=30
        )
        
        timeout = aiohttp.ClientTimeout(
            total=self.config.static_timeout,
            connect=3,
            sock_read=self.config.static_timeout
        )
        
        self.static_session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                'User-Agent': 'Finploy-Sitemap-Generator/2.0 (High-Performance)',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive'
            }
        )
        
        # Initialize Playwright for dynamic content (lazy loading)
        logger.info("Crawler initialization completed")
    
    async def _init_playwright(self):
        """Initialize Playwright only when needed."""
        if not self.browser:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-web-security',
                    '--disable-images',  # Skip images for speed
                    '--disable-javascript-harmony-shipping',
                    '--disable-extensions',
                    '--disable-plugins',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding',
                    '--disable-features=TranslateUI,BlinkGenPropertyTrees'
                ]
            )
    
    def is_target_domain(self, url: str) -> bool:
        """Check if URL belongs to target domains."""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        return domain in ['finploy.com', 'www.finploy.com', 'finploy.co.uk', 'www.finploy.co.uk']
    
    def should_skip_url(self, url: str) -> bool:
        """Check if URL should be skipped."""
        return any(re.search(pattern, url, re.IGNORECASE) for pattern in self.skip_patterns)
    
    def is_dynamic_url(self, url: str) -> bool:
        """Determine if URL requires dynamic crawling."""
        return any(re.search(pattern, url, re.IGNORECASE) for pattern in self.dynamic_patterns)
    
    def normalize_url(self, url: str, base_url: str = "") -> str:
        """Normalize URL for deduplication."""
        if base_url:
            url = urljoin(base_url, url)
        
        parsed = urlparse(url)
        
        # Remove fragment
        url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        
        # Add query if present (important for job searches)
        if parsed.query:
            url += f"?{parsed.query}"
        
        # Remove trailing slash except for root
        if url.endswith('/') and len(parsed.path) > 1:
            url = url.rstrip('/')
        
        return url
    
    async def crawl_static_url(self, url: str) -> CrawlResult:
        """Fast static URL crawling."""
        start_time = time.time()
        
        try:
            async with self.static_session.get(url) as response:
                content_type = response.headers.get('content-type', '')
                
                if 'text/html' not in content_type:
                    return CrawlResult(
                        url=url,
                        status_code=response.status,
                        discovered_urls=[],
                        content_type=content_type,
                        response_time=time.time() - start_time
                    )
                
                html = await response.text()
                discovered_urls = self.extract_links_fast(html, url)
                
                return CrawlResult(
                    url=url,
                    status_code=response.status,
                    discovered_urls=discovered_urls,
                    content_type=content_type,
                    response_time=time.time() - start_time
                )
                
        except Exception as e:
            return CrawlResult(
                url=url,
                status_code=0,
                discovered_urls=[],
                error=str(e),
                response_time=time.time() - start_time
            )
    
    def extract_links_fast(self, html: str, base_url: str) -> List[str]:
        """Fast link extraction using optimized BeautifulSoup."""
        try:
            # Only parse link-containing elements for speed
            parse_only = SoupStrainer(["a", "link", "area", "form"])
            soup = BeautifulSoup(html, 'lxml', parse_only=parse_only)
            
            urls = set()
            
            # Extract anchor links
            for link in soup.find_all('a', href=True):
                href = link.get('href', '').strip()
                if href and not href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                    urls.add(self.normalize_url(href, base_url))
            
            # Extract canonical and alternate links
            for link in soup.find_all('link', href=True):
                rel = link.get('rel', [])
                if isinstance(rel, str):
                    rel = [rel]
                if any(r in ['canonical', 'alternate'] for r in rel):
                    href = link.get('href', '').strip()
                    if href:
                        urls.add(self.normalize_url(href, base_url))
            
            # Extract form actions (for job search forms)
            for form in soup.find_all('form', action=True):
                action = form.get('action', '').strip()
                method = form.get('method', 'get').lower()
                if action and method == 'get':
                    urls.add(self.normalize_url(action, base_url))
            
            # Generate job location URLs (Finploy-specific optimization)
            self._generate_job_location_urls(soup, base_url, urls)
            
            # Filter valid URLs
            valid_urls = []
            for url in urls:
                if (self.is_target_domain(url) and 
                    not self.should_skip_url(url) and 
                    url != base_url):
                    valid_urls.append(url)
            
            return valid_urls
            
        except Exception as e:
            logger.debug(f"Error extracting links from {base_url}: {e}")
            return []
    
    def _generate_job_location_urls(self, soup: BeautifulSoup, base_url: str, urls: set):
        """Generate job location URLs from dropdowns and forms."""
        try:
            # Look for location options in select elements
            for select in soup.find_all('select'):
                name = select.get('name', '').lower()
                if any(keyword in name for keyword in ['location', 'city', 'area', 'region']):
                    for option in select.find_all('option', value=True):
                        value = option.get('value', '').strip()
                        if value and value not in ['', '0', 'all']:
                            # Generate common job URL patterns
                            if '-' in value:
                                urls.add(self.normalize_url(f"/jobs-in-{value}", base_url))
                                urls.add(self.normalize_url(f"/{value}-jobs", base_url))
            
            # Look for data attributes that might contain location info
            for element in soup.find_all(attrs={"data-location": True}):
                location = element.get('data-location', '').strip()
                if location:
                    urls.add(self.normalize_url(f"/jobs-in-{location}", base_url))
            
        except Exception as e:
            logger.debug(f"Error generating job location URLs: {e}")
    
    async def crawl_dynamic_url(self, url: str) -> CrawlResult:
        """Optimized dynamic URL crawling."""
        if not self.browser:
            await self._init_playwright()
        
        start_time = time.time()
        page = None
        
        try:
            page = await self.browser.new_page(
                viewport={'width': 1920, 'height': 1080}
            )
            
            # Block unnecessary resources for speed
            await page.route("**/*.{png,jpg,jpeg,gif,svg,ico,css,woff,woff2}", 
                           lambda route: route.abort())
            
            # Navigate with shorter timeout
            try:
                response = await page.goto(
                    url, 
                    wait_until='domcontentloaded',  # Don't wait for all resources
                    timeout=self.config.dynamic_timeout * 1000
                )
                status_code = response.status if response else 0
            except Exception:
                # Try with even shorter timeout
                try:
                    response = await page.goto(url, timeout=5000)
                    status_code = response.status if response else 0
                except Exception:
                    return CrawlResult(
                        url=url,
                        status_code=0,
                        discovered_urls=[],
                        error="Failed to load page",
                        is_dynamic=True,
                        response_time=time.time() - start_time
                    )
            
            # Quick wait for initial content
            await asyncio.sleep(1)
            
            # Extract links efficiently
            discovered_urls = await self._extract_dynamic_links(page, url)
            
            return CrawlResult(
                url=url,
                status_code=status_code,
                discovered_urls=discovered_urls,
                is_dynamic=True,
                response_time=time.time() - start_time
            )
            
        except Exception as e:
            return CrawlResult(
                url=url,
                status_code=0,
                discovered_urls=[],
                error=str(e),
                is_dynamic=True,
                response_time=time.time() - start_time
            )
        finally:
            if page:
                await page.close()
    
    async def _extract_dynamic_links(self, page: Page, base_url: str) -> List[str]:
        """Extract links from dynamic page efficiently."""
        try:
            # Get all links using JavaScript (faster than parsing HTML)
            links = await page.evaluate("""
                () => {
                    const links = [];
                    document.querySelectorAll('a[href], area[href]').forEach(el => {
                        const href = el.getAttribute('href');
                        if (href && !href.startsWith('#') && !href.startsWith('javascript:') && 
                            !href.startsWith('mailto:') && !href.startsWith('tel:')) {
                            links.push(href);
                        }
                    });
                    return links;
                }
            """)
            
            # Handle "Load More" buttons quickly (max 2 clicks)
            await self._handle_load_more_buttons(page, base_url, max_clicks=2)
            
            # Get additional links after interactions
            additional_links = await page.evaluate("""
                () => {
                    const links = [];
                    document.querySelectorAll('a[href], area[href]').forEach(el => {
                        const href = el.getAttribute('href');
                        if (href && !href.startsWith('#') && !href.startsWith('javascript:') && 
                            !href.startsWith('mailto:') && !href.startsWith('tel:')) {
                            links.push(href);
                        }
                    });
                    return links;
                }
            """)
            
            all_links = set(links + additional_links)
            
            # Normalize and filter URLs
            valid_urls = []
            for link in all_links:
                normalized_url = self.normalize_url(link, base_url)
                if (self.is_target_domain(normalized_url) and 
                    not self.should_skip_url(normalized_url) and
                    normalized_url != base_url):
                    valid_urls.append(normalized_url)
            
            return valid_urls
            
        except Exception as e:
            logger.debug(f"Error extracting dynamic links from {base_url}: {e}")
            return []
    
    async def _handle_load_more_buttons(self, page: Page, base_url: str, max_clicks: int = 2):
        """Handle load more buttons with limited clicks for speed."""
        selectors = [
            'button:has-text("Load More")',
            'button:has-text("View More")',
            'a:has-text("Load More")',
            'a:has-text("View More")',
            '.load-more',
            '.view-more'
        ]
        
        clicks = 0
        for selector in selectors:
            if clicks >= max_clicks:
                break
                
            try:
                button = await page.query_selector(selector)
                if button and await button.is_visible():
                    await button.click()
                    await asyncio.sleep(1)  # Quick wait
                    clicks += 1
            except Exception:
                continue
    
    async def crawl_all_urls(self) -> Dict:
        """Main crawling orchestrator."""
        logger.info("Starting high-performance crawl...")
        
        # Add base URLs to queue
        for base_url in self.config.base_urls:
            await self.url_queue.put((base_url, 0))
            self.discovered_urls.add(base_url)
        
        current_depth = 0
        
        while current_depth <= self.config.max_depth:
            # Get URLs for current depth
            depth_urls = []
            temp_queue = []
            
            # Collect all URLs for current depth
            while not self.url_queue.empty():
                url, depth = await self.url_queue.get()
                if depth == current_depth:
                    depth_urls.append(url)
                else:
                    temp_queue.append((url, depth))
            
            # Put back URLs for future depths
            for url, depth in temp_queue:
                await self.url_queue.put((url, depth))
            
            if not depth_urls:
                current_depth += 1
                continue
            
            logger.info(f"Crawling depth {current_depth}: {len(depth_urls)} URLs")
            
            # Separate static and dynamic URLs
            static_urls = []
            dynamic_urls = []
            
            for url in depth_urls:
                if url in self.crawled_urls:
                    continue
                    
                if self.is_dynamic_url(url):
                    dynamic_urls.append(url)
                else:
                    static_urls.append(url)
            
            # Crawl static URLs with high concurrency
            if static_urls:
                await self._crawl_static_batch(static_urls, current_depth)
            
            # Crawl dynamic URLs with limited concurrency
            if dynamic_urls:
                await self._crawl_dynamic_batch(dynamic_urls, current_depth)
            
            current_depth += 1
        
        # Generate statistics
        total_time = time.time() - self.start_time
        stats = {
            'total_discovered': len(self.discovered_urls),
            'total_crawled': len(self.crawled_urls),
            'total_failed': len(self.failed_urls),
            'success_rate': (len(self.crawled_urls) / max(len(self.discovered_urls), 1)) * 100,
            'total_time': total_time,
            'urls_per_second': len(self.crawled_urls) / max(total_time, 1)
        }
        
        logger.info(f"Crawl completed: {stats}")
        return stats
    
    async def _crawl_static_batch(self, urls: List[str], depth: int):
        """Crawl static URLs with high concurrency."""
        semaphore = asyncio.Semaphore(self.config.max_concurrent_static)
        
        async def crawl_with_semaphore(url):
            async with semaphore:
                if self.config.crawl_delay > 0:
                    await asyncio.sleep(self.config.crawl_delay)
                return await self.crawl_static_url(url)
        
        tasks = [crawl_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        await self._process_results(results, depth)
    
    async def _crawl_dynamic_batch(self, urls: List[str], depth: int):
        """Crawl dynamic URLs with limited concurrency."""
        semaphore = asyncio.Semaphore(self.config.max_concurrent_dynamic)
        
        async def crawl_with_semaphore(url):
            async with semaphore:
                return await self.crawl_dynamic_url(url)
        
        tasks = [crawl_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        await self._process_results(results, depth)
    
    async def _process_results(self, results: List, depth: int):
        """Process crawl results and add new URLs to queue."""
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Crawl task failed: {result}")
                continue
            
            if not isinstance(result, CrawlResult):
                continue
            
            self.results.append(result)
            self.crawled_urls.add(result.url)
            
            if result.error:
                self.failed_urls.add(result.url)
                continue
            
            # Add discovered URLs to queue for next depth
            if depth < self.config.max_depth:
                for discovered_url in result.discovered_urls:
                    if (discovered_url not in self.discovered_urls and
                        discovered_url not in self.crawled_urls):
                        self.discovered_urls.add(discovered_url)
                        await self.url_queue.put((discovered_url, depth + 1))
    
    async def generate_sitemap(self) -> List[str]:
        """Generate sitemap from successful crawls."""
        from .sitemap_writer import SitemapWriter
        
        # Get successful URLs
        successful_urls = []
        for result in self.results:
            if result.status_code == 200 and not result.error:
                successful_urls.append({
                    'url': result.url,
                    'lastmod': datetime.utcnow().isoformat() + 'Z',
                    'changefreq': 'weekly',
                    'priority': 0.8 if result.is_dynamic else 0.5
                })
        
        logger.info(f"Generating sitemap with {len(successful_urls)} URLs")
        
        writer = SitemapWriter(self.config.output_dir, self.config.max_urls_per_sitemap)
        sitemap_files = writer.generate_sitemaps(successful_urls, self.config.base_urls[0])
        
        return sitemap_files
    
    async def cleanup(self):
        """Cleanup resources."""
        if self.static_session:
            await self.static_session.close()
        
        if self.browser:
            await self.browser.close()
        
        if self.playwright:
            await self.playwright.stop()

# Main execution function
async def run_optimized_crawler(config: OptimizedConfig) -> Dict:
    """Run the optimized crawler."""
    crawler = HighPerformanceCrawler(config)
    
    try:
        await crawler.initialize()
        stats = await crawler.crawl_all_urls()
        sitemap_files = await crawler.generate_sitemap()
        
        stats['sitemap_files'] = sitemap_files
        return stats
        
    finally:
        await crawler.cleanup()

# CLI interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="High-Performance Finploy Sitemap Generator")
    parser.add_argument("--base-urls", nargs="+", 
                       default=["https://www.finploy.com", "https://finploy.co.uk"],
                       help="Base URLs to crawl")
    parser.add_argument("--max-depth", type=int, default=4, help="Maximum crawl depth")
    parser.add_argument("--output-dir", default="data/sitemap/", help="Output directory")
    
    args = parser.parse_args()
    
    config = OptimizedConfig(
        base_urls=args.base_urls,
        max_depth=args.max_depth,
        output_dir=args.output_dir
    )
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run crawler
    stats = asyncio.run(run_optimized_crawler(config))
    
    print("\n" + "="*60)
    print("OPTIMIZED CRAWL RESULTS")
    print("="*60)
    print(f"Total URLs discovered: {stats['total_discovered']:,}")
    print(f"Total URLs crawled: {stats['total_crawled']:,}")
    print(f"Success rate: {stats['success_rate']:.1f}%")
    print(f"Total time: {stats['total_time']:.1f} seconds")
    print(f"Speed: {stats['urls_per_second']:.1f} URLs/second")
    print(f"Sitemap files: {len(stats.get('sitemap_files', []))}")
    print("="*60)
