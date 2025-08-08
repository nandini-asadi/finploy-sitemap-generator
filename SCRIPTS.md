# Finploy Sitemap Generator - Script Documentation

This document provides comprehensive information about the bash scripts included with the Finploy Sitemap Generator.

## 📋 Available Scripts

### 1. `run_sitemap_generator.sh` - Production Runner Script

**Purpose**: Production-ready script with comprehensive error handling, validation, and logging.

**Features**:
- ✅ **Comprehensive validation** of Python version, virtual environment, and dependencies
- ✅ **Automatic virtual environment** activation and management
- ✅ **Advanced logging** with timestamps and colored output
- ✅ **PID file management** to prevent multiple instances
- ✅ **Signal handling** for graceful shutdown
- ✅ **Configuration validation** with detailed error messages
- ✅ **Dry run mode** for testing configuration
- ✅ **Environment variable support** for configuration
- ✅ **Detailed help and usage** information

**Usage**:
```bash
# Basic usage
./run_sitemap_generator.sh

# With custom options
./run_sitemap_generator.sh --max-depth 3 --max-concurrent 5 --crawl-delay 2.0

# Debug mode
./run_sitemap_generator.sh --debug --log-level DEBUG

# Dry run (validate only)
./run_sitemap_generator.sh --dry-run

# Show help
./run_sitemap_generator.sh --help
```

### 2. `quick_start.sh` - Simple Quick Start Script

**Purpose**: Simplified script for quick setup and execution.

**Features**:
- ✅ **Automatic setup** of virtual environment if missing
- ✅ **Dependency installation** with pip and playwright
- ✅ **One-command execution** with sensible defaults
- ✅ **Minimal configuration** required

**Usage**:
```bash
# Run with default settings
./quick_start.sh
```

### 3. `finploy-sitemap.service` - Systemd Service File

**Purpose**: Production deployment as a systemd service.

**Features**:
- ✅ **Systemd integration** for production environments
- ✅ **Security hardening** with restricted permissions
- ✅ **Resource limits** (memory, CPU)
- ✅ **Automatic restart** on failure
- ✅ **Journal logging** integration

**Installation**:
```bash
# Copy to systemd directory
sudo cp finploy-sitemap.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable service
sudo systemctl enable finploy-sitemap.service

# Start service
sudo systemctl start finploy-sitemap.service

# Check status
sudo systemctl status finploy-sitemap.service
```

### 4. `cron_template.txt` - Cron Job Templates

**Purpose**: Templates for scheduled sitemap generation.

**Examples**:
```bash
# Daily generation at 2 AM
0 2 * * * /opt/finploy-sitemap-generator/run_sitemap_generator.sh --clean

# Weekly deep crawl on Sundays
0 3 * * 0 /opt/finploy-sitemap-generator/run_sitemap_generator.sh --clean --max-depth 6

# Hourly validation
0 * * * * /opt/finploy-sitemap-generator/run_sitemap_generator.sh --validate-only
```

## 🛠️ Script Best Practices Implemented

### 1. **Error Handling**
```bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures
IFS=$'\n\t'        # Secure Internal Field Separator
```

### 2. **Signal Handling**
```bash
trap handle_interrupt SIGINT SIGTERM
trap cleanup EXIT
```

### 3. **Logging Functions**
```bash
log_info() { echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $*" >&2; }
log_error() { echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $*" >&2; }
```

### 4. **Path Safety**
```bash
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
```

### 5. **Input Validation**
```bash
validate_numeric() {
    if ! [[ "$value" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
        log_error "$name must be a valid number. Got: $value"
        return 1
    fi
}
```

### 6. **Resource Management**
```bash
cleanup() {
    local exit_code=$?
    [[ -f "$PID_FILE" ]] && rm -f "$PID_FILE"
    exit $exit_code
}
```

## 🔧 Configuration Options

### Command Line Arguments

