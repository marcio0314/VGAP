# VGAP Launcher - User Guide

## Quick Start

**Double-click** `start_vgap.command` to launch the platform.

A Terminal window will open automatically with:
- Environment validation
- Service startup
- Real-time colorized logs

## What Happens on Launch

1. **Environment Check**
   - Docker installed and running
   - Ports 8000, 5432, 6379 available
   - Disk space and memory validation

2. **Service Startup**
   - PostgreSQL database
   - Redis message queue
   - VGAP API server
   - Celery workers

3. **Health Monitoring**
   - Live service status
   - Colorized log stream
   - Error highlighting

## Access Points

| Service | URL |
|---------|-----|
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/api/docs |
| Flower | http://localhost:5555 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |

## Shutdown

Press **Ctrl+C** in the terminal to cleanly stop all services.

## Troubleshooting

### Docker Not Running
```
ERROR: Docker is not running
```
→ Open Docker Desktop and wait for it to start

### Port Already in Use
```
WARN: Port 8000 is already in use
```
→ Stop the conflicting service or change the port in `.env`

### Permission Denied
```bash
chmod +x start_vgap.command
```

## Log Files

Logs are saved to: `logs/startup_YYYYMMDD_HHMMSS.log`

## Color Legend

| Color | Meaning |
|-------|---------|
| 🟢 Green | Success / Info |
| 🔵 Blue | API logs |
| 🟣 Purple | Worker logs |
| 🔵 Cyan | Database logs |
| 🟡 Yellow | Warnings |
| 🔴 Red | Errors |
