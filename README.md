# Finploy Sitemap Generator

A production-ready, comprehensive sitemap generator specifically designed for Finploy websites. This tool crawls both static and dynamic content to create complete XML sitemaps that comply with sitemaps.org standards.

## 🚀 Features

- **Comprehensive Crawling**: Handles both static pages and JavaScript-heavy dynamic content
- **Dynamic Content Support**: Discovers URLs behind "View More" buttons, pagination, and AJAX loading
- **High Performance**: Asynchronous crawling with configurable concurrency and rate limiting
- **Smart URL Discovery**: Extracts job filter URLs, location-based pages, and category combinations
- **Robust Architecture**: SQLite database for URL management, deduplication, and crash recovery
- **Standards Compliant**: Generates XML sitemaps following sitemaps.org specifications
- **Scalable**: Automatically splits large sitemaps and creates sitemap index files
- **Production Ready**: Comprehensive error handling, logging, and monitoring

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   CLI Interface │    │  Main Crawler    │    │  URL Manager    │
│                 │───▶│   Orchestrator   │───▶│   (SQLite)      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
        ┌─────────────────┐    ┌─────────────────┐
        │ Static Crawler  │    │ Dynamic Handler │
        │   (aiohttp)     │    │  (Playwright)   │
        └─────────────────┘    └─────────────────┘
                    │                       │
                    └───────────┬───────────┘
                                ▼
                    ┌─────────────────┐
                    │ Sitemap Writer  │
                    │    (lxml)       │
                    └─────────────────┘
```

## 📋 Requirements

- Python 3.11+
- 4GB+ RAM (for large-scale crawling)
- 1GB+ disk space (for database and sitemaps)
- Internet connection

## 🛠️ Installation

### 1. Clone Repository

```bash
git clone <repository-url>
cd finploy-sitemap-generator
```

### 2. Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### 3. Verify Installation

```bash
python -m src.sitemap_generator.main --help
```

## 🚀 Quick Start

### Basic Usage

```bash
# Generate sitemaps for both Finploy domains
python -m src.sitemap_generator.main

# Custom configuration
python -m src.sitemap_generator.main \
    --max-depth 3 \
    --max-concurrent 5 \
    --crawl-delay 2.0 \
    --output-dir ./my-sitemaps/
```

### Environment Variables

```bash
# Set environment variables for configuration
export FINPLOY_BASE_URLS="https://www.finploy.com,https://finploy.co.uk"
export FINPLOY_MAX_DEPTH=5
export FINPLOY_MAX_CONCURRENT=10
export FINPLOY_CRAWL_DELAY=1.0

python -m src.sitemap_generator.main
```

## 📖 Usage Guide

### Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--base-urls` | finploy.com,finploy.co.uk | Comma-separated base URLs |
| `--max-depth` | 5 | Maximum crawl depth |
| `--max-concurrent` | 10 | Maximum concurrent requests |
| `--crawl-delay` | 1.0 | Delay between requests (seconds) |
| `--timeout` | 30 | Request timeout (seconds) |
| `--output-dir` | data/sitemap/ | Sitemap output directory |
| `--database-path` | data/urls.db | SQLite database path |
| `--log-level` | INFO | Logging level (DEBUG/INFO/WARNING/ERROR) |
| `--log-file` | None | Log file path (optional) |
| `--clean` | False | Clean database before starting |
| `--disable-dynamic` | False | Disable dynamic content crawling |
| `--disable-robots` | False | Disable robots.txt checking |
| `--export-debug` | None | Export debug info to file |
| `--validate-only` | False | Only validate existing sitemaps |

### Advanced Examples

#### Large Scale Crawling
```bash
python -m src.sitemap_generator.main \
    --max-depth 6 \
    --max-concurrent 20 \
    --crawl-delay 0.5 \
    --log-level DEBUG \
    --log-file crawl.log
```

#### Conservative Crawling
```bash
python -m src.sitemap_generator.main \
    --max-depth 3 \
    --max-concurrent 3 \
    --crawl-delay 3.0 \
    --disable-dynamic
```

#### Resume After Interruption
```bash
# Database persists URLs, so you can resume
python -m src.sitemap_generator.main
```

#### Clean Start
```bash
python -m src.sitemap_generator.main --clean
```

## 🔧 Configuration

### Environment Variables

Create a `.env` file or set environment variables:

```bash
# Base URLs to crawl
FINPLOY_BASE_URLS=https://www.finploy.com,https://finploy.co.uk

# Crawling parameters
FINPLOY_MAX_DEPTH=5
FINPLOY_MAX_CONCURRENT=10
FINPLOY_CRAWL_DELAY=1.0
FINPLOY_TIMEOUT=30

# File paths
FINPLOY_DATABASE_PATH=data/urls.db
FINPLOY_SITEMAP_DIR=data/sitemap/

# Behavior
FINPLOY_RESPECT_ROBOTS=true
FINPLOY_ENABLE_DYNAMIC=true

# HTTP settings
FINPLOY_USER_AGENT=Finploy-Sitemap-Generator/1.0
```

