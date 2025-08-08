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

## 🛠️ Installation & Quick Start

### Option 1: Quick Start (Recommended)

The easiest way to get started is using the quick start script that handles everything automatically:

```bash
# Clone the repository
git clone https://github.com/nandini-asadi/finploy-sitemap-generator.git
cd finploy-sitemap-generator

# Run the quick start script (handles setup + execution)
./quick_start.sh
```

**What the quick start script does:**
- ✅ Creates virtual environment if missing
- ✅ Installs all Python dependencies
- ✅ Installs Playwright browsers
- ✅ Runs the sitemap generator with default settings
- ✅ Shows you where the generated files are located

### Option 2: Production Script (Advanced)

For more control and production use, use the main runner script:

```bash
# Clone the repository
git clone https://github.com/nandini-asadi/finploy-sitemap-generator.git
cd finploy-sitemap-generator

# Use the production script with custom options
./run_sitemap_generator.sh --help                    # See all options
./run_sitemap_generator.sh                           # Run with defaults
./run_sitemap_generator.sh --max-depth 3 --clean    # Custom settings
```

### Option 3: Manual Python Execution (For Development)

If you want to run the Python module directly (useful for development):

```bash
# Set up virtual environment manually
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Run the Python module directly
python -m src.sitemap_generator.main --help
python -m src.sitemap_generator.main
```

## 🚀 Usage Guide

### Recommended Approach: Use the Scripts

**For most users, use the scripts instead of Python commands directly:**

```bash
# Quick and easy (auto-setup + run)
./quick_start.sh

# Production use with custom settings
./run_sitemap_generator.sh --max-concurrent 15 --crawl-delay 0.5

# Conservative crawling
./run_sitemap_generator.sh --max-concurrent 3 --crawl-delay 3.0 --disable-dynamic

# Debug mode
./run_sitemap_generator.sh --debug --log-level DEBUG

# Clean start
./run_sitemap_generator.sh --clean
```

### Script Options

The `run_sitemap_generator.sh` script supports all these options:

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
| `--validate-only` | False | Only validate existing sitemaps |
| `--dry-run` | False | Test configuration without running |

### Why Use Scripts Instead of Python Commands?

The bash scripts provide several advantages:

1. **Automatic Setup**: Handle virtual environment and dependencies
2. **Validation**: Check system requirements before running
3. **Error Handling**: Better error messages and recovery
4. **Logging**: Automatic log file creation and management
5. **Safety**: Prevent multiple instances and handle crashes
6. **Convenience**: No need to remember Python module paths

## 🔧 Configuration

### Environment Variables

The project includes a `.env` file with default settings:

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

You can modify the `.env` file or override with command line options.

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

## 🧪 Testing

### Run Tests

```bash
# Install test dependencies (if not already installed)
source venv/bin/activate
pip install pytest pytest-asyncio

# Run all tests
pytest

# Run specific test categories
pytest tests/test_url_manager.py
pytest tests/test_crawler.py
pytest tests/test_sitemap_writer.py

# Run with verbose output
pytest -v
```

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

1. **Increase Concurrency**: `--max-concurrent 20` for faster crawling
2. **Reduce Delay**: `--crawl-delay 0.5` for speed (respect server limits)
3. **Limit Depth**: `--max-depth 3` for focused crawling
4. **Disable Dynamic**: `--disable-dynamic` for static-only crawling

## 🔍 Monitoring

### Logging

The scripts provide comprehensive logging:

```bash
# Enable debug logging
./run_sitemap_generator.sh --log-level DEBUG --log-file debug.log

# Monitor progress
tail -f logs/sitemap_generator_*.log
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

#### 1. Permission Denied
```bash
# Make scripts executable
chmod +x quick_start.sh run_sitemap_generator.sh
```

#### 2. Playwright Installation Issues
```bash
# The quick_start.sh script handles this automatically, but if needed:
source venv/bin/activate
playwright install chromium
```

#### 3. Memory Issues
```bash
# Reduce concurrency
./run_sitemap_generator.sh --max-concurrent 3 --disable-dynamic
```

#### 4. Rate Limiting
```bash
# Increase delay between requests
./run_sitemap_generator.sh --crawl-delay 3.0
```

### Debug Mode

Enable debug mode for detailed troubleshooting:

```bash
./run_sitemap_generator.sh --debug --log-level DEBUG --export-debug debug_urls.txt
```

## 🚀 Deployment

### Systemd Service (Production)

For production deployment, use the included systemd service:

```bash
# Copy service file
sudo cp finploy-sitemap.service /etc/systemd/system/

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable finploy-sitemap.service
sudo systemctl start finploy-sitemap.service

# Check status
sudo systemctl status finploy-sitemap.service
```

### Cron Job (Scheduled)

For scheduled execution, use the cron templates:

```bash
# Edit crontab
crontab -e

# Add daily execution at 2 AM
0 2 * * * /path/to/finploy-sitemap-generator/run_sitemap_generator.sh --clean
```

## 📚 Project Structure

```
finploy-sitemap-generator/
├── quick_start.sh              # Easy setup and run script
├── run_sitemap_generator.sh    # Production runner script
├── src/sitemap_generator/      # Python application code
├── tests/                      # Test suite
├── data/                       # Generated data (sitemaps, database)
├── logs/                       # Log files
├── .env                        # Environment configuration
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## 🤝 Contributing

### Development Setup

```bash
# Clone and set up development environment
git clone https://github.com/nandini-asadi/finploy-sitemap-generator.git
cd finploy-sitemap-generator

# Use quick start for initial setup
./quick_start.sh

# Install development dependencies
source venv/bin/activate
pip install pytest pytest-asyncio black isort mypy

# Run tests
pytest

# Format code
black src/ tests/
isort src/ tests/
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙋 Support

### Getting Help

1. **Documentation**: Check this README and the `SCRIPTS.md` file
2. **Issues**: Create GitHub issue for bugs/features
3. **Logs**: Check the `logs/` directory for detailed error information

### Reporting Bugs

When reporting bugs, please include:

- Python version and OS
- Full command used
- Error messages and logs
- Expected vs actual behavior
- Steps to reproduce

---

**Built with ❤️ for the Finploy team**
