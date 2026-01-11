#!/bin/bash
# VGAP Deployment Script - Development/Staging
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== VGAP Development Deployment ==="
echo "Project directory: $PROJECT_DIR"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "ERROR: Docker Compose is not installed"
    exit 1
fi

# Create .env if not exists
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "Creating .env from .env.example..."
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    
    # Generate a secret key
    SECRET_KEY=$(openssl rand -hex 32)
    sed -i.bak "s/your-super-secret-key-change-in-production/$SECRET_KEY/" "$PROJECT_DIR/.env"
    rm -f "$PROJECT_DIR/.env.bak"
    
    echo "WARNING: Using auto-generated secret key. Change for production!"
fi

# Create data directories
mkdir -p "$PROJECT_DIR/data/uploads"
mkdir -p "$PROJECT_DIR/data/results"
mkdir -p "$PROJECT_DIR/data/references"
mkdir -p "$PROJECT_DIR/data/postgres"
mkdir -p "$PROJECT_DIR/data/redis"

# Build and start services
cd "$PROJECT_DIR/docker"

echo ""
echo "Building Docker images..."
docker compose build

echo ""
echo "Starting services..."
docker compose up -d

echo ""
echo "Waiting for services to be healthy..."
sleep 10

# Check service health
echo ""
echo "Service status:"
docker compose ps

# Check API health
echo ""
echo "Checking API health..."
for i in {1..30}; do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "API is healthy!"
        break
    fi
    echo "Waiting for API... ($i/30)"
    sleep 2
done

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Access points:"
echo "  - API:        http://localhost:8000"
echo "  - API Docs:   http://localhost:8000/api/docs"
echo "  - Flower:     http://localhost:5555"
echo "  - Prometheus: http://localhost:9090"
echo "  - Grafana:    http://localhost:3000 (admin/admin)"
echo ""
echo "Default login: admin@vgap.local / admin_dev_password"
echo ""
echo "To view logs:  docker compose -f docker/docker-compose.yml logs -f"
echo "To stop:       docker compose -f docker/docker-compose.yml down"
