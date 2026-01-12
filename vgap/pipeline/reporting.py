"""
VGAP Report Generation Module

Generates publication-quality HTML and PDF reports.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = structlog.get_logger()


@dataclass
class ReportConfig:
    """Report generation configuration."""
    title: str = "Viral Genomics Analysis Report"
    include_figures: bool = True
    include_tables: bool = True
    include_provenance: bool = True
    include_methods: bool = True
    figure_format: str = "svg"  # svg or png
    figure_dpi: int = 300


class ReportData:
    """Container for all report data."""
    
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.generated_at = datetime.utcnow()
        
        # Run info
        self.run_name = ""
        self.run_description = ""
        self.user = ""
        self.mode = ""
        self.primer_scheme = ""
        
        # QC summary
        self.total_samples = 0
        self.passed_samples = 0
        self.failed_samples = 0
        self.samples: list[dict] = []
        
        # Variants summary
        self.total_variants = 0
        self.consensus_variants = 0
        self.minor_variants = 0
        self.variants_by_gene: dict[str, int] = {}
        
        # Lineage summary
        self.lineage_counts: dict[str, int] = {}
        
        # Coverage summary
        self.avg_depth = 0.0
        self.avg_coverage_10x = 0.0
        
        # Notable findings
        self.warnings: list[str] = []
        self.notable_mutations: list[str] = []
        
        # Provenance
        self.provenance: Optional[dict] = None
    
    def add_sample(
        self,
        sample_id: str,
        qc_metrics: dict,
        coverage: dict,
        variants: list,
        lineage: Optional[dict] = None,
    ):
        """Add sample data to report."""
        self.samples.append({
            "sample_id": sample_id,
            "qc": qc_metrics,
            "coverage": coverage,
            "variant_count": len(variants),
            "lineage": lineage,
        })
        self.total_samples += 1
        
        if qc_metrics.get("qc_pass", False):
            self.passed_samples += 1
        else:
            self.failed_samples += 1
    
    def compute_summaries(self):
        """Compute aggregate statistics."""
        if not self.samples:
            return
        
        # Coverage averages
        depths = [s["coverage"].get("mean_depth", 0) for s in self.samples]
        self.avg_depth = sum(depths) / len(depths) if depths else 0
        
        cov10x = [s["coverage"].get("coverage_10x", 0) for s in self.samples]
        self.avg_coverage_10x = sum(cov10x) / len(cov10x) if cov10x else 0
        
        # Lineage counts
        for s in self.samples:
            lineage = s.get("lineage", {})
            if lineage:
                lin = lineage.get("pangolin_lineage") or lineage.get("nextclade_clade") or "Unknown"
                self.lineage_counts[lin] = self.lineage_counts.get(lin, 0) + 1
    
    def to_dict(self) -> dict[str, Any]:
        """Export as dictionary for template rendering."""
        return {
            "run_id": self.run_id,
            "generated_at": self.generated_at.isoformat(),
            "run_name": self.run_name,
            "run_description": self.run_description,
            "user": self.user,
            "mode": self.mode,
            "primer_scheme": self.primer_scheme,
            "total_samples": self.total_samples,
            "passed_samples": self.passed_samples,
            "failed_samples": self.failed_samples,
            "samples": self.samples,
            "total_variants": self.total_variants,
            "consensus_variants": self.consensus_variants,
            "minor_variants": self.minor_variants,
            "variants_by_gene": self.variants_by_gene,
            "lineage_counts": self.lineage_counts,
            "avg_depth": self.avg_depth,
            "avg_coverage_10x": self.avg_coverage_10x,
            "warnings": self.warnings,
            "notable_mutations": self.notable_mutations,
            "provenance": self.provenance,
        }


class HTMLReportGenerator:
    """Generate HTML reports using Jinja2 templates."""
    
    TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - {{ run_id }}</title>
    <style>
        :root {
            --primary: #2563eb;
            --success: #16a34a;
            --warning: #ca8a04;
            --danger: #dc2626;
            --bg: #f8fafc;
            --card: #ffffff;
            --text: #1e293b;
            --muted: #64748b;
            --border: #e2e8f0;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 2rem; }
        .header {
            background: linear-gradient(135deg, var(--primary), #1d4ed8);
            color: white;
            padding: 3rem 2rem;
            margin-bottom: 2rem;
            border-radius: 1rem;
        }
        .header h1 { font-size: 2rem; margin-bottom: 0.5rem; }
        .header .meta { opacity: 0.9; font-size: 0.9rem; }
        .card {
            background: var(--card);
            border-radius: 0.75rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        }
        .card h2 {
            font-size: 1.25rem;
            color: var(--primary);
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid var(--border);
        }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem; }
        .stat {
            text-align: center;
            padding: 1rem;
            background: var(--bg);
            border-radius: 0.5rem;
        }
        .stat-value { font-size: 2rem; font-weight: bold; color: var(--primary); }
        .stat-label { color: var(--muted); font-size: 0.85rem; }
        .badge {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .badge-success { background: #dcfce7; color: var(--success); }
        .badge-warning { background: #fef3c7; color: var(--warning); }
        .badge-danger { background: #fee2e2; color: var(--danger); }
        table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
        th, td { padding: 0.75rem; text-align: left; border-bottom: 1px solid var(--border); }
        th { background: var(--bg); font-weight: 600; }
        tr:hover { background: var(--bg); }
        .warning-box {
            background: #fef3c7;
            border-left: 4px solid var(--warning);
            padding: 1rem;
            margin-bottom: 1rem;
            border-radius: 0 0.5rem 0.5rem 0;
        }
        .lineage-chart { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 1rem; }
        .lineage-item {
            background: var(--bg);
            padding: 0.5rem 1rem;
            border-radius: 0.5rem;
            font-size: 0.85rem;
        }
        .lineage-item strong { color: var(--primary); }
        pre {
            background: #1e293b;
            color: #e2e8f0;
            padding: 1rem;
            border-radius: 0.5rem;
            overflow-x: auto;
            font-size: 0.8rem;
        }
        @media print {
            .container { max-width: 100%; }
            .card { break-inside: avoid; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{{ title }}</h1>
            <div class="meta">
                <strong>Run ID:</strong> {{ run_id }} | 
                <strong>Generated:</strong> {{ generated_at }} |
                <strong>Mode:</strong> {{ mode }}
                {% if primer_scheme %} | <strong>Primer Scheme:</strong> {{ primer_scheme }}{% endif %}
            </div>
        </div>

        <!-- Executive Summary -->
        <div class="card">
            <h2>📊 Executive Summary</h2>
            <div class="grid">
                <div class="stat">
                    <div class="stat-value">{{ total_samples }}</div>
                    <div class="stat-label">Total Samples</div>
                </div>
                <div class="stat">
                    <div class="stat-value" style="color: var(--success)">{{ passed_samples }}</div>
                    <div class="stat-label">Passed QC</div>
                </div>
                <div class="stat">
                    <div class="stat-value" style="color: var(--danger)">{{ failed_samples }}</div>
                    <div class="stat-label">Failed QC</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{{ "%.1f"|format(avg_depth) }}×</div>
                    <div class="stat-label">Mean Depth</div>
                </div>
            </div>
            
            {% if warnings %}
            <div class="warning-box" style="margin-top: 1rem;">
                <strong>⚠️ Warnings:</strong>
                <ul>{% for w in warnings %}<li>{{ w }}</li>{% endfor %}</ul>
            </div>
            {% endif %}
        </div>

        <!-- Lineage Distribution -->
        {% if lineage_counts %}
        <div class="card">
            <h2>🧬 Lineage Distribution</h2>
            <div class="lineage-chart">
                {% for lineage, count in lineage_counts.items() %}
                <div class="lineage-item">
                    <strong>{{ lineage }}</strong>: {{ count }} sample{% if count != 1 %}s{% endif %}
                </div>
                {% endfor %}
            </div>
        </div>
        {% endif %}

        <!-- Sample Results -->
        <div class="card">
            <h2>📋 Sample Results</h2>
            <table>
                <thead>
                    <tr>
                        <th>Sample ID</th>
                        <th>QC Status</th>
                        <th>Mean Depth</th>
                        <th>Coverage ≥10×</th>
                        <th>Variants</th>
                        <th>Lineage</th>
                    </tr>
                </thead>
                <tbody>
                {% for sample in samples %}
                <tr>
                    <td><strong>{{ sample.sample_id }}</strong></td>
                    <td>
                        {% if sample.qc.qc_pass %}
                        <span class="badge badge-success">PASS</span>
                        {% else %}
                        <span class="badge badge-danger">FAIL</span>
                        {% endif %}
                    </td>
                    <td>{{ "%.1f"|format(sample.coverage.mean_depth|default(0)) }}×</td>
                    <td>{{ "%.1f"|format((sample.coverage.coverage_10x|default(0)) * 100) }}%</td>
                    <td>{{ sample.variant_count }}</td>
                    <td>{{ sample.lineage.pangolin_lineage|default(sample.lineage.nextclade_clade)|default('—') if sample.lineage else '—' }}</td>
                </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>

        <!-- Methods -->
        {% if provenance %}
        <div class="card">
            <h2>📖 Methods</h2>
            <p>Analysis performed using the VGAP pipeline with the following software:</p>
            <table>
                <thead><tr><th>Software</th><th>Version</th></tr></thead>
                <tbody>
                {% for sw in provenance.software %}
                <tr><td>{{ sw.name }}</td><td>{{ sw.version }}</td></tr>
                {% endfor %}
                </tbody>
            </table>
            
            <h3 style="margin-top: 1.5rem; margin-bottom: 0.5rem;">Parameters</h3>
            <pre>{{ provenance.parameters | tojson(indent=2) }}</pre>
        </div>
        {% endif %}

        <!-- Provenance -->
        {% if provenance %}
        <div class="card">
            <h2>🔍 Provenance</h2>
            <p><strong>Run ID:</strong> {{ provenance.run_id }}</p>
            <p><strong>Timestamp:</strong> {{ provenance.timestamp }}</p>
            
            {% if provenance.random_seeds %}
            <h3 style="margin-top: 1rem;">Random Seeds</h3>
            <pre>{{ provenance.random_seeds | tojson(indent=2) }}</pre>
            {% endif %}
            
            <h3 style="margin-top: 1rem;">Output Checksums</h3>
            <pre>{{ provenance.outputs | tojson(indent=2) }}</pre>
        </div>
        {% endif %}

        <footer style="text-align: center; color: var(--muted); padding: 2rem; font-size: 0.85rem;">
            Generated by VGAP (Viral Genomics Analysis Platform) | {{ generated_at }}
        </footer>
    </div>
</body>
</html>
"""
    
    def __init__(self, template_dir: Optional[Path] = None):
        if template_dir and template_dir.exists():
            self.env = Environment(
                loader=FileSystemLoader(str(template_dir)),
                autoescape=select_autoescape(['html', 'xml'])
            )
        else:
            from jinja2 import BaseLoader
            self.env = Environment(loader=BaseLoader(), autoescape=True)
    
    def generate(
        self,
        data: ReportData,
        output_path: Path,
        config: Optional[ReportConfig] = None,
    ) -> Path:
        """Generate HTML report."""
        config = config or ReportConfig()
        
        template = self.env.from_string(self.TEMPLATE)
        
        context = data.to_dict()
        context["title"] = config.title
        
        html = template.render(**context)
        
        output_path.write_text(html)
        logger.info("Generated HTML report", path=str(output_path))
        
        return output_path


