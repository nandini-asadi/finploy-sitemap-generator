"""Main crawler orchestrator that coordinates all crawling components."""

import asyncio
import logging
import signal
import time
from datetime import datetime
from typing import List, Optional
import aiohttp
from tqdm.asyncio import tqdm
from .types import CrawlConfig, CrawlResult, CrawlStatistics
from .url_manager import URLManager
from .static_crawler import StaticCrawler, create_crawler_session
from .dynamic_handler import DynamicHandler
from .sitemap_writer import SitemapWriter
from .config import is_dynamic_url, is_target_domain, should_skip_url
from .utils import RateLimiter, RobotsChecker, format_duration, format_number

logger = logging.getLogger(__name__)


class SitemapCrawler:
    """Main crawler that orchestrates the entire sitemap generation process."""
    
    def __init__(self, config: CrawlConfig):
        self.config = config
        self.url_manager: Optional[URLManager] = None
        self.static_crawler: Optional[StaticCrawler] = None
        self.dynamic_handler: Optional[DynamicHandler] = None
        self.sitemap_writer: Optional[SitemapWriter] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.statistics = CrawlStatistics()
        self._shutdown_requested = False
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self._shutdown_requested = True
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def initialize(self) -> None:
        """Initialize all crawler components."""
        logger.info("Initializing crawler components...")
        
        # Initialize URL manager
        self.url_manager = URLManager(self.config.database_path)
        await self.url_manager.initialize()
        await self.url_manager.clear_processing_flags()  # Recovery from crashes
        
        # Initialize HTTP session
        self.session = await create_crawler_session(
            timeout=self.config.request_timeout,
            max_connections=self.config.max_concurrent_requests * 2,
            user_agent=self.config.user_agent
        )
        
        # Initialize rate limiter and robots checker
        rate_limiter = RateLimiter(self.config.crawl_delay)
        robots_checker = RobotsChecker(self.config.user_agent) if self.config.respect_robots_txt else None
        
        # Initialize static crawler
        self.static_crawler = StaticCrawler(
            session=self.session,
            rate_limiter=rate_limiter,
            robots_checker=robots_checker,
            respect_robots=self.config.respect_robots_txt
        )
        
        # Initialize dynamic handler if enabled
        if self.config.enable_dynamic_crawling:
            self.dynamic_handler = DynamicHandler(self.config.user_agent)
            await self.dynamic_handler.initialize()
        
        # Initialize sitemap writer
        self.sitemap_writer = SitemapWriter(
            output_dir=self.config.sitemap_output_dir,
            max_urls_per_sitemap=self.config.max_urls_per_sitemap
        )
        
        logger.info("Crawler initialization completed")
    
    async def crawl_websites(self) -> CrawlStatistics:
        """
        Main crawling process.
        
        Returns:
            CrawlStatistics with crawling results
        """
        self.statistics.start_time = datetime.utcnow()
        
        try:
            # Add base URLs to crawl queue
            await self._add_base_urls()
            
            # Main crawling loop
            await self._crawl_loop()
            
            # Generate sitemaps
            await self._generate_sitemaps()
            
        except Exception as e:
            logger.error(f"Error in crawling process: {e}")
            raise
        finally:
            self.statistics.end_time = datetime.utcnow()
            await self._update_final_statistics()
        
        return self.statistics
    
    async def _add_base_urls(self) -> None:
        """Add base URLs to the crawl queue."""
        logger.info(f"Adding {len(self.config.base_urls)} base URLs to crawl queue")
        
        for base_url in self.config.base_urls:
            await self.url_manager.add_url(
                url=base_url,
                depth=0,
                is_dynamic=False,
                priority=100  # Highest priority for base URLs
            )
        
        initial_stats = await self.url_manager.get_statistics()
        logger.info(f"Initial queue size: {format_number(initial_stats.total_urls_discovered)}")
    
    async def _crawl_loop(self) -> None:
        """Main crawling loop that processes URLs until queue is empty or max depth reached."""
        current_depth = 0
        
        while current_depth <= self.config.max_depth and not self._shutdown_requested:
            queue_size = await self.url_manager.get_queue_size()
            
            if queue_size == 0:
                logger.info("Crawl queue is empty, crawling completed")
                break
            
            logger.info(
                f"Starting crawl at depth {current_depth}, "
                f"queue size: {format_number(queue_size)}"
            )
            
            # Process URLs in batches
            batch_size = min(self.config.max_concurrent_requests, queue_size)
            processed_in_depth = 0
            
            while queue_size > 0 and not self._shutdown_requested:
                # Get next batch of URLs
                urls_to_crawl = await self.url_manager.get_next_urls_to_crawl(batch_size)
                
                if not urls_to_crawl:
                    break
                
                # Crawl batch
                await self._crawl_batch(urls_to_crawl, current_depth)
                
                processed_in_depth += len(urls_to_crawl)
                queue_size = await self.url_manager.get_queue_size()
                
                # Progress update
                if processed_in_depth % 100 == 0:
                    stats = await self.url_manager.get_statistics()
                    logger.info(
                        f"Depth {current_depth}: Processed {format_number(processed_in_depth)}, "
                        f"Queue: {format_number(queue_size)}, "
                        f"Success rate: {stats.success_rate:.1f}%"
                    )
            
            logger.info(
                f"Completed depth {current_depth}, "
                f"processed {format_number(processed_in_depth)} URLs"
            )
            
            current_depth += 1
    
    async def _crawl_batch(self, urls: List[str], depth: int) -> None:
        """Crawl a batch of URLs concurrently."""
        if not urls:
            return
        
        # Separate URLs by crawling method
        static_urls = []
        dynamic_urls = []
        
        for url in urls:
            if self.config.enable_dynamic_crawling and is_dynamic_url(url):
                dynamic_urls.append(url)
            else:
                static_urls.append(url)
        
        # Create crawling tasks
        tasks = []
        
        # Static crawling tasks
        if static_urls:
            static_tasks = [
                self._crawl_static_url(url, depth) 
                for url in static_urls
            ]
            tasks.extend(static_tasks)
        
        # Dynamic crawling tasks (limited concurrency)
        if dynamic_urls and self.dynamic_handler:
            # Limit dynamic crawling concurrency to prevent resource exhaustion
            dynamic_semaphore = asyncio.Semaphore(min(3, len(dynamic_urls)))
            dynamic_tasks = [
                self._crawl_dynamic_url_with_semaphore(url, depth, dynamic_semaphore)
                for url in dynamic_urls
            ]
            tasks.extend(dynamic_tasks)
        
        # Execute all tasks with progress bar
        if tasks:
            results = []
            with tqdm(total=len(tasks), desc=f"Crawling depth {depth}", unit="url") as pbar:
                for coro in asyncio.as_completed(tasks):
                    try:
                        result = await coro
                        results.append(result)
                        pbar.update(1)
                    except Exception as e:
                        logger.error(f"Error in batch crawling task: {e}")
                        pbar.update(1)
            
            # Process results
            await self._process_crawl_results(results, depth)
    
    async def _crawl_static_url(self, url: str, depth: int) -> CrawlResult:
        """Crawl a single static URL."""
        try:
            return await self.static_crawler.crawl_url(url, depth)
        except Exception as e:
            logger.error(f"Error crawling static URL {url}: {e}")
            return CrawlResult(
                url=url,
                status_code=0,
                discovered_urls=[],
                error=str(e)
            )
    
    async def _crawl_dynamic_url_with_semaphore(
        self, 
        url: str, 
        depth: int, 
        semaphore: asyncio.Semaphore
    ) -> CrawlResult:
        """Crawl a dynamic URL with semaphore for concurrency control."""
        async with semaphore:
            try:
                return await self.dynamic_handler.crawl_dynamic_url(url, depth)
            except Exception as e:
                logger.error(f"Error crawling dynamic URL {url}: {e}")
                return CrawlResult(
                    url=url,
                    status_code=0,
                    discovered_urls=[],
                    error=str(e),
                    is_dynamic_content=True
                )
    
    async def _process_crawl_results(self, results: List[CrawlResult], depth: int) -> None:
        """Process crawl results and update URL manager."""
        new_urls_batch = []
        
        for result in results:
            # Mark URL as crawled
            await self.url_manager.mark_crawled(
                url=result.url,
                status_code=result.status_code,
                content_type=result.content_type,
                error_message=result.error,
                response_time=result.response_time
            )
            
            # Update statistics
            if result.error:
                self.statistics.failed_crawls += 1
            elif 200 <= result.status_code < 400:
                self.statistics.successful_crawls += 1
                if result.is_dynamic_content:
                    self.statistics.dynamic_pages_crawled += 1
                else:
                    self.statistics.static_pages_crawled += 1
            else:
                self.statistics.failed_crawls += 1
            
            self.statistics.total_urls_crawled += 1
            
            # Process discovered URLs
            if result.discovered_urls and depth < self.config.max_depth:
                for discovered_url in result.discovered_urls:
                    # Skip if not target domain or should be skipped
                    if not is_target_domain(discovered_url) or should_skip_url(discovered_url):
                        continue
                    
                    # Determine if URL is dynamic
                    is_dynamic = is_dynamic_url(discovered_url)
                    
                    # Calculate priority (higher for lower depth)
                    priority = max(0, 100 - depth * 10)
                    
                    new_urls_batch.append((
                        discovered_url,
                        result.url,  # parent_url
                        depth + 1,
                        is_dynamic,
                        priority
                    ))
        
        # Add new URLs in batch
        if new_urls_batch:
            added_count = await self.url_manager.add_urls_batch(new_urls_batch)
            self.statistics.total_urls_discovered += added_count
            
            if added_count > 0:
                logger.debug(f"Added {format_number(added_count)} new URLs from batch results")
    
    async def _generate_sitemaps(self) -> None:
        """Generate sitemap files from crawled URLs."""
        logger.info("Generating sitemaps...")
        
        # Get all valid URLs
        valid_urls = await self.url_manager.get_all_valid_urls()
        
        if not valid_urls:
            logger.warning("No valid URLs found for sitemap generation")
            return
        
        logger.info(f"Generating sitemaps for {format_number(len(valid_urls))} valid URLs")
        
        # Generate sitemaps
        sitemap_files = self.sitemap_writer.generate_sitemaps(
            urls=valid_urls,
            base_url=self.config.base_urls[0]  # Use first base URL
        )
        
        # Validate generated sitemaps
        for sitemap_file in sitemap_files:
            if self.sitemap_writer.validate_sitemap(sitemap_file):
                stats = self.sitemap_writer.get_sitemap_stats(sitemap_file)
                logger.info(
                    f"Sitemap {sitemap_file}: {format_number(stats['total_urls'])} URLs, "
                    f"{stats['file_size_mb']:.2f} MB"
                )
        
        # Generate robots.txt
        robots_file = self.sitemap_writer.generate_robots_txt(
            base_url=self.config.base_urls[0],
            sitemap_files=sitemap_files
        )
        
        logger.info(f"Sitemap generation completed: {len(sitemap_files)} files")
    
    async def _update_final_statistics(self) -> None:
        """Update final statistics from URL manager."""
        db_stats = await self.url_manager.get_statistics()
        
        # Update statistics with database values (more accurate)
        self.statistics.total_urls_discovered = db_stats.total_urls_discovered
        self.statistics.total_urls_crawled = db_stats.total_urls_crawled
        self.statistics.successful_crawls = db_stats.successful_crawls
        self.statistics.failed_crawls = db_stats.failed_crawls
        self.statistics.skipped_urls = db_stats.skipped_urls
        self.statistics.dynamic_pages_crawled = db_stats.dynamic_pages_crawled
        self.statistics.static_pages_crawled = db_stats.static_pages_crawled
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        logger.info("Cleaning up crawler resources...")
        
        try:
            if self.dynamic_handler:
                await self.dynamic_handler.close()
            
            if self.session:
                await self.session.close()
            
            if self.url_manager:
                await self.url_manager.close()
            
            logger.info("Crawler cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def print_statistics(self) -> None:
        """Print crawling statistics."""
        print("\n" + "="*60)
        print("CRAWLING STATISTICS")
        print("="*60)
        
        print(f"Total URLs discovered: {format_number(self.statistics.total_urls_discovered)}")
        print(f"Total URLs crawled: {format_number(self.statistics.total_urls_crawled)}")
        print(f"Successful crawls: {format_number(self.statistics.successful_crawls)}")
        print(f"Failed crawls: {format_number(self.statistics.failed_crawls)}")
        print(f"Skipped URLs: {format_number(self.statistics.skipped_urls)}")
        print(f"Success rate: {self.statistics.success_rate:.1f}%")
        
        print(f"\nCrawling method breakdown:")
        print(f"Static pages: {format_number(self.statistics.static_pages_crawled)}")
        print(f"Dynamic pages: {format_number(self.statistics.dynamic_pages_crawled)}")
        
        if self.statistics.start_time and self.statistics.end_time:
            duration = format_duration(self.statistics.duration_seconds)
            print(f"\nCrawling duration: {duration}")
            
            if self.statistics.duration_seconds > 0:
                rate = self.statistics.total_urls_crawled / self.statistics.duration_seconds
                print(f"Average crawling rate: {rate:.1f} URLs/second")
        
        print("="*60)
    
    async def export_debug_info(self, output_file: str) -> None:
        """Export debug information for analysis."""
        if self.url_manager:
            await self.url_manager.export_urls_to_file(output_file)
            logger.info(f"Debug information exported to {output_file}")


async def run_crawler(config: CrawlConfig) -> CrawlStatistics:
    """
    Run the complete crawling process.
    
    Args:
        config: Crawling configuration
        
    Returns:
        CrawlStatistics with results
    """
    crawler = SitemapCrawler(config)
    
    try:
        await crawler.initialize()
        statistics = await crawler.crawl_websites()
        crawler.print_statistics()
        return statistics
        
    except KeyboardInterrupt:
        logger.info("Crawling interrupted by user")
        return crawler.statistics
        
    except Exception as e:
        logger.error(f"Crawling failed: {e}")
        raise
        
    finally:
        await crawler.cleanup()