### YAML Configuration (Optional)

Create `config/crawler_config.yaml`:

```yaml
base_urls:
  - https://www.finploy.com
  - https://finploy.co.uk

crawling:
  max_depth: 5
  max_concurrent_requests: 10
  crawl_delay: 1.0
  request_timeout: 30

paths:
  database_path: data/urls.db
  sitemap_output_dir: data/sitemap/

features:
  enable_dynamic_crawling: true
  respect_robots_txt: true

http:
  user_agent: Finploy-Sitemap-Generator/1.0
```

## 📊 Output

### Generated Files

The tool generates the following files in the output directory:

```
data/sitemap/
├── sitemap.xml              # Single sitemap (if ≤50k URLs)
├── sitemap_001.xml          # Multiple sitemaps (if >50k URLs)
├── sitemap_002.xml
├── ...
├── sitemap_index.xml        # Sitemap index (for multiple files)
└── robots.txt               # Robots.txt with sitemap references
```

### Sitemap Structure

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://www.finploy.com/</loc>
    <lastmod>2024-01-15T10:30:00+00:00</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://www.finploy.com/jobs</loc>
    <lastmod>2024-01-15T10:30:00+00:00</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.8</priority>
  </url>
</urlset>
```

### Database Schema

SQLite database stores crawling state:

```sql
-- URLs table
CREATE TABLE urls (
    id INTEGER PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    discovered_at TIMESTAMP,
    last_crawled TIMESTAMP,
    status_code INTEGER,
    content_type TEXT,
    is_dynamic BOOLEAN,
    depth INTEGER,
    parent_url TEXT,
    crawl_status TEXT,
    error_message TEXT
);

-- Crawl queue
CREATE TABLE crawl_queue (
    id INTEGER PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    priority INTEGER,
    added_at TIMESTAMP,
    is_processing BOOLEAN
);
```

## 🧪 Testing

### Run Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run all tests
pytest

# Run specific test categories
pytest tests/test_url_manager.py
pytest tests/test_crawler.py
pytest tests/test_sitemap_writer.py

# Run with coverage
pytest --cov=src/sitemap_generator

# Run with verbose output
pytest -v
```

### Test Categories

- **Unit Tests**: Individual component testing
- **Integration Tests**: Component interaction testing
- **Mock Tests**: External dependency mocking

## 📈 Performance

### Benchmarks

Typical performance on modern hardware:

| Metric | Value |
|--------|-------|
| Crawling Speed | 50-100 URLs/minute |
| Memory Usage | 200-500 MB |
| Database Size | ~1MB per 10k URLs |
| Sitemap Generation | <30 seconds for 50k URLs |

### Optimization Tips

1. **Increase Concurrency**: Higher `--max-concurrent` for faster crawling
2. **Reduce Delay**: Lower `--crawl-delay` for speed (respect server limits)
3. **Limit Depth**: Lower `--max-depth` for focused crawling
4. **Disable Dynamic**: Use `--disable-dynamic` for static-only crawling
5. **SSD Storage**: Use SSD for database performance

## 🔍 Monitoring

### Logging

The tool provides comprehensive logging:

```bash
# Enable debug logging
python -m src.sitemap_generator.main --log-level DEBUG --log-file debug.log

# Monitor progress
tail -f debug.log
```

### Statistics

Real-time statistics during crawling:

```
CRAWLING STATISTICS
==========================================
Total URLs discovered: 15,432
Total URLs crawled: 12,845
Successful crawls: 12,234
Failed crawls: 611
Success rate: 95.2%

Crawling method breakdown:
Static pages: 10,123
Dynamic pages: 2,111

Crawling duration: 2.5h
Average crawling rate: 1.4 URLs/second
==========================================
```

## 🐛 Troubleshooting

### Common Issues

#### 1. Playwright Installation
```bash
# Error: Playwright browsers not found
playwright install chromium

# Alternative: Use system Chrome
export PLAYWRIGHT_BROWSERS_PATH=/usr/bin/google-chrome
```

#### 2. Memory Issues
```bash
# Reduce concurrency
python -m src.sitemap_generator.main --max-concurrent 3

# Disable dynamic crawling
python -m src.sitemap_generator.main --disable-dynamic
```

#### 3. Rate Limiting
```bash
# Increase delay between requests
python -m src.sitemap_generator.main --crawl-delay 3.0
```