class FigureGenerator:
    """Generate publication-quality figures using Plotly."""
    
    def __init__(self, output_dir: Path, format: str = "svg", dpi: int = 300):
        self.output_dir = output_dir
        self.format = format
        self.dpi = dpi
        output_dir.mkdir(parents=True, exist_ok=True)
    
    def coverage_plot(self, depths: list[int], sample_id: str) -> Path:
        """Generate per-base coverage plot."""
        try:
            import plotly.graph_objects as go
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                y=depths,
                mode='lines',
                fill='tozeroy',
                line=dict(color='#2563eb', width=1),
                fillcolor='rgba(37, 99, 235, 0.3)',
            ))
            
            # Add threshold lines
            fig.add_hline(y=10, line_dash="dash", line_color="#16a34a",
                         annotation_text="10× threshold")
            fig.add_hline(y=30, line_dash="dash", line_color="#ca8a04",
                         annotation_text="30× threshold")
            
            fig.update_layout(
                title=f"Coverage - {sample_id}",
                xaxis_title="Genome Position",
                yaxis_title="Depth",
                template="plotly_white",
                height=400,
            )
            
            output_path = self.output_dir / f"{sample_id}_coverage.{self.format}"
            
            if self.format == "svg":
                fig.write_image(str(output_path), format="svg")
            else:
                fig.write_image(str(output_path), format="png", scale=self.dpi / 72)
            
            return output_path
            
        except ImportError:
            logger.warning("Plotly not available, skipping figure generation")
            return None
    
    def variant_lollipop(
        self,
        variants: list[dict],
        genome_length: int,
        sample_id: str,
    ) -> Path:
        """Generate variant lollipop plot."""
        try:
            import plotly.graph_objects as go
            
            fig = go.Figure()
            
            # Consensus variants
            consensus = [v for v in variants if v.get("is_consensus")]
            if consensus:
                fig.add_trace(go.Scatter(
                    x=[v["pos"] for v in consensus],
                    y=[v["allele_freq"] for v in consensus],
                    mode='markers',
                    marker=dict(size=10, color='#2563eb'),
                    name='Consensus',
                    text=[v.get("aa_change", f"{v['ref']}>{v['alt']}") for v in consensus],
                ))
            
            # Minor variants
            minor = [v for v in variants if v.get("is_minor")]
            if minor:
                fig.add_trace(go.Scatter(
                    x=[v["pos"] for v in minor],
                    y=[v["allele_freq"] for v in minor],
                    mode='markers',
                    marker=dict(size=6, color='#ca8a04', symbol='diamond'),
                    name='Minor',
                ))
            
            fig.update_layout(
                title=f"Variants - {sample_id}",
                xaxis_title="Genome Position",
                yaxis_title="Allele Frequency",
                xaxis=dict(range=[0, genome_length]),
                yaxis=dict(range=[0, 1]),
                template="plotly_white",
                height=300,
            )
            
            output_path = self.output_dir / f"{sample_id}_variants.{self.format}"
            fig.write_image(str(output_path), format=self.format)
            
            return output_path
            
        except Exception as e:
            logger.warning("Failed to generate variant chart", error=str(e))
            return None
    
    def lineage_pie(self, lineage_counts: dict[str, int]) -> Path:
        """Generate lineage distribution pie chart."""
        try:
            import plotly.graph_objects as go
            
            fig = go.Figure(data=[go.Pie(
                labels=list(lineage_counts.keys()),
                values=list(lineage_counts.values()),
                hole=0.4,
            )])
            
            fig.update_layout(
                title="Lineage Distribution",
                template="plotly_white",
            )
            
            output_path = self.output_dir / f"lineage_distribution.{self.format}"
            fig.write_image(str(output_path), format=self.format)
            
            return output_path
            
        except Exception as e:
            logger.warning("Failed to generate lineage chart", error=str(e))
            return None


