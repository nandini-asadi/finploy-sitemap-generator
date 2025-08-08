#!/usr/bin/env bash

#==============================================================================
# Finploy Sitemap Generator Runner Script
#==============================================================================
# Description: Production-ready script to run the Finploy sitemap generator
# Author: Amazon Q Developer
# Version: 1.0.0
# Usage: ./run_sitemap_generator.sh [options]
#==============================================================================

set -euo pipefail  # Exit on error, undefined vars, pipe failures
IFS=$'\n\t'        # Secure Internal Field Separator

#==============================================================================
# CONFIGURATION AND CONSTANTS
#==============================================================================

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_NAME="$(basename "${BASH_SOURCE[0]}")"
readonly VENV_DIR="${SCRIPT_DIR}/venv"
readonly PYTHON_MODULE="src.sitemap_generator.main"
readonly LOG_DIR="${SCRIPT_DIR}/logs"
readonly PID_FILE="${SCRIPT_DIR}/.sitemap_generator.pid"

# Default configuration
DEFAULT_BASE_URLS="https://www.finploy.com,https://finploy.co.uk"
DEFAULT_MAX_DEPTH=5
DEFAULT_MAX_CONCURRENT=10
DEFAULT_CRAWL_DELAY=1.0
DEFAULT_LOG_LEVEL="INFO"
DEFAULT_OUTPUT_DIR="${SCRIPT_DIR}/data/sitemap"
DEFAULT_DATABASE_PATH="${SCRIPT_DIR}/data/urls.db"

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly PURPLE='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly WHITE='\033[1;37m'
readonly NC='\033[0m' # No Color

#==============================================================================
# UTILITY FUNCTIONS
#==============================================================================

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $*" >&2
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $*" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $*" >&2
}

log_debug() {
    if [[ "${DEBUG:-0}" == "1" ]]; then
        echo -e "${BLUE}[DEBUG]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $*" >&2
    fi
}