#### 4. Database Corruption
```bash
# Clean and restart
python -m src.sitemap_generator.main --clean
```

### Debug Mode

Enable debug mode for detailed troubleshooting:

```bash
python -m src.sitemap_generator.main \
    --log-level DEBUG \
    --log-file debug.log \
    --export-debug debug_urls.txt
```

## 🔒 Security

### Best Practices

1. **Respect robots.txt**: Enabled by default
2. **Rate Limiting**: Prevents server overload
3. **User Agent**: Identifies the crawler
4. **Timeout Handling**: Prevents hanging requests
5. **Error Handling**: Graceful failure recovery

### Compliance

- Follows robots.txt directives
- Implements polite crawling delays
- Respects server response codes
- Uses appropriate User-Agent string

## 🚀 Deployment

### Production Deployment

#### Docker (Recommended)

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN playwright install chromium

COPY . .
CMD ["python", "-m", "src.sitemap_generator.main"]
```

#### Systemd Service

```ini
[Unit]
Description=Finploy Sitemap Generator
After=network.target

[Service]
Type=simple
User=crawler
WorkingDirectory=/opt/finploy-sitemap-generator
ExecStart=/usr/bin/python -m src.sitemap_generator.main
Restart=on-failure
RestartSec=300

[Install]
WantedBy=multi-user.target
```

#### Cron Job

```bash
# Daily sitemap generation
0 2 * * * cd /opt/finploy-sitemap-generator && python -m src.sitemap_generator.main --clean
```

### Cloud Deployment

#### AWS EC2
- Use t3.medium or larger instance
- Install Chrome dependencies
- Configure security groups for outbound HTTP/HTTPS

#### Google Cloud Platform
- Use e2-standard-2 or larger instance
- Enable Cloud Logging for monitoring
- Use persistent disks for database storage

#### Azure VM
- Use Standard_B2s or larger instance
- Configure Network Security Groups
- Use managed disks for storage

## 📚 API Reference

### Core Classes

#### `SitemapCrawler`
Main orchestrator class that coordinates all crawling activities.

```python
from src.sitemap_generator import SitemapCrawler, CrawlConfig

config = CrawlConfig(
    base_urls=["https://www.finploy.com"],
    max_depth=3
)

crawler = SitemapCrawler(config)
await crawler.initialize()
statistics = await crawler.crawl_websites()
await crawler.cleanup()
```

#### `URLManager`
Manages URL storage and retrieval using SQLite.

```python
from src.sitemap_generator.url_manager import URLManager

manager = URLManager("urls.db")
await manager.initialize()
await manager.add_url("https://example.com")
urls = await manager.get_next_urls_to_crawl(10)
```

#### `SitemapWriter`
Generates XML sitemaps from crawled URLs.

```python
from src.sitemap_generator.sitemap_writer import SitemapWriter

writer = SitemapWriter("output/")
sitemap_files = writer.generate_sitemaps(url_records)
```

### Configuration

#### `CrawlConfig`
Configuration dataclass for crawler settings.

```python
from src.sitemap_generator.types import CrawlConfig

config = CrawlConfig(
    base_urls=["https://www.finploy.com"],
    max_depth=5,
    max_concurrent_requests=10,
    crawl_delay=1.0,
    request_timeout=30,
    database_path="data/urls.db",
    sitemap_output_dir="data/sitemap/",
    respect_robots_txt=True,
    enable_dynamic_crawling=True
)
```

## 🤝 Contributing

### Development Setup

```bash
# Clone repository
git clone <repository-url>
cd finploy-sitemap-generator

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install development dependencies
pip install -r requirements.txt
pip install pytest pytest-asyncio black isort mypy

# Install Playwright
playwright install chromium

# Run tests
pytest

# Format code
black src/ tests/
isort src/ tests/

# Type checking
mypy src/
```

### Code Style

- Follow PEP 8 guidelines
- Use Black for code formatting
- Use isort for import sorting
- Add type hints to all functions
- Write comprehensive docstrings
- Maintain test coverage >90%

### Pull Request Process

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Run full test suite
5. Format code with Black/isort
6. Submit pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙋 Support

### Getting Help

1. **Documentation**: Check this README and code comments
2. **Issues**: Create GitHub issue for bugs/features
3. **Discussions**: Use GitHub Discussions for questions
4. **Email**: Contact tech@finploy.com for urgent issues

### Reporting Bugs

When reporting bugs, please include:

- Python version and OS
- Full command used
- Error messages and logs
- Expected vs actual behavior
- Steps to reproduce

### Feature Requests

For feature requests, please describe:

- Use case and motivation
- Proposed solution
- Alternative approaches considered
- Impact on existing functionality

---

**Built with ❤️ for the Finploy team**
