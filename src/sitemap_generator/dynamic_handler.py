"""Dynamic content handler using Playwright for JavaScript-heavy pages."""

import asyncio
import logging
import time
from typing import List, Optional, Set
from urllib.parse import urljoin
from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
from .types import CrawlResult
from .config import PLAYWRIGHT_CONFIG, DYNAMIC_CONTENT_SELECTORS, is_target_domain, should_skip_url
from .utils import normalize_url, deduplicate_urls

logger = logging.getLogger(__name__)


class DynamicHandler:
    """Handles dynamic content crawling using Playwright."""
    
    def __init__(self, user_agent: str):
        self.user_agent = user_agent
        self.playwright = None
        self.browser: Optional[Browser] = None
        self._browser_lock = asyncio.Lock()
    
    async def initialize(self) -> None:
        """Initialize Playwright browser."""
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=PLAYWRIGHT_CONFIG["headless"],
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding'
                ]
            )
            logger.info("Playwright browser initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Playwright: {e}")
            raise
    
    async def crawl_dynamic_url(self, url: str, depth: int) -> CrawlResult:
        """
        Crawl a URL that contains dynamic content.
        
        Args:
            url: URL to crawl
            depth: Current crawl depth
            
        Returns:
            CrawlResult with discovered URLs and metadata
        """
        if not self.browser:
            await self.initialize()
        
        start_time = time.time()
        page: Optional[Page] = None
        
        try:
            async with self._browser_lock:
                page = await self.browser.new_page(
                    viewport=PLAYWRIGHT_CONFIG["viewport"],
                    user_agent=self.user_agent
                )
            
            # Navigate to page with timeout
            try:
                response = await page.goto(
                    url,
                    wait_until=PLAYWRIGHT_CONFIG["wait_for_load_state"],
                    timeout=PLAYWRIGHT_CONFIG["timeout"]
                )
                
                if not response:
                    return CrawlResult(
                        url=url,
                        status_code=0,
                        discovered_urls=[],
                        error="No response received"
                    )
                
                status_code = response.status
                
            except PlaywrightTimeoutError:
                logger.warning(f"Timeout loading {url}, trying with basic wait")
                try:
                    response = await page.goto(url, timeout=15000)
                    status_code = response.status if response else 0
                except Exception:
                    return CrawlResult(
                        url=url,
                        status_code=0,
                        discovered_urls=[],
                        error="Failed to load page"
                    )
            
            # Wait for initial content to load
            await asyncio.sleep(2)
            
            # Handle dynamic content loading
            discovered_urls = await self._handle_dynamic_content(page, url)
            
            response_time = time.time() - start_time
            
            logger.debug(
                f"Dynamic crawl {url} -> {status_code} ({len(discovered_urls)} links, "
                f"{response_time:.2f}s)"
            )
            
            return CrawlResult(
                url=url,
                status_code=status_code,
                discovered_urls=discovered_urls,
                is_dynamic_content=True,
                response_time=response_time
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            logger.error(f"Error in dynamic crawl of {url}: {e}")
            return CrawlResult(
                url=url,
                status_code=0,
                discovered_urls=[],
                error=str(e),
                is_dynamic_content=True,
                response_time=response_time
            )
        
        finally:
            if page:
                try:
                    await page.close()
                except Exception as e:
                    logger.debug(f"Error closing page: {e}")
    
    async def _handle_dynamic_content(self, page: Page, base_url: str) -> List[str]:
        """Handle various types of dynamic content on the page."""
        all_urls: Set[str] = set()
        
        try:
            # Extract initial links
            initial_urls = await self._extract_links_from_page(page, base_url)
            all_urls.update(initial_urls)
            
            # Handle "View More" / "Load More" buttons
            view_more_urls = await self._handle_view_more_buttons(page, base_url)
            all_urls.update(view_more_urls)
            
            # Handle pagination
            pagination_urls = await self._handle_pagination(page, base_url)
            all_urls.update(pagination_urls)
            
            # Handle job filter forms
            filter_urls = await self._handle_job_filters(page, base_url)
            all_urls.update(filter_urls)
            
            # Handle infinite scroll
            scroll_urls = await self._handle_infinite_scroll(page, base_url)
            all_urls.update(scroll_urls)
            
            # Final extraction after all interactions
            final_urls = await self._extract_links_from_page(page, base_url)
            all_urls.update(final_urls)
            
        except Exception as e:
            logger.error(f"Error handling dynamic content for {base_url}: {e}")
        
        # Filter and normalize URLs
        valid_urls = []
        for url in all_urls:
            normalized_url = normalize_url(url, base_url)
            
            if (is_target_domain(normalized_url) and 
                not should_skip_url(normalized_url) and
                normalized_url != normalize_url(base_url)):
                valid_urls.append(normalized_url)
        
        return deduplicate_urls(valid_urls)
    
    async def _extract_links_from_page(self, page: Page, base_url: str) -> List[str]:
        """Extract all links from current page state."""
        try:
            # Get all links using JavaScript for better performance
            links = await page.evaluate("""
                () => {
                    const links = [];
                    const elements = document.querySelectorAll('a[href], area[href]');
                    elements.forEach(el => {
                        const href = el.getAttribute('href');
                        if (href && !href.startsWith('#') && !href.startsWith('javascript:') && 
                            !href.startsWith('mailto:') && !href.startsWith('tel:')) {
                            links.push(href);
                        }
                    });
                    return links;
                }
            """)
            
            # Convert relative URLs to absolute
            absolute_urls = []
            for link in links:
                absolute_url = urljoin(base_url, link)
                absolute_urls.append(absolute_url)
            
            return absolute_urls
            
        except Exception as e:
            logger.debug(f"Error extracting links from page: {e}")
            return []
    
    async def _handle_view_more_buttons(self, page: Page, base_url: str) -> List[str]:
        """Handle 'View More' and 'Load More' buttons."""
        discovered_urls: Set[str] = set()
        max_clicks = 10  # Prevent infinite loops
        clicks = 0
        
        try:
            while clicks < max_clicks:
                # Look for view more buttons
                view_more_found = False
                
                for selector in DYNAMIC_CONTENT_SELECTORS["view_more_buttons"]:
                    try:
                        # Check if button exists and is visible
                        button = await page.query_selector(selector)
                        if button:
                            is_visible = await button.is_visible()
                            if is_visible:
                                logger.debug(f"Clicking view more button: {selector}")
                                
                                # Get URLs before click
                                urls_before = set(await self._extract_links_from_page(page, base_url))
                                
                                # Click button
                                await button.click()
                                view_more_found = True
                                
                                # Wait for content to load
                                await asyncio.sleep(3)
                                
                                # Get URLs after click
                                urls_after = set(await self._extract_links_from_page(page, base_url))
                                
                                # Add new URLs
                                new_urls = urls_after - urls_before
                                discovered_urls.update(new_urls)
                                
                                logger.debug(f"Found {len(new_urls)} new URLs after clicking")
                                break
                                
                    except Exception as e:
                        logger.debug(f"Error with selector {selector}: {e}")
                        continue
                
                if not view_more_found:
                    break
                
                clicks += 1
                
        except Exception as e:
            logger.debug(f"Error handling view more buttons: {e}")
        
        return list(discovered_urls)
    
    async def _handle_pagination(self, page: Page, base_url: str) -> List[str]:
        """Handle pagination controls."""
        pagination_urls: Set[str] = set()
        
        try:
            for selector in DYNAMIC_CONTENT_SELECTORS["pagination"]:
                try:
                    pagination_links = await page.query_selector_all(selector)
                    
                    for link in pagination_links:
                        href = await link.get_attribute('href')
                        if href:
                            absolute_url = urljoin(base_url, href)
                            pagination_urls.add(absolute_url)
                            
                except Exception as e:
                    logger.debug(f"Error with pagination selector {selector}: {e}")
                    continue
            
            # Also look for numbered pagination
            numbered_links = await page.evaluate("""
                () => {
                    const links = [];
                    const elements = document.querySelectorAll('a[href]');
                    elements.forEach(el => {
                        const text = el.textContent.trim();
                        const href = el.getAttribute('href');
                        // Look for numeric pagination or next/prev
                        if (href && (/^\\d+$/.test(text) || 
                            ['next', 'previous', 'prev', '→', '←', '»', '«'].includes(text.toLowerCase()))) {
                            links.push(href);
                        }
                    });
                    return links;
                }
            """)
            
            for link in numbered_links:
                absolute_url = urljoin(base_url, link)
                pagination_urls.add(absolute_url)
                
        except Exception as e:
            logger.debug(f"Error handling pagination: {e}")
        
        return list(pagination_urls)
    
    async def _handle_job_filters(self, page: Page, base_url: str) -> List[str]:
        """Handle job filter forms and dropdowns."""
        filter_urls: Set[str] = set()
        
        try:
            # Look for location and category filters
            location_options = await page.evaluate("""
                () => {
                    const urls = [];
                    const selects = document.querySelectorAll('select[name*="location"], select[name*="city"], select[name*="area"]');
                    selects.forEach(select => {
                        const options = select.querySelectorAll('option[value]');
                        options.forEach(option => {
                            const value = option.getAttribute('value');
                            if (value && value !== '' && value !== '0') {
                                // Try to construct job URLs
                                if (value.includes('-')) {
                                    urls.push('/jobs-in-' + value);
                                    urls.push('/' + value + '-jobs');
                                }
                            }
                        });
                    });
                    return urls;
                }
            """)
            
            for url_path in location_options:
                absolute_url = urljoin(base_url, url_path)
                filter_urls.add(absolute_url)
            
            # Look for category filters
            category_options = await page.evaluate("""
                () => {
                    const urls = [];
                    const selects = document.querySelectorAll('select[name*="category"], select[name*="sector"], select[name*="industry"]');
                    selects.forEach(select => {
                        const options = select.querySelectorAll('option[value]');
                        options.forEach(option => {
                            const value = option.getAttribute('value');
                            if (value && value !== '' && value !== '0') {
                                urls.push('/' + value + '-jobs');
                            }
                        });
                    });
                    return urls;
                }
            """)
            
            for url_path in category_options:
                absolute_url = urljoin(base_url, url_path)
                filter_urls.add(absolute_url)
                
        except Exception as e:
            logger.debug(f"Error handling job filters: {e}")
        
        return list(filter_urls)
    
    async def _handle_infinite_scroll(self, page: Page, base_url: str) -> List[str]:
        """Handle infinite scroll to load more content."""
        discovered_urls: Set[str] = set()
        max_scrolls = 5
        scrolls = 0
        
        try:
            while scrolls < max_scrolls:
                # Get URLs before scroll
                urls_before = set(await self._extract_links_from_page(page, base_url))
                
                # Scroll to bottom
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                
                # Wait for potential content loading
                await asyncio.sleep(3)
                
                # Get URLs after scroll
                urls_after = set(await self._extract_links_from_page(page, base_url))
                
                # Check if new content was loaded
                new_urls = urls_after - urls_before
                if not new_urls:
                    break  # No new content loaded
                
                discovered_urls.update(new_urls)
                logger.debug(f"Infinite scroll found {len(new_urls)} new URLs")
                
                scrolls += 1
                
        except Exception as e:
            logger.debug(f"Error handling infinite scroll: {e}")
        
        return list(discovered_urls)
    
    async def close(self) -> None:
        """Close browser and cleanup resources."""
        try:
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            logger.info("Playwright browser closed")
        except Exception as e:
            logger.error(f"Error closing Playwright: {e}")
    
    async def get_page_screenshot(self, url: str, output_path: str) -> bool:
        """Take screenshot of page for debugging (optional)."""
        if not self.browser:
            await self.initialize()
        
        page = None
        try:
            page = await self.browser.new_page()
            await page.goto(url, timeout=30000)
            await page.screenshot(path=output_path, full_page=True)
            logger.info(f"Screenshot saved: {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error taking screenshot of {url}: {e}")
            return False
        finally:
            if page:
                await page.close()
    
    async def extract_page_content(self, url: str) -> Optional[str]:
        """Extract text content from page for analysis."""
        if not self.browser:
            await self.initialize()
        
        page = None
        try:
            page = await self.browser.new_page()
            await page.goto(url, timeout=30000)
            
            # Extract main content
            content = await page.evaluate("""
                () => {
                    // Remove script and style elements
                    const scripts = document.querySelectorAll('script, style');
                    scripts.forEach(el => el.remove());
                    
                    // Get main content areas
                    const main = document.querySelector('main, .main, #main, .content, #content');
                    if (main) {
                        return main.textContent.trim();
                    }
                    
                    // Fallback to body
                    return document.body.textContent.trim();
                }
            """)
            
            return content
            
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {e}")
            return None
        finally:
            if page:
                await page.close()
