#!/bin/bash
#===============================================================================
# VGAP Runtime Monitor
#
# Displays real-time status of all platform services in a formatted view.
# Run this in a separate terminal while the platform is running.
#===============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker/docker-compose.yml"

check_service() {
    local service="$1"
    if docker compose -f "$COMPOSE_FILE" ps --status running 2>/dev/null | grep -q "$service"; then
        echo -e "${GREEN}●${NC}"
    else
        echo -e "${RED}●${NC}"
    fi
}

get_cpu_mem() {
    docker stats --no-stream --format "{{.Name}}: CPU {{.CPUPerc}} | MEM {{.MemUsage}}" 2>/dev/null | head -5
}

get_active_runs() {
    curl -sf http://localhost:8000/api/v1/runs?status=running 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('total', 0))
except:
    print('?')
" 2>/dev/null || echo "?"
}

get_api_health() {
    if curl -sf http://localhost:8000/health | grep -q "healthy"; then
        echo -e "${GREEN}healthy${NC}"
    else
        echo -e "${RED}unhealthy${NC}"
    fi
}

print_header() {
    clear
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════════════╗"
    echo "║                    VGAP RUNTIME MONITOR                              ║"
    echo "╚══════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_services() {
    echo -e "${BOLD}Services:${NC}"
    echo ""
    printf "  %-20s %s\n" "PostgreSQL" "$(check_service 'postgres')"
    printf "  %-20s %s\n" "Redis" "$(check_service 'redis')"
    printf "  %-20s %s\n" "VGAP API" "$(check_service 'vgap-api')"
    printf "  %-20s %s\n" "VGAP Worker" "$(check_service 'vgap-worker')"
    printf "  %-20s %s\n" "Prometheus" "$(check_service 'prometheus')"
    printf "  %-20s %s\n" "Grafana" "$(check_service 'grafana')"
    echo ""
}

print_api_status() {
    echo -e "${BOLD}API Status:${NC}"
    echo ""
    echo "  Health: $(get_api_health)"
    echo "  Active Runs: $(get_active_runs)"
    echo ""
}

print_resources() {
    echo -e "${BOLD}Resource Usage:${NC}"
    echo ""
    docker stats --no-stream --format "  {{.Name}}: CPU {{.CPUPerc}} | MEM {{.MemUsage}}" 2>/dev/null | head -6
    echo ""
}

print_footer() {
    echo -e "${CYAN}────────────────────────────────────────────────────────────────────────${NC}"
    echo ""
    echo -e "  API:        ${BOLD}http://localhost:8000${NC}"
    echo -e "  API Docs:   ${BOLD}http://localhost:8000/api/docs${NC}"
    echo -e "  Grafana:    ${BOLD}http://localhost:3000${NC}"
    echo ""
    echo -e "  Last update: $(date '+%Y-%m-%d %H:%M:%S')"
    echo -e "  Press ${BOLD}Ctrl+C${NC} to exit"
    echo ""
}

# Main loop
trap 'echo ""; echo "Monitor stopped."; exit 0' SIGINT SIGTERM

while true; do
    print_header
    print_services
    print_api_status
    print_resources
    print_footer
    sleep 5
done
