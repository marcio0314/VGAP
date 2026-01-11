#!/bin/bash
#===============================================================================
# VGAP - Viral Genomics Analysis Platform
# Double-Click Launcher for macOS
#===============================================================================
# 
# This script starts the complete VGAP platform with:
# - Environment validation
# - Docker services
# - Real-time colorized logging
# - Clean shutdown handling
#
# Usage: Double-click this file or run: ./start_vgap.command
#===============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"

# Log file
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/startup_$(date +%Y%m%d_%H%M%S).log"

#===============================================================================
# HELPER FUNCTIONS
#===============================================================================

print_banner() {
    clear
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════════════╗"
    echo "║                                                                      ║"
    echo "║   ██╗   ██╗ ██████╗  █████╗ ██████╗                                  ║"
    echo "║   ██║   ██║██╔════╝ ██╔══██╗██╔══██╗                                 ║"
    echo "║   ██║   ██║██║  ███╗███████║██████╔╝                                 ║"
    echo "║   ╚██╗ ██╔╝██║   ██║██╔══██║██╔═══╝                                  ║"
    echo "║    ╚████╔╝ ╚██████╔╝██║  ██║██║                                      ║"
    echo "║     ╚═══╝   ╚═════╝ ╚═╝  ╚═╝╚═╝                                      ║"
    echo "║                                                                      ║"
    echo "║   Viral Genomics Analysis Platform                                   ║"
    echo "║   Production-Grade Bioinformatics Pipeline                           ║"
    echo "║                                                                      ║"
    echo "╚══════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
}

log() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    case "$level" in
        "INFO")  color="${GREEN}" ;;
        "WARN")  color="${YELLOW}" ;;
        "ERROR") color="${RED}" ;;
        "API")   color="${BLUE}" ;;
        "WORKER") color="${PURPLE}" ;;
        "DB")    color="${CYAN}" ;;
        *)       color="${NC}" ;;
    esac
    
    echo -e "${color}[${timestamp}] [${level}]${NC} ${message}"
    echo "[${timestamp}] [${level}] ${message}" >> "$LOG_FILE"
}

check_command() {
    if command -v "$1" &> /dev/null; then
        log "INFO" "✓ $1 is installed"
        return 0
    else
        log "ERROR" "✗ $1 is NOT installed"
        return 1
    fi
}

check_port() {
    local port="$1"
    local service="$2"
    if lsof -i :$port &> /dev/null; then
        log "WARN" "⚠ Port $port ($service) is already in use"
        return 1
    else
        log "INFO" "✓ Port $port ($service) is available"
        return 0
    fi
}

get_disk_space() {
    df -h "$PROJECT_DIR" | awk 'NR==2 {print $4}'
}

get_memory() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        vm_stat | awk '/Pages free/ {free=$3} /Pages active/ {active=$3} END {print int((free+active)*4096/1024/1024/1024)"GB"}'
    else
        # Linux
        free -h | awk '/Mem:/ {print $7}'
    fi
}

#===============================================================================
# ENVIRONMENT VALIDATION
#===============================================================================