| Option | Description | Default |
|--------|-------------|---------|
| `-u, --base-urls` | Comma-separated URLs to crawl | finploy.com,finploy.co.uk |
| `-d, --max-depth` | Maximum crawl depth | 5 |
| `-c, --max-concurrent` | Maximum concurrent requests | 10 |
| `-r, --crawl-delay` | Delay between requests (seconds) | 1.0 |
| `-l, --log-level` | Log level (DEBUG/INFO/WARNING/ERROR) | INFO |
| `-o, --output-dir` | Output directory for sitemaps | data/sitemap/ |
| `-b, --database-path` | SQLite database path | data/urls.db |
| `--clean` | Clean database before starting | false |
| `--disable-dynamic` | Disable dynamic content crawling | false |
| `--disable-robots` | Disable robots.txt checking | false |
| `--validate-only` | Only validate existing sitemaps | false |
| `--dry-run` | Validate configuration without running | false |
| `--debug` | Enable debug output | false |

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FINPLOY_BASE_URLS` | Override default base URLs | - |
| `FINPLOY_MAX_DEPTH` | Override default max depth | - |
| `FINPLOY_MAX_CONCURRENT` | Override default concurrency | - |
| `FINPLOY_CRAWL_DELAY` | Override default crawl delay | - |
| `DEBUG` | Enable debug output (0/1) | 0 |

## 📁 File Structure

```
finploy-sitemap-generator/
├── run_sitemap_generator.sh    # Main production script
├── quick_start.sh              # Simple quick start script
├── finploy-sitemap.service     # Systemd service file
├── cron_template.txt           # Cron job templates
├── logs/                       # Log files directory
│   └── sitemap_generator_*.log
├── data/                       # Generated data
│   ├── sitemap/               # XML sitemaps
│   └── urls.db                # SQLite database
└── .sitemap_generator.pid     # PID file (when running)
```

## 🚀 Usage Examples

### Basic Usage
```bash
# Run with defaults
./run_sitemap_generator.sh

# Quick start (auto-setup)
./quick_start.sh
```

### Custom Configuration
```bash
# Conservative crawling
./run_sitemap_generator.sh \
    --max-depth 3 \
    --max-concurrent 3 \
    --crawl-delay 3.0 \
    --disable-dynamic

# Aggressive crawling
./run_sitemap_generator.sh \
    --max-depth 6 \
    --max-concurrent 20 \
    --crawl-delay 0.5 \
    --clean
```

### Development and Testing
```bash
# Debug mode
./run_sitemap_generator.sh --debug --log-level DEBUG

# Validate configuration only
./run_sitemap_generator.sh --dry-run

# Validate existing sitemaps
./run_sitemap_generator.sh --validate-only
```

### Production Deployment
```bash
# Using environment variables
export FINPLOY_MAX_CONCURRENT=15
export FINPLOY_CRAWL_DELAY=0.8
./run_sitemap_generator.sh --clean

# With systemd
sudo systemctl start finploy-sitemap.service

# With cron (daily at 2 AM)
echo "0 2 * * * /opt/finploy-sitemap-generator/run_sitemap_generator.sh --clean" | crontab -
```

## 🔍 Troubleshooting

### Common Issues

#### 1. Permission Denied
```bash
# Make scripts executable
chmod +x run_sitemap_generator.sh quick_start.sh
```

#### 2. Virtual Environment Issues
```bash
# Recreate virtual environment
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

#### 3. Dependencies Missing
```bash
# Install system dependencies (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install python3 python3-venv python3-pip

# Install Python dependencies
./quick_start.sh  # This will auto-install dependencies
```

#### 4. Multiple Instances
```bash
# Check for running instances
ps aux | grep sitemap_generator

# Remove stale PID file
rm -f .sitemap_generator.pid
```

### Debug Mode

Enable debug mode for detailed troubleshooting:
```bash
./run_sitemap_generator.sh --debug --log-level DEBUG
```

This will show:
- Detailed validation steps
- Command construction
- Environment variables
- File operations
- Error stack traces

### Log Files

Check log files for detailed information:
```bash
# View latest log
ls -la logs/
tail -f logs/sitemap_generator_*.log

# Search for errors
grep -i error logs/sitemap_generator_*.log
```

## 🔒 Security Considerations

### File Permissions
```bash
# Secure script permissions
chmod 755 run_sitemap_generator.sh
chmod 755 quick_start.sh

# Secure data directory
chmod 750 data/
chmod 640 data/urls.db
```

### Systemd Security
The systemd service includes security hardening:
- `NoNewPrivileges=true`
- `PrivateTmp=true`
- `ProtectSystem=strict`
- `ProtectHome=true`
- Limited read/write paths

### Resource Limits
- Memory limit: 1GB
- CPU quota: 80%
- Automatic restart on failure

## 📊 Monitoring

### Log Monitoring
```bash
# Real-time log monitoring
tail -f logs/sitemap_generator_*.log

# Error monitoring
grep -i "error\|failed\|exception" logs/sitemap_generator_*.log

# Success monitoring
grep -i "completed successfully" logs/sitemap_generator_*.log
```

### System Monitoring
```bash
# Check service status
sudo systemctl status finploy-sitemap.service

# View service logs
sudo journalctl -u finploy-sitemap.service -f

# Check resource usage
ps aux | grep sitemap_generator
```

### Performance Monitoring
```bash
# Monitor crawling progress
tail -f logs/sitemap_generator_*.log | grep "Crawling depth\|STATISTICS"

# Check generated files
ls -la data/sitemap/
wc -l data/sitemap/sitemap*.xml
```

---

**These scripts provide a complete, production-ready solution for running the Finploy Sitemap Generator with comprehensive error handling, logging, and deployment options.**
