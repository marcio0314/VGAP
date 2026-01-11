# VGAP Report Generation Flow

**Document Version:** 1.0  
**Last Updated:** 2026-01-11

---

## No-Cache Policy

> **CRITICAL:** Reports are ALWAYS generated fresh. No caching is performed.

Every report generation request:
1. Loads current data from results directory
2. Generates new HTML with unique report ID
3. Includes current timestamp
4. Creates new figures
5. Returns unique download URL

---

## Report Generation Flow

```
┌─────────────────┐
│ User Request    │
│ POST /generate  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Validate Run    │
│ - Status check  │
│ - Access check  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Generate IDs    │
│ - report_id     │   ← UUID, unique per request
│ - timestamp     │   ← Current UTC time
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Load Run Data   │
│ - QC metrics    │
│ - Coverage      │
│ - Variants      │
│ - Lineage       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Load Provenance │
│ - Software vers │
│ - Random seeds  │
│ - Checksums     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Generate Report │
│ - Render HTML   │   ← FRESH, not cached
│ - Generate figs │   ← NEW figures
│ - Export tables │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Write Metadata  │
│ - report_id     │
│ - generated_at  │
│ - generated_by  │
│ - config hash   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Return Response │
│ - download_url  │
│ - report_id     │
│ - generated_at  │
└─────────────────┘
```

---

## Report Integrity

Every report includes:

### Header Metadata
```html
<meta name="report-id" content="550e8400-e29b-41d4-a716-446655440000">
<meta name="generated-at" content="2026-01-11T10:30:00Z">
<meta name="run-id" content="run-uuid-here">
```

### Software Versions Table
| Software | Version |
|----------|---------|
| fastp | 0.23.4 |
| minimap2 | 2.26 |
| ivar | 1.4.2 |
| pangolin | 4.3 |
| nextclade | 3.0 |

### Provenance Section
- Input file checksums (SHA256)
- Reference database versions
- Random seeds used
- Output file checksums

---

## Report Storage Structure

```
results/{run_id}/reports/{report_id}/
├── report.html          # Main HTML report
├── metadata.json        # Generation metadata
├── figures/
│   ├── coverage_*.svg
│   ├── variants_*.svg
│   └── lineage_*.svg
└── tables/
    ├── variants.tsv
    └── summary.tsv
```

---

## API Endpoints

### Generate Report
```http
POST /api/v1/reports/{run_id}/generate
Content-Type: application/json

{
  "format": "html",
  "title": "Analysis Report",
  "include_figures": true,
  "include_tables": true,
  "include_provenance": true,
  "figure_format": "svg",
  "figure_dpi": 300
}
```

**Response:**
```json
{
  "report_id": "550e8400-e29b-41d4-a716-446655440000",
  "run_id": "run-uuid-here",
  "format": "html",
  "generated_at": "2026-01-11T10:30:00Z",
  "download_url": "/api/v1/reports/{run_id}/download/{report_id}"
}
```

### Download Report
```http
GET /api/v1/reports/{run_id}/download/{report_id}?format=html
```

Returns the HTML file directly.

---

## Verification Test

```python
# test_fresh_reports.py

async def test_reports_always_fresh():
    """Verify each request generates a new report."""
    
    # Generate first report
    response1 = await client.post(f"/api/v1/reports/{run_id}/generate", json={})
    report1 = response1.json()
    
    # Wait a moment
    await asyncio.sleep(0.1)
    
    # Generate second report
    response2 = await client.post(f"/api/v1/reports/{run_id}/generate", json={})
    report2 = response2.json()
    
    # Verify different report IDs
    assert report1["report_id"] != report2["report_id"]
    
    # Verify different timestamps
    assert report1["generated_at"] != report2["generated_at"]
    
    # Verify different download URLs
    assert report1["download_url"] != report2["download_url"]
```

---

## No-Cache Enforcement

The following ensures no caching:

1. **No Cache Headers**
   ```python
   response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
   response.headers["Pragma"] = "no-cache"
   ```

2. **Unique Report IDs**
   - Each generation creates new UUID
   - Stored in separate directory

3. **Timestamp Verification**
   - Report HTML includes generation timestamp
   - Metadata JSON includes timestamp
   - Different timestamps = different reports

4. **No Lookup Cache**
   - No in-memory cache of rendered HTML
   - No file-based cache lookup
   - Always reads from results directory