class ReportPipeline:
    """Complete report generation pipeline."""
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.html_generator = HTMLReportGenerator()
        self.figure_generator = FigureGenerator(output_dir / "figures")
    
    def generate(
        self,
        run_id: str,
        samples_data: list[dict],
        provenance: Optional[dict] = None,
        config: Optional[ReportConfig] = None,
    ) -> dict[str, Path]:
        """Generate complete report package."""
        config = config or ReportConfig()
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Build report data
        data = ReportData(run_id)
        data.provenance = provenance
        
        for sample in samples_data:
            data.add_sample(
                sample_id=sample["sample_id"],
                qc_metrics=sample.get("qc", {}),
                coverage=sample.get("coverage", {}),
                variants=sample.get("variants", []),
                lineage=sample.get("lineage"),
            )
        
        data.compute_summaries()
        
        outputs = {}
        
        # Generate HTML report
        html_path = self.output_dir / "report.html"
        self.html_generator.generate(data, html_path, config)
        outputs["html"] = html_path
        
        # Generate figures
        if config.include_figures:
            if data.lineage_counts:
                fig = self.figure_generator.lineage_pie(data.lineage_counts)
                if fig:
                    outputs["lineage_chart"] = fig
        
        # Export data tables
        samples_tsv = self.output_dir / "samples_summary.tsv"
        self._export_samples_tsv(data, samples_tsv)
        outputs["samples_tsv"] = samples_tsv
        
        logger.info("Report generation complete", run_id=run_id, outputs=len(outputs))
        
        return outputs
    
    def _export_samples_tsv(self, data: ReportData, output_path: Path):
        """Export samples summary as TSV."""
        with open(output_path, 'w') as f:
            headers = ["sample_id", "qc_pass", "mean_depth", "coverage_10x", 
                      "variant_count", "lineage"]
            f.write('\t'.join(headers) + '\n')
            
            for s in data.samples:
                row = [
                    s["sample_id"],
                    str(s["qc"].get("qc_pass", False)),
                    f"{s['coverage'].get('mean_depth', 0):.1f}",
                    f"{s['coverage'].get('coverage_10x', 0):.3f}",
                    str(s.get("variant_count", 0)),
                    s["lineage"].get("pangolin_lineage", "") if s.get("lineage") else "",
                ]
                f.write('\t'.join(row) + '\n')
