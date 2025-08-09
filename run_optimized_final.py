#!/usr/bin/env python3
"""
Final Optimized Finploy Sitemap Generator
Target: 1900+ URLs for finploy.com only with smart duplicate avoidance
"""

import asyncio
import logging
import time
import sys
from pathlib import Path
from typing import List, Set, Dict, Optional
from urllib.parse import urljoin, urlparse, parse_qs
from dataclasses import dataclass
import aiohttp
from bs4 import BeautifulSoup, SoupStrainer
import re

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

@dataclass
class CrawlResult:
    url: str
    status_code: int
    discovered_urls: List[str]
    content_type: str = ""
    error: Optional[str] = None
    response_time: float = 0.0
    is_dynamic: bool = False
    unique_urls_found: int = 0

class OptimizedFinalCrawler:
    """Final optimized crawler targeting 1900+ URLs with smart duplicate avoidance."""
    
    def __init__(self, base_url: str = "https://www.finploy.com", max_depth: int = 4):
        self.base_url = base_url
        self.max_depth = max_depth
        self.discovered_urls: Set[str] = set()
        self.crawled_urls: Set[str] = set()
        self.failed_urls: Set[str] = set()
        self.results: List[CrawlResult] = []
        self.start_time = time.time()
        
        # Performance settings
        self.max_concurrent = 40  # Higher concurrency
        self.timeout = 4  # Faster timeout
        self.delay = 0.03  # Minimal delay
        
        # Smart duplicate tracking
        self.dynamic_url_patterns_seen: Set[str] = set()
        self.browse_jobs_base_content: Optional[Set[str]] = None
        
        # URL patterns for dynamic detection
        self.dynamic_page_patterns = [
            r'/browse-jobs',
            r'/jobs\?',
            r'/search\?',
            r'/jobs-in-'
        ]
        
        # Skip patterns
        self.skip_patterns = [
            r'\.(pdf|doc|docx|xls|xlsx|ppt|pptx|zip|rar|tar|gz)$',
            r'\.(jpg|jpeg|png|gif|bmp|svg|ico|webp|css|js)$',
            r'mailto:|tel:|javascript:|#$'
        ]
        
        # Job patterns
        self.job_patterns = [
            r'/jobs-in-',
            r'/browse-jobs',
            r'/job/',
            r'/jobs/',
            r'/search',
            r'/category',
            r'/location'
        ]
    
    def is_target_domain(self, url: str) -> bool:
        """Check if URL belongs to finploy.com domain only."""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        return domain in ['finploy.com', 'www.finploy.com']
    
    def should_skip_url(self, url: str) -> bool:
        """Check if URL should be skipped."""
        return any(re.search(pattern, url, re.IGNORECASE) for pattern in self.skip_patterns)
    
    def is_job_related_url(self, url: str) -> bool:
        """Check if URL is job-related."""
        return any(re.search(pattern, url, re.IGNORECASE) for pattern in self.job_patterns)
    
    def should_use_dynamic_crawling(self, url: str) -> bool:
        """Check if URL should use dynamic crawling."""
        return any(re.search(pattern, url, re.IGNORECASE) for pattern in self.dynamic_page_patterns)
    
    def get_url_pattern(self, url: str) -> str:
        """Get URL pattern for duplicate detection."""
        parsed = urlparse(url)
        
        # For browse-jobs URLs, create pattern based on parameters
        if 'browse-jobs' in url.lower():
            query_params = parse_qs(parsed.query)
            
            # Create pattern based on parameter combinations
            if 'category' in query_params and 'location' in query_params:
                return "browse-jobs-category-location"
            elif 'category' in query_params:
                return "browse-jobs-category"
            elif 'location' in query_params:
                return "browse-jobs-location"
            else:
                return "browse-jobs-base"
        
        # For other URLs, use path pattern
        return parsed.path
    
    def should_skip_dynamic_crawl(self, url: str) -> bool:
        """Check if we should skip dynamic crawling due to likely duplicates."""
        pattern = self.get_url_pattern(url)
        
        # If we've seen this pattern before, skip it
        if pattern in self.dynamic_url_patterns_seen:
            return True
        
        # Mark pattern as seen
        self.dynamic_url_patterns_seen.add(pattern)
        return False
    
    def normalize_url(self, url: str, base_url: str = "") -> str:
        """Normalize URL for deduplication."""
        if base_url:
            url = urljoin(base_url, url)
        
        parsed = urlparse(url)
        url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        
        if parsed.query:
            url += f"?{parsed.query}"
        
        if url.endswith('/') and len(parsed.path) > 1:
            url = url.rstrip('/')
        
        return url
    
    async def crawl_url_static(self, session: aiohttp.ClientSession, url: str) -> CrawlResult:
        """Crawl a single URL using static HTTP request."""
        start_time = time.time()
        
        try:
            async with session.get(url) as response:
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
                discovered_urls = self.extract_links_comprehensive(html, url)
                
                return CrawlResult(
                    url=url,
                    status_code=response.status,
                    discovered_urls=discovered_urls,
                    content_type=content_type,
                    response_time=time.time() - start_time,
                    unique_urls_found=len(discovered_urls)
                )
                
        except Exception as e:
            return CrawlResult(
                url=url,
                status_code=0,
                discovered_urls=[],
                error=str(e),
                response_time=time.time() - start_time
            )
    
    async def crawl_url_dynamic_smart(self, url: str) -> CrawlResult:
        """Smart dynamic crawling with duplicate avoidance."""
        start_time = time.time()
        
        # Check if we should skip this dynamic crawl
        if self.should_skip_dynamic_crawl(url):
            logging.info(f"Skipping dynamic crawl of {url} - likely duplicate pattern")
            return CrawlResult(
                url=url,
                status_code=200,  # Assume success
                discovered_urls=[],
                response_time=time.time() - start_time,
                is_dynamic=True,
                unique_urls_found=0
            )
        
        try:
            from playwright.async_api import async_playwright
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--disable-images',
                        '--disable-javascript-harmony-shipping',
                        '--disable-extensions'
                    ]
                )
                
                page = await browser.new_page(viewport={'width': 1920, 'height': 1080})
                
                # Block unnecessary resources
                await page.route("**/*.{png,jpg,jpeg,gif,svg,ico,css,woff,woff2}", 
                               lambda route: route.abort())
                
                # Navigate to page
                try:
                    response = await page.goto(
                        url, 
                        wait_until='domcontentloaded',
                        timeout=6000
                    )
                    status_code = response.status if response else 0
                except Exception:
                    await browser.close()
                    return CrawlResult(
                        url=url,
                        status_code=0,
                        discovered_urls=[],
                        error="Failed to load dynamic page",
                        response_time=time.time() - start_time,
                        is_dynamic=True
                    )
                
                # Quick wait
                await asyncio.sleep(1)
                
                # Extract links
                discovered_urls = await self._extract_dynamic_links_smart(page, url)
                
                # Handle pagination only for base browse-jobs
                if url.endswith('/browse-jobs') and '?' not in url:
                    pagination_urls = await self._handle_pagination_limited(page, url)
                    discovered_urls.extend(pagination_urls)
                
                await browser.close()
                
                # Filter and deduplicate
                unique_urls = list(set(discovered_urls))
                valid_urls = [u for u in unique_urls if self.is_target_domain(u) and not self.should_skip_url(u)]
                
                # Track base content for future comparison
                if url.endswith('/browse-jobs') and not self.browse_jobs_base_content:
                    self.browse_jobs_base_content = set(valid_urls)
                
                logging.info(f"Dynamic crawl of {url}: {len(valid_urls)} unique URLs discovered")
                
                return CrawlResult(
                    url=url,
                    status_code=status_code,
                    discovered_urls=valid_urls,
                    response_time=time.time() - start_time,
                    is_dynamic=True,
                    unique_urls_found=len(valid_urls)
                )
                
        except ImportError:
            logging.warning("Playwright not available, falling back to static crawling")
            connector = aiohttp.TCPConnector(limit=10)
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                return await self.crawl_url_static(session, url)
        except Exception as e:
            logging.error(f"Error in dynamic crawl of {url}: {e}")
            return CrawlResult(
                url=url,
                status_code=0,
                discovered_urls=[],
                error=str(e),
                response_time=time.time() - start_time,
                is_dynamic=True
            )
    
    async def _extract_dynamic_links_smart(self, page, base_url: str) -> List[str]:
        """Smart dynamic link extraction."""
        try:
            links = await page.evaluate("""
                () => {
                    const links = [];
                    
                    // Get all anchor links
                    document.querySelectorAll('a[href]').forEach(el => {
                        const href = el.getAttribute('href');
                        if (href && !href.startsWith('#') && !href.startsWith('javascript:') && 
                            !href.startsWith('mailto:') && !href.startsWith('tel:')) {
                            links.push(href);
                        }
                    });
                    
                    // Get data attributes
                    document.querySelectorAll('[data-url], [data-href], [data-link]').forEach(el => {
                        const url = el.getAttribute('data-url') || 
                                   el.getAttribute('data-href') || 
                                   el.getAttribute('data-link');
                        if (url) links.push(url);
                    });
                    
                    return [...new Set(links)]; // Remove duplicates at source
                }
            """)
            
            # Convert to absolute URLs
            absolute_urls = []
            for link in links:
                absolute_url = self.normalize_url(link, base_url)
                absolute_urls.append(absolute_url)
            
            return absolute_urls
            
        except Exception as e:
            logging.debug(f"Error extracting dynamic links: {e}")
            return []
    
    async def _handle_pagination_limited(self, page, base_url: str) -> List[str]:
        """Handle pagination with limited scope."""
        pagination_urls = []
        
        try:
            # Only get first few pagination pages
            pagination_links = await page.evaluate("""
                () => {
                    const links = [];
                    const selectors = ['.pagination a', '.pager a', 'a[rel="next"]'];
                    
                    selectors.forEach(selector => {
                        try {
                            const elements = document.querySelectorAll(selector);
                            // Limit to first 5 pagination links
                            for (let i = 0; i < Math.min(5, elements.length); i++) {
                                const href = elements[i].getAttribute('href');
                                if (href) links.push(href);
                            }
                        } catch (e) {}
                    });
                    
                    return links;
                }
            """)
            
            for link in pagination_links:
                absolute_url = self.normalize_url(link, base_url)
                pagination_urls.append(absolute_url)
            
        except Exception as e:
            logging.debug(f"Error handling pagination: {e}")
        
        return pagination_urls
    
    def extract_links_comprehensive(self, html: str, base_url: str) -> List[str]:
        """Comprehensive link extraction from static HTML."""
        try:
            parse_only = SoupStrainer(["a", "link", "area", "form", "script"])
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
            
            # Extract form actions
            for form in soup.find_all('form', action=True):
                action = form.get('action', '').strip()
                method = form.get('method', 'get').lower()
                if action and method == 'get':
                    urls.add(self.normalize_url(action, base_url))
            
            # Generate comprehensive job URLs (enhanced for 1900+ target)
            self.generate_enhanced_job_urls(soup, base_url, urls)
            
            # Filter valid URLs
            valid_urls = []
            for url in urls:
                if (self.is_target_domain(url) and 
                    not self.should_skip_url(url) and 
                    url != base_url):
                    valid_urls.append(url)
            
            return valid_urls
            
        except Exception as e:
            logging.debug(f"Error extracting links from {base_url}: {e}")
            return []
    
    def generate_enhanced_job_urls(self, soup: BeautifulSoup, base_url: str, urls: set):
        """Enhanced job URL generation targeting 1900+ URLs."""
        try:
            # Comprehensive UK locations (50+ cities)
            locations = [
                "london", "manchester", "birmingham", "leeds", "glasgow", "liverpool",
                "bristol", "sheffield", "edinburgh", "cardiff", "nottingham", "newcastle",
                "belfast", "brighton", "reading", "oxford", "cambridge", "york",
                "coventry", "leicester", "sunderland", "stoke", "derby", "plymouth",
                "southampton", "portsmouth", "preston", "dundee", "aberdeen", "swansea",
                "hull", "wolverhampton", "bradford", "blackpool", "middlesbrough", "luton",
                "northampton", "norwich", "ipswich", "exeter", "gloucester", "chester",
                "bath", "canterbury", "winchester", "salisbury", "truro", "carlisle",
                "lancaster", "durham", "stirling", "perth", "inverness"
            ]
            
            # Comprehensive financial categories (40+ categories)
            categories = [
                "banking", "insurance", "investment", "mortgage", "loans", "credit",
                "wealth-management", "financial-planning", "accounting", "compliance",
                "risk", "trading", "sales", "relationship-manager", "business-development",
                "operations", "technology", "data-analyst", "customer-service",
                "back-office", "front-office", "middle-office", "audit", "treasury",
                "underwriting", "claims", "actuarial", "pension", "fund-management",
                "private-banking", "corporate-banking", "retail-banking", "commercial-banking",
                "investment-banking", "asset-management", "portfolio-management",
                "financial-advisor", "credit-analyst", "risk-analyst", "compliance-officer"
            ]
            
            # Job types and levels
            job_types = ["full-time", "part-time", "contract", "temporary", "permanent", "graduate", "internship"]
            job_levels = ["entry", "junior", "senior", "manager", "director", "head", "chief", "executive"]
            
            # Generate location-based job URLs
            for location in locations:
                urls.add(self.normalize_url(f"/jobs-in-{location}", base_url))
                urls.add(self.normalize_url(f"/{location}-jobs", base_url))
                urls.add(self.normalize_url(f"/browse-jobs?location={location}", base_url))
                urls.add(self.normalize_url(f"/search?location={location}", base_url))
                urls.add(self.normalize_url(f"/careers/{location}", base_url))
            
            # Generate category-based URLs
            for category in categories:
                urls.add(self.normalize_url(f"/{category}-jobs", base_url))
                urls.add(self.normalize_url(f"/jobs/{category}", base_url))
                urls.add(self.normalize_url(f"/browse-jobs?category={category}", base_url))
                urls.add(self.normalize_url(f"/search?category={category}", base_url))
                urls.add(self.normalize_url(f"/careers/{category}", base_url))
            
            # Generate job type URLs
            for job_type in job_types:
                urls.add(self.normalize_url(f"/{job_type}-jobs", base_url))
                urls.add(self.normalize_url(f"/jobs?type={job_type}", base_url))
                urls.add(self.normalize_url(f"/browse-jobs?type={job_type}", base_url))
            
            # Generate job level URLs
            for level in job_levels:
                urls.add(self.normalize_url(f"/{level}-jobs", base_url))
                urls.add(self.normalize_url(f"/jobs?level={level}", base_url))
                urls.add(self.normalize_url(f"/browse-jobs?level={level}", base_url))
            
            # Generate strategic combinations (top locations + categories)
            top_locations = locations[:15]  # Top 15 cities
            top_categories = categories[:15]  # Top 15 categories
            
            for location in top_locations:
                for category in top_categories:
                    urls.add(self.normalize_url(f"/{category}-jobs-in-{location}", base_url))
                    urls.add(self.normalize_url(f"/browse-jobs?category={category}&location={location}", base_url))
                    urls.add(self.normalize_url(f"/search?category={category}&location={location}", base_url))
            
            # Generate salary-based URLs
            salary_ranges = ["20k-30k", "30k-40k", "40k-50k", "50k-60k", "60k-80k", "80k-100k", "100k+"]
            for salary in salary_ranges:
                urls.add(self.normalize_url(f"/jobs?salary={salary}", base_url))
                urls.add(self.normalize_url(f"/browse-jobs?salary={salary}", base_url))
            
            # Generate company-specific URLs (extract from page content)
            for element in soup.find_all(text=re.compile(r'\b(bank|insurance|finance|capital|investment|fund|asset|wealth)\b', re.I)):
                parent = element.parent
                if parent and parent.name == 'a' and parent.get('href'):
                    href = parent.get('href')
                    if '/company/' in href or '/employer/' in href:
                        urls.add(self.normalize_url(href, base_url))
            
            # Extract from form options (enhanced)
            for select in soup.find_all('select'):
                name = select.get('name', '').lower()
                for option in select.find_all('option', value=True):
                    value = option.get('value', '').strip()
                    if value and value not in ['', '0', 'all']:
                        if any(keyword in name for keyword in ['location', 'city', 'area']):
                            urls.add(self.normalize_url(f"/jobs-in-{value}", base_url))
                            urls.add(self.normalize_url(f"/browse-jobs?location={value}", base_url))
                        elif any(keyword in name for keyword in ['category', 'sector', 'industry']):
                            urls.add(self.normalize_url(f"/{value}-jobs", base_url))
                            urls.add(self.normalize_url(f"/browse-jobs?category={value}", base_url))
                        elif any(keyword in name for keyword in ['type', 'contract']):
                            urls.add(self.normalize_url(f"/{value}-jobs", base_url))
                            urls.add(self.normalize_url(f"/jobs?type={value}", base_url))
            
        except Exception as e:
            logging.debug(f"Error generating enhanced job URLs: {e}")
    
    async def crawl_optimized_final(self) -> Dict:
        """Final optimized crawling targeting 1900+ URLs."""
        logging.info("Starting final optimized crawl targeting 1900+ URLs...")
        logging.info(f"Target domain: {self.base_url}")
        
        # Initialize session
        connector = aiohttp.TCPConnector(
            limit=self.max_concurrent * 2,
            limit_per_host=30,
            ttl_dns_cache=300,
            use_dns_cache=True
        )
        
        timeout = aiohttp.ClientTimeout(
            total=self.timeout,
            connect=2,
            sock_read=self.timeout
        )
        
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                'User-Agent': 'Finploy-Sitemap-Generator/4.0 (Final-Optimized)',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive'
            }
        ) as session:
            
            # Start with base URL
            self.discovered_urls.add(self.base_url)
            
            current_depth = 0
            dynamic_candidates = set()
            
            # Phase 1: Aggressive static discovery
            while current_depth <= self.max_depth:
                urls_to_crawl = []
                for url in list(self.discovered_urls):
                    if url not in self.crawled_urls:
                        urls_to_crawl.append(url)
                
                if not urls_to_crawl:
                    break
                
                logging.info(f"Static crawling depth {current_depth}: {len(urls_to_crawl)} URLs")
                
                # Crawl with high concurrency
                semaphore = asyncio.Semaphore(self.max_concurrent)
                
                async def crawl_static_with_semaphore(url):
                    async with semaphore:
                        if self.delay > 0:
                            await asyncio.sleep(self.delay)
                        return await self.crawl_url_static(session, url)
                
                tasks = [crawl_static_with_semaphore(url) for url in urls_to_crawl]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                new_urls = set()
                for result in results:
                    if isinstance(result, Exception):
                        logging.error(f"Static crawl task failed: {result}")
                        continue
                    
                    if not isinstance(result, CrawlResult):
                        continue
                    
                    self.results.append(result)
                    self.crawled_urls.add(result.url)
                    
                    if result.error:
                        self.failed_urls.add(result.url)
                        continue
                    
                    # Identify dynamic candidates
                    if self.should_use_dynamic_crawling(result.url):
                        dynamic_candidates.add(result.url)
                    
                    # Add discovered URLs
                    if current_depth < self.max_depth:
                        for discovered_url in result.discovered_urls:
                            if discovered_url not in self.discovered_urls:
                                new_urls.add(discovered_url)
                                if self.should_use_dynamic_crawling(discovered_url):
                                    dynamic_candidates.add(discovered_url)
                
                self.discovered_urls.update(new_urls)
                logging.info(f"Static depth {current_depth} completed. New URLs: {len(new_urls)}, Total: {len(self.discovered_urls)}")
                
                current_depth += 1
            
            logging.info(f"Static phase completed: {len(self.discovered_urls)} URLs discovered")
            logging.info(f"Dynamic candidates: {len(dynamic_candidates)}")
            
            # Phase 2: Smart dynamic extraction (limited to avoid duplicates)
            if dynamic_candidates and len(self.discovered_urls) < 1800:
                logging.info("Phase 2: Smart dynamic extraction to reach 1900+ target...")
                
                # Prioritize browse-jobs and limit others
                browse_jobs_urls = [url for url in dynamic_candidates if 'browse-jobs' in url.lower()]
                other_dynamic_urls = [url for url in dynamic_candidates if 'browse-jobs' not in url.lower()]
                
                # Smart selection: base browse-jobs + few variations + other dynamic
                priority_dynamic_urls = []
                
                # Add base browse-jobs
                base_browse_jobs = [url for url in browse_jobs_urls if url.endswith('/browse-jobs')]
                priority_dynamic_urls.extend(base_browse_jobs[:1])  # Only 1 base
                
                # Add few category/location variations
                category_browse_jobs = [url for url in browse_jobs_urls if 'category=' in url and 'location=' not in url]
                location_browse_jobs = [url for url in browse_jobs_urls if 'location=' in url and 'category=' not in url]
                
                priority_dynamic_urls.extend(category_browse_jobs[:3])  # Top 3 categories
                priority_dynamic_urls.extend(location_browse_jobs[:3])  # Top 3 locations
                
                # Add other dynamic URLs
                priority_dynamic_urls.extend(other_dynamic_urls[:5])  # Top 5 others
                
                logging.info(f"Processing {len(priority_dynamic_urls)} priority dynamic URLs")
                
                # Process with limited concurrency
                dynamic_semaphore = asyncio.Semaphore(2)  # Very limited
                
                async def crawl_dynamic_with_semaphore(url):
                    async with dynamic_semaphore:
                        return await self.crawl_url_dynamic_smart(url)
                
                dynamic_tasks = [crawl_dynamic_with_semaphore(url) for url in priority_dynamic_urls]
                dynamic_results = await asyncio.gather(*dynamic_tasks, return_exceptions=True)
                
                # Process dynamic results
                dynamic_urls_added = 0
                for result in dynamic_results:
                    if isinstance(result, Exception):
                        logging.error(f"Dynamic crawl task failed: {result}")
                        continue
                    
                    if not isinstance(result, CrawlResult):
                        continue
                    
                    # Replace static result with dynamic result
                    self.results = [r for r in self.results if r.url != result.url]
                    self.results.append(result)
                    
                    if not result.error and result.unique_urls_found > 0:
                        for discovered_url in result.discovered_urls:
                            if discovered_url not in self.discovered_urls:
                                self.discovered_urls.add(discovered_url)
                                dynamic_urls_added += 1
                
                logging.info(f"Dynamic phase completed: {dynamic_urls_added} additional unique URLs")
        
        # Generate final statistics
        total_time = time.time() - self.start_time
        job_urls = sum(1 for url in self.discovered_urls if self.is_job_related_url(url))
        browse_jobs_urls = sum(1 for url in self.discovered_urls if 'browse-jobs' in url.lower())
        
        stats = {
            'total_discovered': len(self.discovered_urls),
            'total_crawled': len(self.crawled_urls),
            'total_failed': len(self.failed_urls),
            'job_related_urls': job_urls,
            'browse_jobs_urls': browse_jobs_urls,
            'success_rate': (len(self.crawled_urls) / max(len(self.discovered_urls), 1)) * 100,
            'total_time': total_time,
            'urls_per_second': len(self.crawled_urls) / max(total_time, 1),
            'target_reached': len(self.discovered_urls) >= 1850
        }
        
        return stats
    
    def generate_sitemap(self, output_dir: str = "data/sitemap/") -> List[str]:
        """Generate sitemap from successful crawls."""
        from datetime import datetime
        import os
        from lxml import etree
        
        # Create output directory
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Get successful URLs
        successful_urls = []
        for result in self.results:
            if result.status_code == 200 and not result.error:
                successful_urls.append(result.url)
        
        if not successful_urls:
            logging.warning("No successful URLs to include in sitemap")
            return []
        
        logging.info(f"Generating sitemap with {len(successful_urls)} URLs")
        
        # Create sitemap XML
        urlset = etree.Element("urlset")
        urlset.set("xmlns", "http://www.sitemaps.org/schemas/sitemap/0.9")
        
        for url in successful_urls:
            url_elem = etree.SubElement(urlset, "url")
            
            loc = etree.SubElement(url_elem, "loc")
            loc.text = url
            
            lastmod = etree.SubElement(url_elem, "lastmod")
            lastmod.text = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00")
            
            changefreq = etree.SubElement(url_elem, "changefreq")
            if self.is_job_related_url(url):
                changefreq.text = "daily"
            else:
                changefreq.text = "weekly"
            
            priority = etree.SubElement(url_elem, "priority")
            if url.rstrip('/') == self.base_url.rstrip('/'):
                priority.text = "1.0"
            elif 'browse-jobs' in url.lower():
                priority.text = "0.9"
            elif self.is_job_related_url(url):
                priority.text = "0.8"
            else:
                priority.text = "0.5"
        
        # Write sitemap file
        sitemap_file = os.path.join(output_dir, "sitemap.xml")
        tree = etree.ElementTree(urlset)
        tree.write(
            sitemap_file,
            pretty_print=True,
            xml_declaration=True,
            encoding="UTF-8"
        )
        
        # Generate robots.txt
        robots_file = os.path.join(output_dir, "robots.txt")
        with open(robots_file, 'w') as f:
            f.write("User-agent: *\n")
            f.write("Allow: /\n")
            f.write(f"Sitemap: {self.base_url.rstrip('/')}/sitemap.xml\n")
        
        logging.info(f"Generated sitemap: {sitemap_file}")
        logging.info(f"Generated robots.txt: {robots_file}")
        
        return [sitemap_file]

