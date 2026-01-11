# VGAP Developer Documentation

## Architecture Overview

VGAP (Viral Genomics Analysis Platform) is a production-grade pipeline for analyzing viral genomic data. This guide covers the system architecture, development setup, and contribution guidelines.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (React)                         │
│                    localhost:3000                               │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Server                             │
│                    localhost:8000                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │  Auth    │  │  Runs    │  │ Samples  │  │ Reports  │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
└─────────────────────────────────────────────────────────────────┘
        │                           │
        ▼                           ▼
┌───────────────┐           ┌───────────────┐
│  PostgreSQL   │           │     Redis     │
│  (Database)   │           │    (Queue)    │
└───────────────┘           └───────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────┐
                    │     Celery Workers        │
                    │  (Pipeline Execution)     │
                    │                           │
                    │  ┌─────┐ ┌─────┐ ┌─────┐ │
                    │  │ QC  │ │ Map │ │ Var │ │
                    │  └─────┘ └─────┘ └─────┘ │
                    └───────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────┐
                    │      Results Storage      │
                    │    (Filesystem + DB)      │
                    └───────────────────────────┘
```

---

## Directory Structure

```
vgap/
├── api/                    # FastAPI application
│   ├── main.py            # App entry point
│   ├── schemas.py         # Pydantic models
│   └── routes/            # API endpoints
│       ├── auth.py
│       ├── runs.py
│       ├── samples.py
│       ├── reports.py
│       └── admin.py
├── models/                 # SQLAlchemy models
│   └── __init__.py        # Database schema
├── services/               # Business logic
│   ├── database.py        # DB connection
│   ├── user_service.py    # User management
│   ├── run_service.py     # Run management
│   └── pipeline.py        # Pipeline orchestration
├── pipeline/               # Bioinformatics modules
│   ├── qc.py              # Quality control
│   ├── mapping.py         # Reference mapping
│   ├── variants.py        # Variant calling
│   ├── lineage.py         # Lineage assignment
│   ├── phylogeny.py       # Phylogenetics
│   ├── influenza.py       # Influenza clades
│   ├── treetime.py        # Time-scaled trees
│   ├── reporting.py       # Report generation
│   ├── visualizations.py  # Interactive plots
│   └── pdf_export.py      # PDF export
├── validators/             # Input validation
│   └── preflight.py       # Pre-flight checks
├── utils/                  # Utilities
│   └── provenance.py      # Audit tracking
├── config.py              # Configuration
└── worker.py              # Celery worker

frontend/                   # React frontend
├── src/
│   ├── pages/             # Route pages
│   ├── components/        # UI components
│   ├── hooks/             # React hooks
│   └── utils/             # API client
├── tailwind.config.js     # Design system
└── vite.config.ts         # Build config

docker/                     # Docker setup
├── docker-compose.yml
├── Dockerfile.api
├── Dockerfile.worker
├── grafana/               # Dashboards
└── prometheus/            # Alerts

tests/                      # Test suite
├── unit/
├── integration/
└── regression/
```

---

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- PostgreSQL 15+
- Redis 7+

### Local Development

```bash
# Clone repository
git clone https://github.com/yourorg/vgap.git
cd vgap

# Create Python virtual environment
python -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install -e ".[dev]"

# Install bioinformatics tools (macOS)
brew install minimap2 samtools bcftools

# Install frontend dependencies
cd frontend && npm install && cd ..

# Start infrastructure
docker compose -f docker/docker-compose.yml up -d postgres redis

# Run database migrations
alembic upgrade head

# Start API server
uvicorn vgap.api.main:app --reload --port 8000

# Start Celery worker (separate terminal)
celery -A vgap.worker worker -l info

# Start frontend (separate terminal)
cd frontend && npm run dev
```

### Environment Variables

```bash
# .env file
VGAP_ADMIN_EMAIL=admin@example.com
VGAP_ADMIN_PASSWORD=secure-password-here

DATABASE_URL=postgresql+asyncpg://vgap:vgap@localhost:5432/vgap
REDIS_URL=redis://localhost:6379

VGAP_SECRET_KEY=your-secret-key-here
VGAP_STORAGE_DIR=/path/to/storage
```

---

## API Development

### Adding New Endpoints

1. Define Pydantic schema in `api/schemas.py`
2. Create route in `api/routes/`
3. Add business logic in `services/`
4. Register router in `api/main.py`

Example:

```python
# api/routes/new_feature.py
from fastapi import APIRouter, Depends
from vgap.api.schemas import NewFeatureRequest, NewFeatureResponse
from vgap.services.database import get_session

