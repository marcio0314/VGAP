# Runtime Monitoring Guide

## Quick Start

### Option 1: Integrated Monitoring (via Launcher)

Double-click `start_vgap.command` - logs are displayed in the terminal automatically.

### Option 2: Separate Monitor

Open a second terminal and run:

```bash
./runtime_monitor.sh
```

This displays a real-time dashboard with:
- Service status (●/●)
- API health
- Active pipeline runs
- Resource usage (CPU/RAM)

## Terminal Output Example

```
╔══════════════════════════════════════════════════════════════════════╗
║                    VGAP RUNTIME MONITOR                              ║
╚══════════════════════════════════════════════════════════════════════╝

Services:

  PostgreSQL           ●
  Redis                ●
  VGAP API             ●
  VGAP Worker          ●
  Prometheus           ●
  Grafana              ●

API Status:

  Health: healthy
  Active Runs: 2

Resource Usage:

  vgap-api: CPU 2.3% | MEM 245MB / 1GB
  vgap-worker: CPU 45.2% | MEM 890MB / 2GB
  postgres: CPU 0.5% | MEM 128MB / 512MB
  redis: CPU 0.1% | MEM 12MB / 64MB

────────────────────────────────────────────────────────────────────────

  API:        http://localhost:8000
  API Docs:   http://localhost:8000/api/docs
  Grafana:    http://localhost:3000

  Last update: 2026-01-11 11:20:00
  Press Ctrl+C to exit
```

## Color Legend

| Symbol | Meaning |
|--------|---------|
| 🟢 ● | Service running |
| 🔴 ● | Service stopped |

## Log Colors (in Launcher)

| Color | Source |
|-------|--------|
| 🔵 Blue | API server |
| 🟣 Purple | Celery worker |
| 🔵 Cyan | Database |
| 🟢 Green | Redis |
| 🟡 Yellow | Warnings |
| 🔴 Red | Errors |

## Viewing Logs

### All Services
```bash
docker compose -f docker/docker-compose.yml logs -f
```

### Specific Service
```bash
docker compose -f docker/docker-compose.yml logs -f vgap-api
docker compose -f docker/docker-compose.yml logs -f vgap-worker
```

### Tail Last N Lines
```bash
docker compose -f docker/docker-compose.yml logs --tail=100 vgap-api
```

## Clean Shutdown

Press **Ctrl+C** in the launcher terminal.

All services will stop gracefully:
1. Celery workers finish current tasks
2. API server closes connections
3. Database flushes and closes
4. Containers stop

## Troubleshooting

### Monitor Shows All Red

```bash
# Check if Docker is running
docker info

# Check container status
docker compose -f docker/docker-compose.yml ps
```

### API Shows Unhealthy

```bash
# Check API logs
docker compose -f docker/docker-compose.yml logs vgap-api

# Check database connectivity
docker compose -f docker/docker-compose.yml exec postgres pg_isready
```
