"""
VGAP PDF Export Module

Generates publication-quality PDF reports using WeasyPrint.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = structlog.get_logger()

# Check if weasyprint is available
try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False
    logger.warning("WeasyPrint not available, PDF export disabled")


@dataclass
class PDFConfig:
    """PDF generation configuration."""
    
    title: str = "VGAP Analysis Report"
    author: str = "VGAP Platform"
    page_size: str = "A4"
    orientation: str = "portrait"
    margin: str = "1.5cm"
    include_toc: bool = True
    include_provenance: bool = True
    include_figures: bool = True
    figure_dpi: int = 150
    font_family: str = "Inter, Helvetica, Arial, sans-serif"


class PDFExporter:
    """Export VGAP reports to PDF format."""
    
    CSS_TEMPLATE = """
    @page {
        size: %(page_size)s %(orientation)s;
        margin: %(margin)s;
        
        @top-center {
            content: "%(title)s";
            font-size: 9pt;
            color: #64748b;
        }
        
        @bottom-right {
            content: "Page " counter(page) " of " counter(pages);
            font-size: 9pt;
            color: #64748b;
        }
        
        @bottom-left {
            content: "Generated: %(date)s";
            font-size: 9pt;
            color: #64748b;
        }
    }
    
    body {
        font-family: %(font_family)s;
        font-size: 10pt;
        line-height: 1.5;
        color: #1f2937;
    }
    
    h1 {
        font-size: 24pt;
        color: #0f172a;
        border-bottom: 2px solid #0ea5e9;
        padding-bottom: 8pt;
        margin-top: 20pt;
        margin-bottom: 16pt;
    }
    
    h2 {
        font-size: 16pt;
        color: #1e293b;
        margin-top: 18pt;
        margin-bottom: 10pt;
        page-break-after: avoid;
    }
    
    h3 {
        font-size: 12pt;
        color: #334155;
        margin-top: 14pt;
        margin-bottom: 8pt;
        page-break-after: avoid;
    }
    
    table {
        width: 100%%;
        border-collapse: collapse;
        margin: 12pt 0;
        font-size: 9pt;
        page-break-inside: avoid;
    }
    
    th {
        background-color: #f1f5f9;
        color: #475569;
        font-weight: 600;
        text-align: left;
        padding: 8pt;
        border: 1px solid #e2e8f0;
    }
    
    td {
        padding: 6pt 8pt;
        border: 1px solid #e2e8f0;
        vertical-align: top;
    }
    
    tr:nth-child(even) {
        background-color: #f8fafc;
    }
    
    .status-pass { color: #16a34a; font-weight: 600; }
    .status-warn { color: #d97706; font-weight: 600; }
    .status-fail { color: #dc2626; font-weight: 600; }
    
    .metric-value {
        font-size: 18pt;
        font-weight: 700;
        color: #0ea5e9;
    }
    
    .metric-label {
        font-size: 9pt;
        color: #64748b;
    }
    
    .metric-card {
        display: inline-block;
        width: 22%%;
        text-align: center;
        padding: 12pt;
        margin: 6pt;
        background: #f8fafc;
        border-radius: 8pt;
    }
    
    figure {
        margin: 16pt 0;
        text-align: center;
        page-break-inside: avoid;
    }
    
    figure img {
        max-width: 100%%;
        height: auto;
    }
    
    figcaption {
        font-size: 9pt;
        color: #64748b;
        margin-top: 8pt;
    }
    
    .toc {
        page-break-after: always;
    }
    
    .toc h2 {
        border-bottom: 1px solid #e2e8f0;
    }
    
    .toc-item {
        padding: 4pt 0;
        border-bottom: 1px dotted #e2e8f0;
    }
    
    .toc-level-1 { margin-left: 0; }
    .toc-level-2 { margin-left: 16pt; font-size: 9pt; }
    
    .provenance {
        font-size: 8pt;
        background: #f1f5f9;
        padding: 12pt;
        border-radius: 4pt;
        margin-top: 20pt;
    }
    
    .provenance h3 {
        margin-top: 0;
        font-size: 10pt;
    }
    
    code {
        font-family: "SF Mono", Monaco, monospace;
        font-size: 8pt;
        background: #f1f5f9;
        padding: 2pt 4pt;
        border-radius: 2pt;
    }
    
    .page-break {
        page-break-before: always;
    }
    
    .summary-box {
        background: linear-gradient(135deg, #0ea5e9 0%%, #0284c7 100%%);
        color: white;
        padding: 16pt;
        border-radius: 8pt;
        margin: 16pt 0;
    }
    
    .summary-box h2 {
        color: white;
        margin-top: 0;
    }
    """
    
    HTML_TEMPLATE = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>{{ title }}</title>
    </head>
    <body>
        <!-- Title Page -->
        <div style="text-align: center; padding-top: 200pt;">
            <h1 style="border: none; font-size: 32pt;">{{ title }}</h1>
            <p style="font-size: 14pt; color: #64748b;">{{ run_name }}</p>
            <p style="font-size: 12pt; color: #94a3b8;">Generated: {{ generated_at }}</p>
            <p style="font-size: 12pt; color: #94a3b8;">Run ID: {{ run_id }}</p>
        </div>
        
        <div class="page-break"></div>
        
        {% if include_toc %}
        <!-- Table of Contents -->
        <div class="toc">
            <h2>Table of Contents</h2>
            <div class="toc-item toc-level-1">1. Executive Summary</div>
            <div class="toc-item toc-level-1">2. Sample Results</div>
            {% for sample in samples %}
            <div class="toc-item toc-level-2">2.{{ loop.index }}. {{ sample.sample_id }}</div>
            {% endfor %}
            <div class="toc-item toc-level-1">3. Quality Control</div>
            <div class="toc-item toc-level-1">4. Variant Analysis</div>
            <div class="toc-item toc-level-1">5. Lineage Assignment</div>
            {% if include_provenance %}
            <div class="toc-item toc-level-1">6. Provenance</div>
            {% endif %}
        </div>
        {% endif %}
        
        <!-- Executive Summary -->
        <h1>1. Executive Summary</h1>
        
        <div class="summary-box">
            <h2>Run Overview</h2>
            <p>{{ samples|length }} samples analyzed</p>
            <p>{{ completed_count }} completed successfully</p>
        </div>
        
        <div style="margin: 20pt 0;">
            <div class="metric-card">
                <div class="metric-value">{{ samples|length }}</div>
                <div class="metric-label">Total Samples</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{{ avg_coverage|round(1) }}x</div>
                <div class="metric-label">Mean Coverage</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{{ total_variants }}</div>
                <div class="metric-label">Total Variants</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{{ unique_lineages }}</div>
                <div class="metric-label">Unique Lineages</div>
            </div>
        </div>
        
        <div class="page-break"></div>
        
        <!-- Sample Results -->
        <h1>2. Sample Results</h1>
        
        <table>
            <thead>
                <tr>
                    <th>Sample ID</th>
                    <th>Status</th>
                    <th>Mean Depth</th>
                    <th>Coverage 10x</th>
                    <th>Variants</th>
                    <th>Lineage</th>
                </tr>
            </thead>
            <tbody>
                {% for sample in samples %}
                <tr>
                    <td>{{ sample.sample_id }}</td>
                    <td class="status-{{ 'pass' if sample.qc_pass else 'warn' }}">
                        {{ 'PASS' if sample.qc_pass else 'WARN' }}
                    </td>
                    <td>{{ sample.mean_depth|round(1) }}x</td>
                    <td>{{ (sample.coverage_10x * 100)|round(1) }}%</td>
                    <td>{{ sample.variant_count }}</td>
                    <td>{{ sample.lineage or 'N/A' }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        
        <div class="page-break"></div>
        
        <!-- Quality Control -->
        <h1>3. Quality Control</h1>
        
        <h2>Read Statistics</h2>
        <table>
            <thead>
                <tr>
                    <th>Sample ID</th>
                    <th>Raw Reads</th>
                    <th>Trimmed Reads</th>
                    <th>Q30 Rate</th>
                    <th>GC Content</th>
                    <th>Mapping Rate</th>
                </tr>
            </thead>
            <tbody>
                {% for sample in samples %}
                <tr>
                    <td>{{ sample.sample_id }}</td>
                    <td>{{ "{:,}".format(sample.raw_reads) }}</td>
                    <td>{{ "{:,}".format(sample.trimmed_reads) }}</td>
                    <td>{{ (sample.q30_rate * 100)|round(1) }}%</td>
                    <td>{{ (sample.gc_content * 100)|round(1) }}%</td>
                    <td>{{ (sample.mapping_rate * 100)|round(1) }}%</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        
        {% if include_figures and figures.coverage %}
        <h2>Coverage Distribution</h2>
        <figure>
            <img src="{{ figures.coverage }}" alt="Coverage Plot">
            <figcaption>Figure 1: Coverage depth across the genome for all samples.</figcaption>
        </figure>
        {% endif %}
        
        <div class="page-break"></div>
        
        <!-- Variant Analysis -->
        <h1>4. Variant Analysis</h1>
        
        <h2>Consensus Variants</h2>
        <table>
            <thead>
                <tr>
                    <th>Sample</th>
                    <th>Position</th>
                    <th>Ref</th>
                    <th>Alt</th>
                    <th>Gene</th>
                    <th>AA Change</th>
                    <th>Freq</th>
                </tr>
            </thead>
            <tbody>
                {% for variant in consensus_variants[:50] %}
                <tr>
                    <td>{{ variant.sample_id }}</td>
                    <td>{{ variant.pos }}</td>
                    <td><code>{{ variant.ref }}</code></td>
                    <td><code>{{ variant.alt }}</code></td>
                    <td>{{ variant.gene or '-' }}</td>
                    <td>{{ variant.aa_change or '-' }}</td>
                    <td>{{ (variant.allele_freq * 100)|round(1) }}%</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        
        {% if consensus_variants|length > 50 %}
        <p><em>Showing first 50 of {{ consensus_variants|length }} variants.</em></p>
        {% endif %}
        
        <div class="page-break"></div>
        
        <!-- Lineage Assignment -->
        <h1>5. Lineage Assignment</h1>
        
        <table>
            <thead>
                <tr>
                    <th>Sample ID</th>
                    <th>Pangolin Lineage</th>
                    <th>Nextclade Clade</th>
                    <th>Scorpio Call</th>
                    <th>QC Status</th>
                </tr>
            </thead>
            <tbody>
                {% for sample in samples %}
                <tr>
                    <td>{{ sample.sample_id }}</td>
                    <td>{{ sample.lineage or 'N/A' }}</td>
                    <td>{{ sample.clade or 'N/A' }}</td>
                    <td>{{ sample.scorpio or '-' }}</td>
                    <td class="status-{{ sample.lineage_qc_status|lower if sample.lineage_qc_status else 'pass' }}">
                        {{ sample.lineage_qc_status or 'PASS' }}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        
        {% if include_provenance %}
        <div class="page-break"></div>
        
        <!-- Provenance -->
        <h1>6. Provenance</h1>
        
        <div class="provenance">
            <h3>Software Versions</h3>
            <table>
                <thead>
                    <tr><th>Software</th><th>Version</th></tr>
                </thead>
                <tbody>
                    {% for sw in software_versions %}
                    <tr>
                        <td>{{ sw.name }}</td>
                        <td><code>{{ sw.version }}</code></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            
            <h3>Run Parameters</h3>
            <table>
                <tbody>
                    <tr><td>Mode</td><td>{{ parameters.mode }}</td></tr>
                    <tr><td>Primer Scheme</td><td>{{ parameters.primer_scheme or 'N/A' }}</td></tr>
                    <tr><td>Min Depth</td><td>{{ parameters.min_depth }}</td></tr>
                    <tr><td>Min Allele Freq</td><td>{{ parameters.min_allele_freq }}</td></tr>
                </tbody>
            </table>
            
            <h3>Pipeline Execution</h3>
            <p>Run ID: <code>{{ run_id }}</code></p>
            <p>Started: {{ started_at }}</p>
            <p>Completed: {{ completed_at }}</p>
        </div>
        {% endif %}
        
    </body>
    </html>
    """
    
    def __init__(self, config: Optional[PDFConfig] = None):
        self.config = config or PDFConfig()
    
    def export(
        self,
        html_path: Path,
        output_path: Path,
    ) -> Optional[Path]:
        """
        Export HTML report to PDF.
        
        Args:
            html_path: Path to HTML report
            output_path: Output PDF path
        
        Returns:
            Path to PDF or None if WeasyPrint unavailable
        """
        if not WEASYPRINT_AVAILABLE:
            logger.warning("WeasyPrint not available, skipping PDF export")
            return None
        
        try:
            css = CSS(string=self.CSS_TEMPLATE % {
                "page_size": self.config.page_size,
                "orientation": self.config.orientation,
                "margin": self.config.margin,
                "title": self.config.title,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "font_family": self.config.font_family,
            })
            
            html = HTML(filename=str(html_path))
            html.write_pdf(str(output_path), stylesheets=[css])
            
            logger.info("PDF exported", path=str(output_path))
            return output_path
            
        except Exception as e:
            logger.exception("PDF export failed", error=str(e))
            return None
    
    def generate_pdf(
        self,
        data: Dict[str, Any],
        output_path: Path,
    ) -> Optional[Path]:
        """
        Generate PDF directly from data.
        
        Args:
            data: Report data dict
            output_path: Output PDF path
        
        Returns:
            Path to PDF or None if failed
        """
        if not WEASYPRINT_AVAILABLE:
            logger.warning("WeasyPrint not available, skipping PDF generation")
            return None
        
        try:
            # Render HTML template
            from jinja2 import Template
            template = Template(self.HTML_TEMPLATE)
            
            # Prepare template data
            samples = data.get("samples", [])
            completed_count = sum(1 for s in samples if s.get("qc_pass", False))
            avg_coverage = sum(s.get("mean_depth", 0) for s in samples) / len(samples) if samples else 0
            total_variants = sum(s.get("variant_count", 0) for s in samples)
            unique_lineages = len(set(s.get("lineage") for s in samples if s.get("lineage")))
            
            # Collect consensus variants
            consensus_variants = []
            for s in samples:
                for v in s.get("variants", []):
                    if v.get("is_consensus", True):
                        v["sample_id"] = s["sample_id"]
                        consensus_variants.append(v)
            
            html_content = template.render(
                title=self.config.title,
                run_name=data.get("run_name", "Analysis"),
                run_id=data.get("run_id", "N/A"),
                generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                include_toc=self.config.include_toc,
                include_provenance=self.config.include_provenance,
                include_figures=self.config.include_figures,
                samples=samples,
                completed_count=completed_count,
                avg_coverage=avg_coverage,
                total_variants=total_variants,
                unique_lineages=unique_lineages,
                consensus_variants=consensus_variants,
                figures=data.get("figures", {}),
                software_versions=data.get("provenance", {}).get("software", []),
                parameters=data.get("parameters", {}),
                started_at=data.get("started_at", "N/A"),
                completed_at=data.get("completed_at", "N/A"),
            )
            
            # Generate PDF
            css = CSS(string=self.CSS_TEMPLATE % {
                "page_size": self.config.page_size,
                "orientation": self.config.orientation,
                "margin": self.config.margin,
                "title": self.config.title,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "font_family": self.config.font_family,
            })
            
            html = HTML(string=html_content)
            html.write_pdf(str(output_path), stylesheets=[css])
            
            logger.info("PDF generated", path=str(output_path))
            return output_path
            
        except Exception as e:
            logger.exception("PDF generation failed", error=str(e))
            return None
