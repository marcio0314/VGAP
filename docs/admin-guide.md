# VGAP Admin Guide

## System Administration

### Deployment

#### Development

```bash
cd docker
docker compose up -d
```

#### Production (Kubernetes)

```bash
# Apply manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
```

### Configuration

Environment variables in `.env`:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/vgap

# Security (CHANGE IN PRODUCTION!)
SECRET_KEY=generate-with-openssl-rand-hex-32

# Pipeline defaults
MIN_DEPTH=10
MIN_ALLELE_FREQ=0.5

# Resource limits
MAX_CONCURRENT_RUNS=4
WORKER_MEMORY_LIMIT_MB=16384
```

## Database Management

### Updating Reference Databases

Lineage databases must be updated by administrators:

```bash
# Via API
curl -X POST http://localhost:8000/api/v1/admin/databases/pangolin/update

# Via CLI
vgap admin update-database pangolin
```

Updates are logged with:
- Timestamp
- Admin user
- Old and new versions
- Checksums

### Database Backup

```bash
# PostgreSQL backup
pg_dump -h localhost -U vgap -d vgap > backup_$(date +%Y%m%d).sql

# Restore
psql -h localhost -U vgap -d vgap < backup_20240115.sql
```

## System Cleanup (Local Mode)

The Master Cleanup feature allows reclaiming disk space by removing temporary files and regenerable results.

### Via Web UI
1. Go to **Admin** panel
2. Select **Maintenance** tab
3. Click **Scan System** to see what can be deleted
4. Review the file list and click **Confirm Cleanup**

### Via API

```bash
# Preview cleanup (Dry run)
curl http://localhost:8000/api/v1/maintenance/cleanup/preview

# Execute cleanup
curl -X POST http://localhost:8000/api/v1/maintenance/cleanup/execute \
  -H "Content-Type: application/json" \
  -d '{"confirm": true}'
```

**Note:** Source code, reference databases, and configuration files are protected and will never be deleted.

## User Management

In Local Mode, a default `admin` user is automatically provided. Additional users can be created for tracking purposes but authentication is permissive.

### Creating Users

```bash
# Via API
curl -X POST http://localhost:8000/api/v1/admin/users \
  -H "Content-Type: application/json" \
  -d '{
    "email": "analyst@example.com",
    "password": "local_password",
    "full_name": "Jane Analyst",
    "role": "analyst"
  }'
```

### Roles

| Role | Permissions |
|------|-------------|
| viewer | View runs and results |
| analyst | Create runs, view results |
| admin | All + user management + DB updates + System Cleanup |

### Deactivating Users

```bash
curl -X POST http://localhost:8000/api/v1/admin/users/{id}/deactivate
```

## Monitoring

### Prometheus Metrics

Available at `http://localhost:8000/metrics`:

- `vgap_api_requests_total{method,endpoint,status}`
- `vgap_api_request_latency_seconds{method,endpoint}`
- `vgap_pipeline_runs_total{status}`
- `vgap_validation_blocks_total{error_code}`

### Grafana Dashboards

Access at `http://localhost:3000` (default: admin/admin):

- **Overview**: Run counts, success rate, queue depth
- **Performance**: Latency percentiles, throughput
- **Errors**: Failure breakdown, validation blocks

### Alerts

Configure in `docker/alertmanager.yml`:

```yaml
groups:
  - name: vgap
    rules:
      - alert: HighFailureRate
        expr: rate(vgap_pipeline_runs_total{status="failed"}[1h]) > 0.1
        for: 10m
```

## Audit Log

All sensitive operations are logged:

```bash
# View via API
curl http://localhost:8000/api/v1/admin/audit-log \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

Logged events:
- User login/logout
- Run creation/cancellation
- Database updates
- Data exports
- User management actions

## Data Retention

Default: 2 years for raw data and results.

Configure via:
```bash
DATA_RETENTION_DAYS=730
ARCHIVE_ENABLED=true
```

Archived data is moved to cold storage with checksums preserved.

## Security

### TLS Configuration

For production, configure TLS in your ingress/load balancer.

### JWT Settings

```bash
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440  # 24 hours
```

### CORS

```bash
CORS_ORIGINS=["https://vgap.example.com"]
```

## Troubleshooting

### Worker Not Processing

```bash
# Check worker logs
docker logs vgap-worker

# Check Redis connection
docker exec vgap-redis redis-cli ping
```

### Database Connection Issues

```bash
# Check PostgreSQL
docker exec vgap-postgres pg_isready -U vgap

# Check connection from API
docker exec vgap-api python -c "from vgap.config import settings; print(settings.database.url)"
```

### High Memory Usage

Increase worker memory limit or reduce concurrency:

```bash
WORKER_MEMORY_LIMIT_MB=32768
WORKER_CONCURRENCY=2
```
