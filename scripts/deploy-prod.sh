#!/bin/bash
# VGAP Production Deployment Script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== VGAP Production Deployment ==="

# Configuration (override with environment variables)
VGAP_DOMAIN="${VGAP_DOMAIN:-vgap.example.com}"
VGAP_EMAIL="${VGAP_EMAIL:-admin@example.com}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-$(openssl rand -hex 16)}"
SECRET_KEY="${SECRET_KEY:-$(openssl rand -hex 32)}"
REGISTRY="${REGISTRY:-ghcr.io/vgap}"
TAG="${TAG:-latest}"

echo "Domain: $VGAP_DOMAIN"
echo "Registry: $REGISTRY"
echo "Tag: $TAG"

# Validate environment
if [ "$VGAP_DOMAIN" = "vgap.example.com" ]; then
    echo "ERROR: Set VGAP_DOMAIN environment variable"
    exit 1
fi

# Check requirements
for cmd in docker kubectl openssl; do
    if ! command -v $cmd &> /dev/null; then
        echo "ERROR: $cmd is not installed"
        exit 1
    fi
done

# Create namespace
kubectl create namespace vgap --dry-run=client -o yaml | kubectl apply -f -

# Create secrets
echo "Creating secrets..."
kubectl create secret generic vgap-secrets \
    --namespace=vgap \
    --from-literal=database-url="postgresql+asyncpg://vgap:${POSTGRES_PASSWORD}@postgres:5432/vgap" \
    --from-literal=redis-url="redis://redis:6379/0" \
    --from-literal=secret-key="${SECRET_KEY}" \
    --from-literal=postgres-password="${POSTGRES_PASSWORD}" \
    --dry-run=client -o yaml | kubectl apply -f -

# Apply Kubernetes manifests
echo "Applying Kubernetes manifests..."

cat <<EOF | kubectl apply -f -
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: vgap-config
  namespace: vgap
data:
  API_HOST: "0.0.0.0"
  API_PORT: "8000"
  MIN_DEPTH: "10"
  MIN_ALLELE_FREQ: "0.5"
  WORKER_CONCURRENCY: "4"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
  namespace: vgap
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:16
        env:
        - name: POSTGRES_USER
          value: vgap
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: vgap-secrets
              key: postgres-password
        - name: POSTGRES_DB
          value: vgap
        ports:
        - containerPort: 5432
        volumeMounts:
        - name: postgres-data
          mountPath: /var/lib/postgresql/data
      volumes:
      - name: postgres-data
        persistentVolumeClaim:
          claimName: postgres-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: vgap
spec:
  selector:
    app: postgres
  ports:
  - port: 5432
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: vgap
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7
        ports:
        - containerPort: 6379
---
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: vgap
spec:
  selector:
    app: redis
  ports:
  - port: 6379
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vgap-api
  namespace: vgap
spec:
  replicas: 2
  selector:
    matchLabels:
      app: vgap-api
  template:
    metadata:
      labels:
        app: vgap-api
    spec:
      containers:
      - name: api
        image: ${REGISTRY}/vgap-api:${TAG}
        envFrom:
        - configMapRef:
            name: vgap-config
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: vgap-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: vgap-secrets
              key: redis-url
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: vgap-secrets
              key: secret-key
        ports:
        - containerPort: 8000
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 15
          periodSeconds: 20
---
apiVersion: v1
kind: Service
metadata:
  name: vgap-api
  namespace: vgap
spec:
  selector:
    app: vgap-api
  ports:
  - port: 8000
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vgap-worker
  namespace: vgap
spec:
  replicas: 2
  selector:
    matchLabels:
      app: vgap-worker
  template:
    metadata:
      labels:
        app: vgap-worker
    spec:
      containers:
      - name: worker
        image: ${REGISTRY}/vgap-worker:${TAG}
        envFrom:
        - configMapRef:
            name: vgap-config
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: vgap-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: vgap-secrets
              key: redis-url
        resources:
          limits:
            memory: "16Gi"
            cpu: "4"
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: vgap-ingress
  namespace: vgap
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - ${VGAP_DOMAIN}
    secretName: vgap-tls
  rules:
  - host: ${VGAP_DOMAIN}
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: vgap-api
            port:
              number: 8000
EOF

echo ""
echo "=== Production Deployment Complete ==="
echo ""
echo "Next steps:"
echo "1. Create PersistentVolumeClaim for postgres (postgres-pvc)"
echo "2. Configure cert-manager for TLS certificates"
echo "3. Set up monitoring (Prometheus/Grafana)"
echo "4. Configure backup jobs for PostgreSQL"
echo ""
echo "Access: https://$VGAP_DOMAIN"