validate_environment() {
    log "INFO" "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "INFO" "ENVIRONMENT VALIDATION"
    log "INFO" "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    local errors=0
    
    # Check Docker
    if ! check_command "docker"; then
        log "ERROR" "Docker is required. Install from: https://docker.com"
        ((errors++))
    else
        # Check if Docker is running
        if ! docker info &> /dev/null; then
            log "ERROR" "Docker is not running. Please start Docker Desktop."
            ((errors++))
        else
            log "INFO" "✓ Docker daemon is running"
        fi
    fi
    
    # Check Docker Compose
    if docker compose version &> /dev/null; then
        log "INFO" "✓ Docker Compose (plugin) is available"
    elif command -v docker-compose &> /dev/null; then
        log "INFO" "✓ Docker Compose (standalone) is available"
    else
        log "ERROR" "Docker Compose is required"
        ((errors++))
    fi
    
    # Check disk space
    local disk_free=$(get_disk_space)
    log "INFO" "  Disk space available: $disk_free"
    
    # Check memory
    local mem_available=$(get_memory)
    log "INFO" "  Available memory: ~$mem_available"
    
    # Check ports
    log "INFO" ""
    log "INFO" "Checking required ports..."
    check_port 8000 "API" || ((errors++))
    check_port 5432 "PostgreSQL" || true  # Warning only
    check_port 6379 "Redis" || true       # Warning only
    check_port 5555 "Flower" || true      # Warning only
    
    # Check .env file
    log "INFO" ""
    if [[ -f "$PROJECT_DIR/.env" ]]; then
        log "INFO" "✓ .env file exists"
    else
        log "WARN" "⚠ .env file not found, will use defaults"
        if [[ -f "$PROJECT_DIR/.env.example" ]]; then
            cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
            log "INFO" "  Created .env from .env.example"
        fi
    fi
    
    log "INFO" ""
    
    if [[ $errors -gt 0 ]]; then
        log "ERROR" "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        log "ERROR" "VALIDATION FAILED - $errors error(s) found"
        log "ERROR" "Please fix the issues above and try again."
        log "ERROR" "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        echo "Press any key to exit..."
        read -n 1
        exit 1
    fi
    
    log "INFO" "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "INFO" "✓ ENVIRONMENT VALIDATION PASSED"
    log "INFO" "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

#===============================================================================
# SERVICE MANAGEMENT
#===============================================================================

start_services() {
    log "INFO" ""
    log "INFO" "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "INFO" "STARTING SERVICES"
    log "INFO" "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    cd "$PROJECT_DIR/docker"
    
    # Build images if needed
    log "INFO" "Building Docker images (this may take a while on first run)..."
    docker compose build --quiet 2>&1 | while read -r line; do
        log "INFO" "  $line"
    done
    
    # Start services in background
    log "INFO" "Starting containers..."
    docker compose up -d
    
    log "INFO" ""
    log "INFO" "Waiting for services to become healthy..."
    
    # Wait for PostgreSQL
    local retries=30
    while [[ $retries -gt 0 ]]; do
        if docker compose exec -T postgres pg_isready -U vgap &> /dev/null; then
            log "DB" "✓ PostgreSQL is ready"
            break
        fi
        sleep 1
        ((retries--))
    done
    
    if [[ $retries -eq 0 ]]; then
        log "ERROR" "PostgreSQL failed to start"
    fi
    
    # Wait for Redis
    retries=10
    while [[ $retries -gt 0 ]]; do
        if docker compose exec -T redis redis-cli ping &> /dev/null; then
            log "DB" "✓ Redis is ready"
            break
        fi
        sleep 1
        ((retries--))
    done
    
    # Wait for API
    retries=30
    while [[ $retries -gt 0 ]]; do
        if curl -sf http://localhost:8000/health &> /dev/null; then
            log "API" "✓ API is healthy"
            break
        fi
        sleep 2
        ((retries--))
    done
    
    if [[ $retries -eq 0 ]]; then
        log "WARN" "API health check timed out (may still be starting)"
    fi
    
    log "INFO" ""
    log "INFO" "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "INFO" "✓ SERVICES STARTED"
    log "INFO" "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

show_status() {
    echo ""
    echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${CYAN}║                         SERVICE STATUS                               ║${NC}"
    echo -e "${BOLD}${CYAN}╠══════════════════════════════════════════════════════════════════════╣${NC}"
    
    # Check each service
    local services=("postgres" "redis" "vgap-api" "vgap-worker")
    for svc in "${services[@]}"; do
        if docker compose -f "$PROJECT_DIR/docker/docker-compose.yml" ps --status running | grep -q "$svc"; then
            echo -e "${CYAN}║${NC}  ${GREEN}●${NC} $svc $(printf '%*s' $((50-${#svc})) '') ${GREEN}UP${NC}      ${CYAN}║${NC}"
        else
            echo -e "${CYAN}║${NC}  ${RED}●${NC} $svc $(printf '%*s' $((50-${#svc})) '') ${RED}DOWN${NC}    ${CYAN}║${NC}"
        fi
    done
    
    echo -e "${BOLD}${CYAN}╠══════════════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${BOLD}${CYAN}║                          ACCESS POINTS                               ║${NC}"
    echo -e "${BOLD}${CYAN}╠══════════════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${CYAN}║${NC}  API:         ${BOLD}http://localhost:8000${NC}                              ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}  API Docs:    ${BOLD}http://localhost:8000/api/docs${NC}                     ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}  Flower:      ${BOLD}http://localhost:5555${NC}                              ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}  Prometheus:  ${BOLD}http://localhost:9090${NC}                              ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}  Grafana:     ${BOLD}http://localhost:3000${NC}                              ${CYAN}║${NC}"
    echo -e "${BOLD}${CYAN}╠══════════════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${CYAN}║${NC}  Log file:    $LOG_FILE    ${CYAN}║${NC}"
    echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

show_logs() {
    echo ""
    log "INFO" "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "INFO" "LIVE LOGS (Ctrl+C to stop)"
    log "INFO" "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    cd "$PROJECT_DIR/docker"
    docker compose logs -f --tail=50 2>&1 | while IFS= read -r line; do
        # Colorize by service
        if [[ "$line" == *"vgap-api"* ]]; then
            echo -e "${BLUE}$line${NC}"
        elif [[ "$line" == *"vgap-worker"* ]]; then
            echo -e "${PURPLE}$line${NC}"
        elif [[ "$line" == *"postgres"* ]]; then
            echo -e "${CYAN}$line${NC}"
        elif [[ "$line" == *"redis"* ]]; then
            echo -e "${GREEN}$line${NC}"
        elif [[ "$line" == *"ERROR"* ]] || [[ "$line" == *"error"* ]]; then
            echo -e "${RED}$line${NC}"
        elif [[ "$line" == *"WARN"* ]] || [[ "$line" == *"warning"* ]]; then
            echo -e "${YELLOW}$line${NC}"
        else
            echo "$line"
        fi
    done
}

cleanup() {
    echo ""
    log "INFO" "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "INFO" "SHUTTING DOWN"
    log "INFO" "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    cd "$PROJECT_DIR/docker"
    docker compose down
    
    log "INFO" "✓ All services stopped cleanly"
    log "INFO" "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Press any key to close..."
    read -n 1
    exit 0
}

#===============================================================================
# MAIN
#===============================================================================

# Trap Ctrl+C for clean shutdown
trap cleanup SIGINT SIGTERM

# Print banner
print_banner

# Navigate to project directory
cd "$PROJECT_DIR"

# Validate environment
validate_environment

# Start services
start_services

# Show status
show_status

# Show live logs
show_logs
