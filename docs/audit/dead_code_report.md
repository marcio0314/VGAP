# Dead Code Analysis Report

**Analysis Date:** 2026-01-11  
**Status:** ✅ CLEAN - No dead code detected

---

## Summary

| Metric | Value | Status |
|--------|-------|--------|
| Orphan files | 0 | ✅ |
| Unreferenced functions | 0 | ✅ |
| Unused imports | 0 | ✅ |
| Unreachable code | 0 | ✅ |

---

## Analysis Method

1. **AST parsing** of all 32 Python files
2. **Import graph construction** for all modules
3. **Function reference tracing** from entry points
4. **Manual verification** of API route mappings

---

## File Reference Map

### Entry Points

| Entry | File | Status |
|-------|------|--------|
| API Server | `vgap/api/main.py` | ✅ Active |
| Celery Worker | `vgap/worker.py` | ✅ Active |

### Core Modules (All Referenced)

| Module | Referenced By | Status |
|--------|---------------|--------|
| `vgap.config` | 8 files | ✅ |
| `vgap.models` | 6 files | ✅ |
| `vgap.api.schemas` | 5 files | ✅ |
| `vgap.services.database` | 4 files | ✅ |
| `vgap.services.user_service` | 2 files | ✅ |
| `vgap.services.run_service` | 2 files | ✅ |
| `vgap.services.upload` | 2 files | ✅ |
| `vgap.validators.preflight` | 3 files | ✅ |
| `vgap.utils.provenance` | 4 files | ✅ |

### Pipeline Modules (All Referenced)

| Module | Called By | Status |
|--------|-----------|--------|
| `vgap.pipeline.qc` | `services/pipeline.py` | ✅ |
| `vgap.pipeline.mapping` | `services/pipeline.py` | ✅ |
| `vgap.pipeline.variants` | `services/pipeline.py` | ✅ |
| `vgap.pipeline.lineage` | `services/pipeline.py` | ✅ |
| `vgap.pipeline.phylogeny` | `services/pipeline.py` | ✅ |
| `vgap.pipeline.assembly` | `services/pipeline.py` | ✅ |
| `vgap.pipeline.comparative` | `services/pipeline.py` | ✅ |
| `vgap.pipeline.reporting` | `services/pipeline.py`, `routes/reports.py` | ✅ |

---

## API Route Coverage

| Route File | Functions | Mapped to Endpoints | Unmapped |
|------------|-----------|---------------------|----------|
| `auth.py` | 8 | 4 | 4 (helpers) |
| `runs.py` | 10 | 8 | 2 (helpers) |
| `samples.py` | 9 | 7 | 2 (helpers) |
| `reports.py` | 5 | 5 | 0 |
| `admin.py` | 13 | 9 | 4 (helpers) |

All unmapped functions are legitimate helper functions (e.g., `run_to_response()`, `sample_to_response()`).

---

## Orphan File Check

Files not imported by any module:

```
None detected
```

Test files (intentionally standalone):
- `tests/unit/test_api.py`
- `tests/unit/test_validators.py`
- `tests/unit/test_provenance.py`
- `tests/integration/test_pipeline.py`
- `tests/conftest.py`
- `tests/fixtures/__init__.py`

---

## Conclusion

**No dead code found.** All modules, functions, and imports are actively used in the codebase.
