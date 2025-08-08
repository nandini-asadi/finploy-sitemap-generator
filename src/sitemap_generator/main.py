"""Main CLI entry point for the Finploy sitemap generator."""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Optional
import click
from .config import get_config_from_env, DEFAULT_BASE_URLS
from .crawler import run_crawler
from .types import CrawlConfig
from .utils import setup_logging, format_duration, format_number

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@click.command()
@click.option(
    '--base-urls',
    default=','.join(DEFAULT_BASE_URLS),
    help='Comma-separated list of base URLs to crawl',
    show_default=True
)
@click.option(
    '--max-depth',
    default=5,
    type=int,
    help='Maximum crawl depth',
    show_default=True
)
@click.option(
    '--max-concurrent',
    default=10,
    type=int,
    help='Maximum concurrent requests',
    show_default=True
)
@click.option(
    '--crawl-delay',
    default=1.0,
    type=float,
    help='Delay between requests in seconds',
    show_default=True
)
@click.option(
    '--timeout',
    default=30,
    type=int,
    help='Request timeout in seconds',
    show_default=True
)
@click.option(
    '--output-dir',
    default='data/sitemap/',
    help='Output directory for sitemaps',
    show_default=True
)
@click.option(
    '--database-path',
    default='data/urls.db',
    help='SQLite database path',
    show_default=True
)
@click.option(
    '--log-level',
    default='INFO',
    type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
    help='Logging level',
    show_default=True
)
@click.option(
    '--log-file',
    help='Log file path (optional)',
    type=click.Path()
)
@click.option(
    '--clean',
    is_flag=True,
    help='Clean database before starting'
)
@click.option(
    '--disable-dynamic',
    is_flag=True,
    help='Disable dynamic content crawling'
)
@click.option(
    '--disable-robots',
    is_flag=True,
    help='Disable robots.txt checking'
)
@click.option(
    '--export-debug',
    help='Export debug information to file',
    type=click.Path()
)
@click.option(
    '--validate-only',
    is_flag=True,
    help='Only validate existing sitemaps'
)
def main(
    base_urls: str,
    max_depth: int,
    max_concurrent: int,
    crawl_delay: float,
    timeout: int,
    output_dir: str,
    database_path: str,
    log_level: str,
    log_file: Optional[str],
    clean: bool,
    disable_dynamic: bool,
    disable_robots: bool,
    export_debug: Optional[str],
    validate_only: bool
) -> None:
    """
    Finploy Sitemap Generator - Generate comprehensive sitemaps for Finploy websites.
    
    This tool crawls https://www.finploy.com and https://finploy.co.uk to discover
    all URLs including dynamic content behind "View More" buttons and generates
    XML sitemaps compliant with sitemaps.org standards.
    """
    # Set up logging
    setup_logging(log_level, log_file)
    logger = logging.getLogger(__name__)
    
    # Print banner
    print_banner()
    
    try:
        # Parse base URLs
        base_url_list = [url.strip() for url in base_urls.split(',') if url.strip()]
        
        if not base_url_list:
            click.echo("Error: No base URLs provided", err=True)
            sys.exit(1)
        
        # Create configuration
        config = CrawlConfig(
            base_urls=base_url_list,
            max_depth=max_depth,
            max_concurrent_requests=max_concurrent,
            crawl_delay=crawl_delay,
            request_timeout=timeout,
            database_path=database_path,
            sitemap_output_dir=output_dir,
            respect_robots_txt=not disable_robots,
            enable_dynamic_crawling=not disable_dynamic
        )
        
        # Validate configuration
        validate_config(config)
        
        # Print configuration
        print_config(config)
        
        if validate_only:
            # Only validate existing sitemaps
            validate_existing_sitemaps(config.sitemap_output_dir)
            return
        
        # Clean database if requested
        if clean:
            clean_database(config.database_path)
        
        # Run crawler
        logger.info("Starting Finploy sitemap generation...")
        statistics = asyncio.run(run_crawler(config))
        
        # Export debug information if requested
        if export_debug:
            async def export_debug_info():
                from .url_manager import URLManager
                url_manager = URLManager(config.database_path)
                await url_manager.initialize()
                await url_manager.export_urls_to_file(export_debug)
                await url_manager.close()
                logger.info(f"Debug information exported to {export_debug}")
            
            asyncio.run(export_debug_info())
        
        # Print final summary
        print_final_summary(statistics, config.sitemap_output_dir)
        
        logger.info("Sitemap generation completed successfully!")
        
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        sys.exit(130)  # Standard exit code for SIGINT
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        if log_level == 'DEBUG':
            import traceback
            traceback.print_exc()
        sys.exit(1)


def print_banner() -> None:
    """Print application banner."""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                 FINPLOY SITEMAP GENERATOR                    ║