# Print colored banner
print_banner() {
    echo -e "${PURPLE}"
    cat << 'EOF'
╔══════════════════════════════════════════════════════════════╗
║                 FINPLOY SITEMAP GENERATOR                    ║
║                                                              ║
║              Production Runner Script v1.0.0                ║
║                                                              ║
║  Comprehensive sitemap generation for Finploy websites      ║
╚══════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if process is running
is_running() {
    [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

# Cleanup function
cleanup() {
    local exit_code=$?
    log_info "Cleaning up..."
    
    # Remove PID file if it exists
    [[ -f "$PID_FILE" ]] && rm -f "$PID_FILE"
    
    # Deactivate virtual environment if active
    if [[ -n "${VIRTUAL_ENV:-}" ]]; then
        log_debug "Deactivating virtual environment"
        deactivate 2>/dev/null || true
    fi
    
    exit $exit_code
}

# Signal handlers
handle_interrupt() {
    log_warn "Received interrupt signal (SIGINT/SIGTERM)"
    cleanup
}

#==============================================================================
# VALIDATION FUNCTIONS
#==============================================================================

# Validate Python version
validate_python() {
    if ! command_exists python3; then
        log_error "Python 3 is not installed or not in PATH"
        return 1
    fi
    
    local python_version
    python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    
    if [[ $(echo "$python_version >= 3.11" | bc -l 2>/dev/null || echo "0") != "1" ]]; then
        log_error "Python 3.11+ is required. Found: Python $python_version"
        return 1
    fi
    
    log_info "Python version validated: $python_version"
    return 0
}

# Validate virtual environment
validate_venv() {
    if [[ ! -d "$VENV_DIR" ]]; then
        log_error "Virtual environment not found at: $VENV_DIR"
        log_info "Please run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
        return 1
    fi
    
    if [[ ! -f "$VENV_DIR/bin/activate" ]]; then
        log_error "Virtual environment activation script not found"
        return 1
    fi
    
    log_debug "Virtual environment validated"
    return 0
}

# Validate dependencies
validate_dependencies() {
    local missing_deps=()
    
    # Check Python dependencies
    if ! python3 -c "import aiohttp, playwright, beautifulsoup4, lxml, click" 2>/dev/null; then
        missing_deps+=("Python dependencies")
    fi
    
    # Check Playwright browsers
    if ! python3 -c "from playwright.sync_api import sync_playwright; sync_playwright().start().chromium.launch()" 2>/dev/null; then
        missing_deps+=("Playwright browsers")
    fi
    
    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        log_error "Missing dependencies: ${missing_deps[*]}"
        log_info "Please run: pip install -r requirements.txt && playwright install chromium"
        return 1
    fi
    
    log_debug "Dependencies validated"
    return 0
}

# Validate URLs
validate_urls() {
    local urls="$1"
    IFS=',' read -ra url_array <<< "$urls"
    
    for url in "${url_array[@]}"; do
        url=$(echo "$url" | xargs) # Trim whitespace
        if [[ ! "$url" =~ ^https?:// ]]; then
            log_error "Invalid URL format: $url"
            return 1
        fi
    done
    
    log_debug "URLs validated: $urls"
    return 0
}

# Validate numeric parameters
validate_numeric() {
    local value="$1"
    local name="$2"
    local min="${3:-0}"
    
    if ! [[ "$value" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
        log_error "$name must be a valid number. Got: $value"
        return 1
    fi
    
    if (( $(echo "$value < $min" | bc -l 2>/dev/null || echo "1") )); then
        log_error "$name must be >= $min. Got: $value"
        return 1
    fi
    
    log_debug "$name validated: $value"
    return 0
}

#==============================================================================
# SETUP FUNCTIONS
#==============================================================================

# Setup directories
setup_directories() {
    local dirs=("$LOG_DIR" "$(dirname "$DEFAULT_OUTPUT_DIR")" "$(dirname "$DEFAULT_DATABASE_PATH")")
    
    for dir in "${dirs[@]}"; do
        if [[ ! -d "$dir" ]]; then
            log_info "Creating directory: $dir"
            mkdir -p "$dir" || {
                log_error "Failed to create directory: $dir"
                return 1
            }
        fi
    done
    
    log_debug "Directories setup completed"
    return 0
}

# Activate virtual environment
activate_venv() {
    log_info "Activating virtual environment..."
    
    # shellcheck source=/dev/null
    source "$VENV_DIR/bin/activate" || {
        log_error "Failed to activate virtual environment"
        return 1
    }
    
    log_debug "Virtual environment activated: $VIRTUAL_ENV"
    return 0
}

# Setup logging
setup_logging() {
    local log_file="${LOG_DIR}/sitemap_generator_$(date '+%Y%m%d_%H%M%S').log"
    
    # Create log file
    touch "$log_file" || {
        log_error "Failed to create log file: $log_file"
        return 1
    }
    
    log_info "Log file created: $log_file"
    echo "$log_file"
}

#==============================================================================
# MAIN FUNCTIONS
#==============================================================================

# Show usage information
show_usage() {
    cat << EOF
${WHITE}USAGE:${NC}
    $SCRIPT_NAME [OPTIONS]

${WHITE}DESCRIPTION:${NC}
    Production-ready script to run the Finploy Sitemap Generator.
    Handles virtual environment activation, dependency validation,
    and provides comprehensive logging and error handling.

${WHITE}OPTIONS:${NC}
    -u, --base-urls URL1,URL2    Base URLs to crawl (default: $DEFAULT_BASE_URLS)
    -d, --max-depth NUM          Maximum crawl depth (default: $DEFAULT_MAX_DEPTH)
    -c, --max-concurrent NUM     Maximum concurrent requests (default: $DEFAULT_MAX_CONCURRENT)
    -r, --crawl-delay SECONDS    Delay between requests (default: $DEFAULT_CRAWL_DELAY)
    -l, --log-level LEVEL        Log level: DEBUG|INFO|WARNING|ERROR (default: $DEFAULT_LOG_LEVEL)
    -o, --output-dir PATH        Output directory for sitemaps (default: $DEFAULT_OUTPUT_DIR)
    -b, --database-path PATH     SQLite database path (default: $DEFAULT_DATABASE_PATH)
    
    --clean                      Clean database before starting
    --disable-dynamic            Disable dynamic content crawling
    --disable-robots             Disable robots.txt checking
    --validate-only              Only validate existing sitemaps
    --dry-run                    Validate configuration without running
    
    -h, --help                   Show this help message
    -v, --version                Show version information
    --debug                      Enable debug output

${WHITE}EXAMPLES:${NC}
    # Basic usage (crawl both Finploy domains)
    $SCRIPT_NAME

    # Custom configuration
    $SCRIPT_NAME --max-depth 3 --max-concurrent 5 --crawl-delay 2.0

    # Conservative crawling
    $SCRIPT_NAME --max-concurrent 3 --crawl-delay 3.0 --disable-dynamic

    # Debug mode with clean start
    $SCRIPT_NAME --debug --clean --log-level DEBUG

    # Validate configuration only
    $SCRIPT_NAME --dry-run

${WHITE}ENVIRONMENT VARIABLES:${NC}
    FINPLOY_BASE_URLS           Override default base URLs
    FINPLOY_MAX_DEPTH           Override default max depth
    FINPLOY_MAX_CONCURRENT      Override default concurrency
    FINPLOY_CRAWL_DELAY         Override default crawl delay
    DEBUG                       Enable debug output (0|1)

${WHITE}FILES:${NC}
    Virtual Environment:        $VENV_DIR
    Log Directory:             $LOG_DIR
    PID File:                  $PID_FILE
    Default Output:            $DEFAULT_OUTPUT_DIR
    Default Database:          $DEFAULT_DATABASE_PATH

EOF
}

# Show version information
show_version() {
    echo -e "${WHITE}Finploy Sitemap Generator Runner${NC}"
    echo -e "Version: ${GREEN}1.0.0${NC}"
    echo -e "Python Module: ${CYAN}$PYTHON_MODULE${NC}"
    echo -e "Script Location: ${BLUE}$SCRIPT_DIR${NC}"
}

# Parse command line arguments
parse_arguments() {
    # Initialize variables with defaults
    BASE_URLS="${FINPLOY_BASE_URLS:-$DEFAULT_BASE_URLS}"
    MAX_DEPTH="${FINPLOY_MAX_DEPTH:-$DEFAULT_MAX_DEPTH}"
    MAX_CONCURRENT="${FINPLOY_MAX_CONCURRENT:-$DEFAULT_MAX_CONCURRENT}"
    CRAWL_DELAY="${FINPLOY_CRAWL_DELAY:-$DEFAULT_CRAWL_DELAY}"
    LOG_LEVEL="$DEFAULT_LOG_LEVEL"
    OUTPUT_DIR="$DEFAULT_OUTPUT_DIR"
    DATABASE_PATH="$DEFAULT_DATABASE_PATH"
    
    # Flags
    CLEAN_DB=false
    DISABLE_DYNAMIC=false
    DISABLE_ROBOTS=false
    VALIDATE_ONLY=false
    DRY_RUN=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -u|--base-urls)
                BASE_URLS="$2"
                shift 2
                ;;
            -d|--max-depth)
                MAX_DEPTH="$2"
                shift 2
                ;;
            -c|--max-concurrent)
                MAX_CONCURRENT="$2"
                shift 2
                ;;
            -r|--crawl-delay)
                CRAWL_DELAY="$2"
                shift 2
                ;;
            -l|--log-level)
                LOG_LEVEL="$2"
                shift 2
                ;;
            -o|--output-dir)
                OUTPUT_DIR="$2"
                shift 2
                ;;
            -b|--database-path)
                DATABASE_PATH="$2"
                shift 2
                ;;
            --clean)
                CLEAN_DB=true
                shift
                ;;
            --disable-dynamic)
                DISABLE_DYNAMIC=true
                shift
                ;;
            --disable-robots)
                DISABLE_ROBOTS=true
                shift
                ;;
            --validate-only)
                VALIDATE_ONLY=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --debug)
                DEBUG=1
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            -v|--version)
                show_version
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                echo "Use --help for usage information."
                exit 1
                ;;
        esac
    done
}

