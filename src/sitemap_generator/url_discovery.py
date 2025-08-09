"""
Advanced URL discovery module for comprehensive Finploy site crawling.
Designed to discover all ~1900 URLs including deep job listings and dynamic content.
"""

import asyncio
import logging
import re
from typing import List, Set, Dict, Optional
from urllib.parse import urljoin, urlparse, parse_qs, urlencode
import aiohttp
from bs4 import BeautifulSoup
from playwright.async_api import Page

logger = logging.getLogger(__name__)

class AdvancedURLDiscovery:
    """Advanced URL discovery for comprehensive site crawling."""
    
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.discovered_patterns: Set[str] = set()
        
        # Common job-related URL patterns for Finploy
        self.job_patterns = [
            "/jobs-in-{location}",
            "/{location}-jobs",
            "/jobs/{category}",
            "/{category}-jobs",
            "/jobs/{category}/{location}",
            "/search?location={location}",
            "/search?category={category}",
            "/search?q={keyword}",
            "/jobs?location={location}",
            "/jobs?category={category}",
            "/jobs?type={type}",
            "/jobs?level={level}"
        ]
        
        # Common location variations
        self.locations = [
            "london", "manchester", "birmingham", "leeds", "glasgow", "liverpool",
            "bristol", "sheffield", "edinburgh", "cardiff", "nottingham", "newcastle",
            "belfast", "brighton", "reading", "oxford", "cambridge", "york",
            "coventry", "leicester", "sunderland", "stoke", "derby", "plymouth",
            "southampton", "portsmouth", "preston", "dundee", "aberdeen", "swansea"
        ]
        
        # Financial services categories
        self.categories = [
            "banking", "insurance", "investment", "mortgage", "loans", "credit",
            "wealth-management", "financial-planning", "accounting", "audit",
            "compliance", "risk", "trading", "sales", "relationship-manager",
            "business-development", "operations", "technology", "data-analyst",
            "customer-service", "back-office", "front-office", "middle-office"
        ]
        
        # Job types and levels
        self.job_types = ["full-time", "part-time", "contract", "temporary", "permanent"]
        self.job_levels = ["entry", "junior", "senior", "manager", "director", "graduate"]
    
    async def discover_comprehensive_urls(self, base_url: str) -> Set[str]:
        """Discover comprehensive URL set using multiple strategies."""
        all_urls = set()
        
        # Strategy 1: Sitemap discovery
        sitemap_urls = await self._discover_from_sitemaps(base_url)
        all_urls.update(sitemap_urls)
        logger.info(f"Found {len(sitemap_urls)} URLs from sitemaps")
        
        # Strategy 2: Robots.txt analysis
        robots_urls = await self._discover_from_robots(base_url)
        all_urls.update(robots_urls)
        logger.info(f"Found {len(robots_urls)} URLs from robots.txt")
        
        # Strategy 3: Homepage deep analysis
        homepage_urls = await self._discover_from_homepage(base_url)
        all_urls.update(homepage_urls)
        logger.info(f"Found {len(homepage_urls)} URLs from homepage analysis")
        
        # Strategy 4: Pattern-based URL generation
        pattern_urls = await self._generate_pattern_urls(base_url)
        all_urls.update(pattern_urls)
        logger.info(f"Generated {len(pattern_urls)} URLs from patterns")
        
        # Strategy 5: Search functionality discovery
        search_urls = await self._discover_search_urls(base_url)
        all_urls.update(search_urls)
        logger.info(f"Found {len(search_urls)} URLs from search functionality")
        
        # Strategy 6: API endpoint discovery
        api_urls = await self._discover_api_endpoints(base_url)
        all_urls.update(api_urls)
        logger.info(f"Found {len(api_urls)} URLs from API endpoints")
        
        logger.info(f"Total comprehensive discovery: {len(all_urls)} URLs")
        return all_urls
    
    async def _discover_from_sitemaps(self, base_url: str) -> Set[str]:
        """Discover URLs from existing sitemaps."""
        urls = set()
        
        # Common sitemap locations
        sitemap_paths = [
            "/sitemap.xml",
            "/sitemap_index.xml",
            "/sitemaps.xml",
            "/sitemap/sitemap.xml",
            "/wp-sitemap.xml"
        ]
        
        for path in sitemap_paths:
            sitemap_url = urljoin(base_url, path)
            try:
                async with self.session.get(sitemap_url) as response:
                    if response.status == 200:
                        content = await response.text()
                        sitemap_urls = self._parse_sitemap_xml(content, base_url)
                        urls.update(sitemap_urls)
                        logger.debug(f"Found sitemap at {sitemap_url} with {len(sitemap_urls)} URLs")
            except Exception as e:
                logger.debug(f"Could not fetch sitemap {sitemap_url}: {e}")
        
        return urls
    
    def _parse_sitemap_xml(self, xml_content: str, base_url: str) -> Set[str]:
        """Parse sitemap XML and extract URLs."""
        urls = set()
        
        try:
            soup = BeautifulSoup(xml_content, 'xml')
            
            # Handle sitemap index files
            for sitemap in soup.find_all('sitemap'):
                loc = sitemap.find('loc')
                if loc:
                    sitemap_url = loc.get_text().strip()
                    # Recursively fetch sub-sitemaps (limited depth)
                    asyncio.create_task(self._fetch_sub_sitemap(sitemap_url, urls))
            
            # Handle regular sitemap files
            for url_elem in soup.find_all('url'):
                loc = url_elem.find('loc')
                if loc:
                    url = loc.get_text().strip()
                    if self._is_valid_url(url, base_url):
                        urls.add(url)
        
        except Exception as e:
            logger.debug(f"Error parsing sitemap XML: {e}")
        
        return urls
    
    async def _fetch_sub_sitemap(self, sitemap_url: str, urls: Set[str]):
        """Fetch and parse sub-sitemap."""
        try:
            async with self.session.get(sitemap_url) as response:
                if response.status == 200:
                    content = await response.text()
                    sub_urls = self._parse_sitemap_xml(content, sitemap_url)
                    urls.update(sub_urls)
        except Exception as e:
            logger.debug(f"Error fetching sub-sitemap {sitemap_url}: {e}")
    
    async def _discover_from_robots(self, base_url: str) -> Set[str]:
        """Discover URLs from robots.txt."""
        urls = set()
        
        robots_url = urljoin(base_url, "/robots.txt")
        try:
            async with self.session.get(robots_url) as response:
                if response.status == 200:
                    content = await response.text()
                    
                    # Extract sitemap URLs
                    for line in content.split('\n'):
                        line = line.strip()
                        if line.lower().startswith('sitemap:'):
                            sitemap_url = line.split(':', 1)[1].strip()
                            sitemap_urls = await self._discover_from_sitemaps(sitemap_url)
                            urls.update(sitemap_urls)
                        
                        # Extract allowed/disallowed paths for pattern discovery
                        elif line.lower().startswith(('allow:', 'disallow:')):
                            path = line.split(':', 1)[1].strip()
                            if path and path != '/' and not path.startswith('*'):
                                full_url = urljoin(base_url, path)
                                if self._is_valid_url(full_url, base_url):
                                    urls.add(full_url)
        
        except Exception as e:
            logger.debug(f"Could not fetch robots.txt: {e}")
        
        return urls
    
    async def _discover_from_homepage(self, base_url: str) -> Set[str]:
        """Deep analysis of homepage to discover URL patterns."""
        urls = set()
        
        try:
            async with self.session.get(base_url) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'lxml')
                    
                    # Extract all links
                    for link in soup.find_all('a', href=True):
                        href = link.get('href')
                        full_url = urljoin(base_url, href)
                        if self._is_valid_url(full_url, base_url):
                            urls.add(full_url)
                    
                    # Look for JavaScript-generated URLs
                    js_urls = self._extract_js_urls(html, base_url)
                    urls.update(js_urls)
                    
                    # Look for form actions
                    for form in soup.find_all('form', action=True):
                        action = form.get('action')
                        if action:
                            form_url = urljoin(base_url, action)
                            if self._is_valid_url(form_url, base_url):
                                urls.add(form_url)
                    
                    # Extract data attributes that might contain URLs
                    for elem in soup.find_all(attrs={"data-url": True}):
                        data_url = elem.get('data-url')
                        if data_url:
                            full_url = urljoin(base_url, data_url)
                            if self._is_valid_url(full_url, base_url):
                                urls.add(full_url)
        
        except Exception as e:
            logger.debug(f"Error analyzing homepage: {e}")
        
        return urls
    
    def _extract_js_urls(self, html: str, base_url: str) -> Set[str]:
        """Extract URLs from JavaScript code."""
        urls = set()
        
        # Common JavaScript URL patterns
        js_patterns = [
            r'["\']([^"\']*(?:jobs|search|category|location)[^"\']*)["\']',
            r'url\s*:\s*["\']([^"\']+)["\']',
            r'href\s*:\s*["\']([^"\']+)["\']',
            r'window\.location\s*=\s*["\']([^"\']+)["\']'
        ]
        
        for pattern in js_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                if match.startswith(('http', '/')):
                    full_url = urljoin(base_url, match)
                    if self._is_valid_url(full_url, base_url):
                        urls.add(full_url)
        
        return urls
    
    async def _generate_pattern_urls(self, base_url: str) -> Set[str]:
        """Generate URLs based on common patterns."""
        urls = set()
        
        # Generate location-based job URLs
        for location in self.locations:
            for pattern in self.job_patterns:
                if "{location}" in pattern:
                    url_path = pattern.format(location=location)
                    full_url = urljoin(base_url, url_path)
                    urls.add(full_url)
        
        # Generate category-based job URLs
        for category in self.categories:
            for pattern in self.job_patterns:
                if "{category}" in pattern:
                    url_path = pattern.format(category=category)
                    full_url = urljoin(base_url, url_path)
                    urls.add(full_url)
        
        # Generate combination URLs (location + category)
        for location in self.locations[:10]:  # Limit combinations
            for category in self.categories[:10]:
                url_path = f"/jobs/{category}/{location}"
                full_url = urljoin(base_url, url_path)
                urls.add(full_url)
                
                # Alternative pattern
                url_path = f"/{category}-jobs-in-{location}"
                full_url = urljoin(base_url, url_path)
                urls.add(full_url)
        
        # Generate search URLs with parameters
        search_params = [
            {"q": "manager"},
            {"q": "analyst"},
            {"q": "advisor"},
            {"location": "london"},
            {"category": "banking"},
            {"type": "permanent"},
            {"level": "senior"}
        ]
        
        for params in search_params:
            query_string = urlencode(params)
            search_url = f"{base_url}/search?{query_string}"
            urls.add(search_url)
            
            # Alternative search paths
            jobs_url = f"{base_url}/jobs?{query_string}"
            urls.add(jobs_url)
        
        return urls
    
    async def _discover_search_urls(self, base_url: str) -> Set[str]:
        """Discover URLs through search functionality."""
        urls = set()
        
        # Try to find search endpoints
        search_endpoints = ["/search", "/jobs", "/find-jobs", "/job-search"]
        
        for endpoint in search_endpoints:
            search_url = urljoin(base_url, endpoint)
            try:
                async with self.session.get(search_url) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'lxml')
                        
                        # Look for search forms
                        for form in soup.find_all('form'):
                            # Extract option values from select elements
                            for select in form.find_all('select'):
                                for option in select.find_all('option', value=True):
                                    value = option.get('value')
                                    if value and value not in ['', '0', 'all']:
                                        # Generate search URL with this parameter
                                        param_name = select.get('name', 'q')
                                        search_params = {param_name: value}
                                        query_string = urlencode(search_params)
                                        param_url = f"{search_url}?{query_string}"
                                        urls.add(param_url)
            
            except Exception as e:
                logger.debug(f"Error discovering search URLs from {search_url}: {e}")
        
        return urls
    
    async def _discover_api_endpoints(self, base_url: str) -> Set[str]:
        """Discover API endpoints that might return job data."""
        urls = set()
        
        # Common API patterns
        api_patterns = [
            "/api/jobs",
            "/api/search",
            "/api/locations",
            "/api/categories",
            "/jobs/api",
            "/search/api",
            "/ajax/jobs",
            "/ajax/search"
        ]
        
        for pattern in api_patterns:
            api_url = urljoin(base_url, pattern)
            try:
                async with self.session.get(api_url) as response:
                    if response.status == 200:
                        content_type = response.headers.get('content-type', '')
                        if 'json' in content_type:
                            # This is likely a valid API endpoint
                            urls.add(api_url)
                            
                            # Try with common parameters
                            for location in self.locations[:5]:
                                param_url = f"{api_url}?location={location}"
                                urls.add(param_url)
                            
                            for category in self.categories[:5]:
                                param_url = f"{api_url}?category={category}"
                                urls.add(param_url)
            
            except Exception as e:
                logger.debug(f"Error checking API endpoint {api_url}: {e}")
        
        return urls
    
    def _is_valid_url(self, url: str, base_url: str) -> bool:
        """Check if URL is valid for crawling."""
        try:
            parsed = urlparse(url)
            base_parsed = urlparse(base_url)
            
            # Must be same domain
            if parsed.netloc.lower() not in [base_parsed.netloc.lower(), 
                                           f"www.{base_parsed.netloc.lower()}",
                                           base_parsed.netloc.lower().replace("www.", "")]:
                return False
            
            # Skip certain file types
            skip_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.zip', 
                             '.jpg', '.jpeg', '.png', '.gif', '.css', '.js']
            if any(url.lower().endswith(ext) for ext in skip_extensions):
                return False
            
            # Skip certain protocols
            if parsed.scheme not in ['http', 'https']:
                return False
            
            # Skip fragments and javascript
            if url.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                return False
            
            return True
            
        except Exception:
            return False
    
    async def discover_from_dynamic_page(self, page: Page, base_url: str) -> Set[str]:
        """Discover URLs from a dynamic page using Playwright."""
        urls = set()
        
        try:
            # Wait for page to load
            await page.wait_for_load_state('networkidle', timeout=10000)
            
            # Extract all links
            links = await page.evaluate("""
                () => {
                    const links = [];
                    document.querySelectorAll('a[href], area[href]').forEach(el => {
                        const href = el.getAttribute('href');
                        if (href) links.push(href);
                    });
                    return links;
                }
            """)
            
            for link in links:
                full_url = urljoin(base_url, link)
                if self._is_valid_url(full_url, base_url):
                    urls.add(full_url)
            
            # Look for data attributes
            data_urls = await page.evaluate("""
                () => {
                    const urls = [];
                    document.querySelectorAll('[data-url], [data-href], [data-link]').forEach(el => {
                        const url = el.getAttribute('data-url') || 
                                   el.getAttribute('data-href') || 
                                   el.getAttribute('data-link');
                        if (url) urls.push(url);
                    });
                    return urls;
                }
            """)
            
            for url in data_urls:
                full_url = urljoin(base_url, url)
                if self._is_valid_url(full_url, base_url):
                    urls.add(full_url)
            
            # Try to trigger dynamic content loading
            await self._trigger_dynamic_content(page, base_url, urls)
            
        except Exception as e:
            logger.debug(f"Error discovering URLs from dynamic page: {e}")
        
        return urls
    
    async def _trigger_dynamic_content(self, page: Page, base_url: str, urls: Set[str]):
        """Trigger dynamic content loading to discover more URLs."""
        try:
            # Try clicking load more buttons
            load_more_selectors = [
                'button:has-text("Load More")',
                'button:has-text("View More")',
                'a:has-text("Load More")',
                '.load-more',
                '.view-more'
            ]
            
            for selector in load_more_selectors:
                try:
                    button = await page.query_selector(selector)
                    if button and await button.is_visible():
                        await button.click()
                        await page.wait_for_timeout(2000)
                        
                        # Extract new links after click
                        new_links = await page.evaluate("""
                            () => {
                                const links = [];
                                document.querySelectorAll('a[href]').forEach(el => {
                                    const href = el.getAttribute('href');
                                    if (href) links.push(href);
                                });
                                return links;
                            }
                        """)
                        
                        for link in new_links:
                            full_url = urljoin(base_url, link)
                            if self._is_valid_url(full_url, base_url):
                                urls.add(full_url)
                        
                        break  # Only click one button to avoid infinite loops
                        
                except Exception:
                    continue
            
            # Try scrolling to trigger infinite scroll
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)
            
            # Extract links after scroll
            scroll_links = await page.evaluate("""
                () => {
                    const links = [];
                    document.querySelectorAll('a[href]').forEach(el => {
                        const href = el.getAttribute('href');
                        if (href) links.push(href);
                    });
                    return links;
                }
            """)
            
            for link in scroll_links:
                full_url = urljoin(base_url, link)
                if self._is_valid_url(full_url, base_url):
                    urls.add(full_url)
        
        except Exception as e:
            logger.debug(f"Error triggering dynamic content: {e}")