║                                                              ║
║  Production-ready sitemap generator for Finploy websites    ║
║  Handles static & dynamic content with full URL discovery   ║
╚══════════════════════════════════════════════════════════════╝
    """
    click.echo(banner)


def print_config(config: CrawlConfig) -> None:
    """Print current configuration."""
    click.echo("\nConfiguration:")
    click.echo(f"  Base URLs: {', '.join(config.base_urls)}")
    click.echo(f"  Max depth: {config.max_depth}")
    click.echo(f"  Max concurrent: {config.max_concurrent_requests}")
    click.echo(f"  Crawl delay: {config.crawl_delay}s")
    click.echo(f"  Request timeout: {config.request_timeout}s")
    click.echo(f"  Output directory: {config.sitemap_output_dir}")
    click.echo(f"  Database path: {config.database_path}")
    click.echo(f"  Dynamic crawling: {'Enabled' if config.enable_dynamic_crawling else 'Disabled'}")
    click.echo(f"  Robots.txt respect: {'Enabled' if config.respect_robots_txt else 'Disabled'}")
    click.echo()


def validate_config(config: CrawlConfig) -> None:
    """Validate configuration parameters."""
    # Validate URLs
    for url in config.base_urls:
        if not url.startswith(('http://', 'https://')):
            raise ValueError(f"Invalid URL format: {url}")
    
    # Validate numeric parameters
    if config.max_depth < 1:
        raise ValueError("Max depth must be at least 1")
    
    if config.max_concurrent_requests < 1:
        raise ValueError("Max concurrent requests must be at least 1")
    
    if config.crawl_delay < 0:
        raise ValueError("Crawl delay cannot be negative")
    
    if config.request_timeout < 1:
        raise ValueError("Request timeout must be at least 1 second")
    
    # Create directories if they don't exist
    os.makedirs(os.path.dirname(config.database_path), exist_ok=True)
    os.makedirs(config.sitemap_output_dir, exist_ok=True)


def clean_database(database_path: str) -> None:
    """Clean the database file."""
    if os.path.exists(database_path):
        os.remove(database_path)
        click.echo(f"Cleaned database: {database_path}")
    else:
        click.echo("Database file does not exist, nothing to clean")


def validate_existing_sitemaps(output_dir: str) -> None:
    """Validate existing sitemap files."""
    from .sitemap_writer import SitemapWriter
    
    if not os.path.exists(output_dir):
        click.echo(f"Output directory does not exist: {output_dir}")
        return
    
    writer = SitemapWriter(output_dir)
    sitemap_files = []
    
    # Find sitemap files
    for filename in os.listdir(output_dir):
        if filename.endswith('.xml') and 'sitemap' in filename.lower():
            filepath = os.path.join(output_dir, filename)
            sitemap_files.append(filepath)
    
    if not sitemap_files:
        click.echo("No sitemap files found to validate")
        return
    
    click.echo(f"Validating {len(sitemap_files)} sitemap files...")
    
    valid_count = 0
    for filepath in sitemap_files:
        if writer.validate_sitemap(filepath):
            stats = writer.get_sitemap_stats(filepath)
            click.echo(f"✓ {os.path.basename(filepath)}: {format_number(stats['total_urls'])} URLs")
            valid_count += 1
        else:
            click.echo(f"✗ {os.path.basename(filepath)}: INVALID")
    
    click.echo(f"\nValidation complete: {valid_count}/{len(sitemap_files)} files valid")


def print_final_summary(statistics, output_dir: str) -> None:
    """Print final summary of the crawling process."""
    click.echo("\n" + "="*70)
    click.echo("SITEMAP GENERATION SUMMARY")
    click.echo("="*70)
    
    click.echo(f"URLs discovered: {format_number(statistics.total_urls_discovered)}")
    click.echo(f"URLs crawled: {format_number(statistics.total_urls_crawled)}")
    click.echo(f"Successful crawls: {format_number(statistics.successful_crawls)}")
    click.echo(f"Success rate: {statistics.success_rate:.1f}%")
    
    if statistics.start_time and statistics.end_time:
        duration = format_duration(statistics.duration_seconds)
        click.echo(f"Total duration: {duration}")
    
    # List generated files
    if os.path.exists(output_dir):
        sitemap_files = [f for f in os.listdir(output_dir) if f.endswith('.xml')]
        if sitemap_files:
            click.echo(f"\nGenerated files in {output_dir}:")
            for filename in sorted(sitemap_files):
                filepath = os.path.join(output_dir, filename)
                size_mb = os.path.getsize(filepath) / (1024 * 1024)
                click.echo(f"  • {filename} ({size_mb:.2f} MB)")
        
        # Check for robots.txt
        robots_file = os.path.join(output_dir, "robots.txt")
        if os.path.exists(robots_file):
            click.echo(f"  • robots.txt")
    
    click.echo("\n" + "="*70)
    click.echo("Sitemap generation completed successfully!")
    click.echo("="*70)


def check_dependencies() -> None:
    """Check if all required dependencies are available."""
    missing_deps = []
    
    try:
        import aiohttp
    except ImportError:
        missing_deps.append('aiohttp')
    
    try:
        import playwright
    except ImportError:
        missing_deps.append('playwright')
    
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        missing_deps.append('beautifulsoup4')
    
    try:
        from lxml import etree
    except ImportError:
        missing_deps.append('lxml')
    
    try:
        import aiosqlite
    except ImportError:
        missing_deps.append('aiosqlite')
    
    if missing_deps:
        click.echo(f"Error: Missing required dependencies: {', '.join(missing_deps)}")
        click.echo("Please install them using: pip install " + ' '.join(missing_deps))
        sys.exit(1)


def install_playwright_browsers() -> None:
    """Install Playwright browsers if needed."""
    try:
        import subprocess
        result = subprocess.run(['playwright', 'install', 'chromium'], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            click.echo("Warning: Could not install Playwright browsers automatically")
            click.echo("Please run: playwright install chromium")
    except Exception:
        click.echo("Warning: Could not check Playwright browser installation")


if __name__ == '__main__':
    # Check dependencies before starting
    check_dependencies()
    
    # Install Playwright browsers if needed
    install_playwright_browsers()
    
    # Run main CLI
    main()