# Validate all configuration
validate_configuration() {
    log_info "Validating configuration..."
    
    # Validate system requirements
    validate_python || return 1
    validate_venv || return 1
    
    # Activate virtual environment for dependency checks
    activate_venv || return 1
    validate_dependencies || return 1
    
    # Validate parameters
    validate_urls "$BASE_URLS" || return 1
    validate_numeric "$MAX_DEPTH" "max-depth" 1 || return 1
    validate_numeric "$MAX_CONCURRENT" "max-concurrent" 1 || return 1
    validate_numeric "$CRAWL_DELAY" "crawl-delay" 0 || return 1
    
    # Validate log level
    if [[ ! "$LOG_LEVEL" =~ ^(DEBUG|INFO|WARNING|ERROR)$ ]]; then
        log_error "Invalid log level: $LOG_LEVEL"
        return 1
    fi
    
    log_info "Configuration validation completed successfully"
    return 0
}

# Build command arguments
build_command_args() {
    local args=()
    
    args+=("--base-urls" "$BASE_URLS")
    args+=("--max-depth" "$MAX_DEPTH")
    args+=("--max-concurrent" "$MAX_CONCURRENT")
    args+=("--crawl-delay" "$CRAWL_DELAY")
    args+=("--log-level" "$LOG_LEVEL")
    args+=("--output-dir" "$OUTPUT_DIR")
    args+=("--database-path" "$DATABASE_PATH")
    
    # Add log file
    local log_file
    log_file=$(setup_logging) || return 1
    args+=("--log-file" "$log_file")
    
    # Add flags
    [[ "$CLEAN_DB" == true ]] && args+=("--clean")
    [[ "$DISABLE_DYNAMIC" == true ]] && args+=("--disable-dynamic")
    [[ "$DISABLE_ROBOTS" == true ]] && args+=("--disable-robots")
    [[ "$VALIDATE_ONLY" == true ]] && args+=("--validate-only")
    
    echo "${args[@]}"
}