router = APIRouter(prefix="/new-feature", tags=["new-feature"])

@router.post("/", response_model=NewFeatureResponse)
async def create_feature(
    request: NewFeatureRequest,
    session: AsyncSession = Depends(get_session),
):
    # Implementation
    pass
```

### Authentication

All protected endpoints use JWT:

```python
from vgap.api.routes.auth import get_current_user, require_admin

@router.get("/protected")
async def protected_endpoint(
    current_user: User = Depends(get_current_user),
):
    pass

@router.post("/admin-only")
async def admin_endpoint(
    current_user: User = Depends(require_admin),
):
    pass
```

---

## Pipeline Development

### Adding New Pipeline Stages

1. Create module in `pipeline/`
2. Define dataclass for results
3. Implement main class with `run()` method
4. Integrate in `services/pipeline.py`

Example:

```python
# pipeline/new_stage.py
from dataclasses import dataclass
from pathlib import Path

@dataclass
class NewStageResult:
    output_path: Path
    metric1: float
    metric2: float

class NewStagePipeline:
    def __init__(self, param1: int = 10):
        self.param1 = param1
    
    def run(
        self,
        input_path: Path,
        output_dir: Path,
    ) -> NewStageResult:
        # Implementation
        output_dir.mkdir(parents=True, exist_ok=True)
        # ... process data ...
        return NewStageResult(
            output_path=output_dir / "output.txt",
            metric1=0.95,
            metric2=100.0,
        )
```

### Provenance Tracking

Always track provenance:

```python
from vgap.utils.provenance import ProvenanceCollector

collector = ProvenanceCollector(run_id=run_id)
collector.record_step(
    name="new_stage",
    tool="mytool",
    version="1.0.0",
    parameters={"param1": self.param1},
    inputs=[str(input_path)],
    outputs=[str(output_path)],
)
```

---

## Testing

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=vgap --cov-report=html

# Unit tests only
pytest tests/unit/

# Integration tests
pytest tests/integration/

# Regression tests
pytest tests/regression/
```

### Writing Tests

```python
# tests/unit/test_new_stage.py
import pytest
from vgap.pipeline.new_stage import NewStagePipeline

class TestNewStagePipeline:
    def test_run_success(self, tmp_path):
        pipeline = NewStagePipeline(param1=20)
        # Create test input
        input_file = tmp_path / "input.txt"
        input_file.write_text("test data")
        
        result = pipeline.run(input_file, tmp_path / "output")
        
        assert result.output_path.exists()
        assert result.metric1 > 0
```

---

## Frontend Development

### Adding New Pages

1. Create component in `src/pages/`
2. Add route in `src/App.tsx`
3. Add navigation link in `src/components/Layout.tsx`

### API Integration

Use React Query for data fetching:

```typescript
import { useQuery, useMutation } from '@tanstack/react-query'
import { runsApi } from '../utils/api'

function MyComponent() {
  const { data, isLoading } = useQuery({
    queryKey: ['runs'],
    queryFn: () => runsApi.list(),
  })
  
  const createMutation = useMutation({
    mutationFn: (data) => runsApi.create(data),
  })
}
```

---

## Deployment

### Docker Deployment

```bash
# Build and deploy
docker compose -f docker/docker-compose.yml up -d --build

# Check logs
docker compose logs -f

# Scale workers
docker compose up -d --scale vgap-worker=4
```

### Production Checklist

- [ ] Set strong `VGAP_SECRET_KEY`
- [ ] Configure HTTPS/TLS
- [ ] Set production database URL
- [ ] Configure backup jobs
- [ ] Set up monitoring alerts
- [ ] Review CORS settings
- [ ] Enable rate limiting
- [ ] Set up log rotation

---

## Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/new-feature`
3. Write tests for new functionality
4. Ensure all tests pass: `pytest`
5. Run linting: `ruff check .`
6. Submit pull request

### Code Style

- Python: Follow PEP 8, use type hints
- TypeScript: Use strict mode
- Commits: Follow conventional commits

---

## Support

- Issues: GitHub Issues
- Discussions: GitHub Discussions
- Email: support@vgap.example.com