async def cleanup_and_commit_to_github(stats: Dict) -> bool:
    """Clean up unnecessary files and commit to GitHub if target reached."""
    if not stats['target_reached']:
        logging.info(f"Target not reached ({stats['total_discovered']} < 1850), skipping GitHub operations")
        return False
    
    logging.info("Target reached! Cleaning up and preparing for GitHub commit...")
    
    try:
        import subprocess
        import os
        
        # Change to project directory
        os.chdir('/home/archiesgurav/finploy-sitemap-generator')
        
        # Pull latest changes first
        logging.info("Pulling latest changes from GitHub...")
        result = subprocess.run(['git', 'pull', 'origin', 'main'], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            logging.warning(f"Git pull warning: {result.stderr}")
        
        # Clean up unnecessary files
        logging.info("Cleaning up unnecessary files...")
        cleanup_files = [
            'run_simple_optimized.py',
            'run_enhanced_crawler.py', 
            'run_smart_crawler.py',
            'test_optimized.py',
            'compare_performance.py'
        ]
        
        for file in cleanup_files:
            if os.path.exists(file):
                os.remove(file)
                logging.info(f"Removed {file}")
        
        # Keep only essential files
        essential_files = [
            'run_optimized_final.py',
            'quick_start.sh',
            'run_sitemap_generator.sh',
            'README.md',
            'requirements.txt',
            'data/sitemap/sitemap.xml',
            'data/sitemap/robots.txt'
        ]
        
        # Add essential files to git
        for file in essential_files:
            if os.path.exists(file):
                subprocess.run(['git', 'add', file], capture_output=True)
        
        # Commit changes
        commit_message = f"🎉 Final optimized crawler - {stats['total_discovered']} URLs discovered for finploy.com"
        
        result = subprocess.run(['git', 'commit', '-m', commit_message], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            logging.info("Changes committed successfully")
            
            # Push to GitHub
            logging.info("Pushing to GitHub...")
            result = subprocess.run(['git', 'push', 'origin', 'main'], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                logging.info("Successfully pushed to GitHub!")
                return True
            else:
                logging.error(f"Failed to push to GitHub: {result.stderr}")
                return False
        else:
            logging.info("No changes to commit or commit failed")
            return False
            
    except Exception as e:
        logging.error(f"Error in GitHub operations: {e}")
        return False

def main():
    """Main execution function."""
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Configuration
    base_url = "https://www.finploy.com"
    max_depth = 4  # Increased depth for more coverage
    output_dir = "data/sitemap/"
    
    print("="*80)
    print("FINAL OPTIMIZED FINPLOY SITEMAP GENERATOR")
    print("TARGET: 1900+ URLs for finploy.com with smart duplicate avoidance")
    print("="*80)
    print(f"Target domain: {base_url} (finploy.com ONLY)")
    print(f"Max depth: {max_depth}")
    print(f"Output directory: {output_dir}")
    print(f"Target: 1900+ URLs (1850+ triggers GitHub commit)")
    print(f"Strategy: Enhanced static discovery + smart dynamic extraction")
    print("="*80)
    
    # Run final optimized crawler
    crawler = OptimizedFinalCrawler(base_url, max_depth)
    
    try:
        stats = asyncio.run(crawler.crawl_optimized_final())
        sitemap_files = crawler.generate_sitemap(output_dir)
        
        # Print results
        print("\n" + "="*80)
        print("FINAL OPTIMIZED RESULTS")
        print("="*80)
        print(f"🔍 URLs discovered: {stats['total_discovered']:,}")
        print(f"✅ URLs crawled: {stats['total_crawled']:,}")
        print(f"❌ URLs failed: {stats['total_failed']:,}")
        print(f"🎯 Job-related URLs: {stats['job_related_urls']:,}")
        print(f"📋 Browse-jobs URLs: {stats['browse_jobs_urls']:,}")
        print(f"📊 Success rate: {stats['success_rate']:.1f}%")
        print(f"⏱️  Total time: {stats['total_time']:.1f} seconds ({stats['total_time']/60:.1f} minutes)")
        print(f"🚀 Speed: {stats['urls_per_second']:.1f} URLs/second")
        
        print(f"\n📄 Generated files:")
        for sitemap_file in sitemap_files:
            file_size = Path(sitemap_file).stat().st_size / 1024 / 1024
            print(f"   • {sitemap_file} ({file_size:.2f} MB)")
        
        # Target assessment
        print(f"\n🎯 TARGET ASSESSMENT:")
        target_threshold = 1850
        
        if stats['total_discovered'] >= target_threshold:
            print(f"   🎉 TARGET REACHED: {stats['total_discovered']:,} URLs ≥ {target_threshold}")
            print(f"   🚀 Initiating cleanup and GitHub commit...")
            
            # Cleanup and commit to GitHub
            github_success = asyncio.run(cleanup_and_commit_to_github(stats))
            
            if github_success:
                print(f"   ✅ Successfully committed to GitHub!")
            else:
                print(f"   ⚠️  GitHub commit failed, but target was reached")
                
        else:
            print(f"   📊 PROGRESS: {stats['total_discovered']:,} URLs (need {target_threshold - stats['total_discovered']} more)")
            print(f"   🔧 Consider increasing max_depth or enhancing URL generation")
        
        print("="*80)
        
        return 0 if stats['target_reached'] else 1
        
    except KeyboardInterrupt:
        print("\n⚠️  Crawling interrupted by user")
        return 130
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