# Print configuration summary
print_configuration() {
    echo -e "\n${WHITE}CONFIGURATION SUMMARY:${NC}"
    echo -e "${CYAN}Base URLs:${NC}          $BASE_URLS"
    echo -e "${CYAN}Max Depth:${NC}          $MAX_DEPTH"
    echo -e "${CYAN}Max Concurrent:${NC}     $MAX_CONCURRENT"
    echo -e "${CYAN}Crawl Delay:${NC}        ${CRAWL_DELAY}s"
    echo -e "${CYAN}Log Level:${NC}          $LOG_LEVEL"
    echo -e "${CYAN}Output Directory:${NC}   $OUTPUT_DIR"
    echo -e "${CYAN}Database Path:${NC}      $DATABASE_PATH"
    echo -e "${CYAN}Clean Database:${NC}     $CLEAN_DB"
    echo -e "${CYAN}Dynamic Crawling:${NC}   $([[ "$DISABLE_DYNAMIC" == true ]] && echo "Disabled" || echo "Enabled")"
    echo -e "${CYAN}Robots.txt Check:${NC}   $([[ "$DISABLE_ROBOTS" == true ]] && echo "Disabled" || echo "Enabled")"
    echo -e "${CYAN}Validate Only:${NC}      $VALIDATE_ONLY"
    echo -e "${CYAN}Debug Mode:${NC}         ${DEBUG:-0}"
    echo ""
}

# Check if another instance is running
check_running_instance() {
    if is_running; then
        local pid
        pid=$(cat "$PID_FILE")
        log_error "Another instance is already running (PID: $pid)"
        log_info "If you're sure no instance is running, remove: $PID_FILE"
        return 1
    fi
    return 0
}

# Run the sitemap generator
run_generator() {
    local args
    args=$(build_command_args) || return 1
    
    log_info "Starting Finploy Sitemap Generator..."
    log_debug "Command: python3 -m $PYTHON_MODULE ${args[*]}"
    
    # Store PID
    echo $$ > "$PID_FILE"
    
    # Run the generator
    # shellcheck disable=SC2086
    python3 -m "$PYTHON_MODULE" $args
    local exit_code=$?
    
    # Remove PID file
    rm -f "$PID_FILE"
    
    if [[ $exit_code -eq 0 ]]; then
        log_info "Sitemap generation completed successfully!"
    else
        log_error "Sitemap generation failed with exit code: $exit_code"
    fi
    
    return $exit_code
}

#==============================================================================
# MAIN EXECUTION
#==============================================================================

main() {
    # Set up signal handlers
    trap handle_interrupt SIGINT SIGTERM
    trap cleanup EXIT
    
    # Parse arguments
    parse_arguments "$@"
    
    # Show banner
    print_banner
    
    # Print configuration
    print_configuration
    
    # Handle dry run
    if [[ "$DRY_RUN" == true ]]; then
        log_info "Dry run mode - validating configuration only"
        validate_configuration
        log_info "Configuration is valid. Exiting dry run."
        return 0
    fi
    
    # Setup and validation
    setup_directories || return 1
    validate_configuration || return 1
    check_running_instance || return 1
    
    # Run the generator
    run_generator
}

# Execute main function if script is run directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
