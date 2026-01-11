"""
VGAP Interactive Visualization Module

Generates interactive visualizations using Plotly for web-based reports.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger()

# Check if plotly is available
try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    logger.warning("Plotly not available, interactive visualizations disabled")


class InteractiveVisualizer:
    """Generate interactive visualizations for VGAP reports."""
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def coverage_plot(
        self,
        coverage_data: Dict[str, List[Dict]],
        sample_ids: List[str],
        output_name: str = "coverage_interactive",
    ) -> Optional[Path]:
        """
        Create interactive coverage plot.
        
        Args:
            coverage_data: Dict mapping sample_id to list of {pos, depth}
            sample_ids: List of sample IDs to include
            output_name: Output filename (without extension)
        
        Returns:
            Path to HTML file or None if Plotly unavailable
        """
        if not PLOTLY_AVAILABLE:
            return None
        
        fig = go.Figure()
        
        for sample_id in sample_ids:
            data = coverage_data.get(sample_id, [])
            if not data:
                continue
            
            positions = [d["pos"] for d in data]
            depths = [d["depth"] for d in data]
            
            fig.add_trace(go.Scatter(
                x=positions,
                y=depths,
                mode='lines',
                name=sample_id,
                hovertemplate=(
                    f"<b>{sample_id}</b><br>"
                    "Position: %{x}<br>"
                    "Depth: %{y}<br>"
                    "<extra></extra>"
                ),
            ))
        
        fig.update_layout(
            title="Coverage Depth Across Genome",
            xaxis_title="Genomic Position",
            yaxis_title="Coverage Depth",
            yaxis_type="log",
            hovermode="x unified",
            template="plotly_white",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
            ),
        )
        
        # Add threshold lines
        fig.add_hline(y=10, line_dash="dash", line_color="orange", 
                      annotation_text="10x threshold")
        fig.add_hline(y=100, line_dash="dash", line_color="green",
                      annotation_text="100x threshold")
        
        output_path = self.output_dir / f"{output_name}.html"
        fig.write_html(str(output_path), include_plotlyjs='cdn')
        
        return output_path
    
    def variant_scatter(
        self,
        variants: List[Dict],
        output_name: str = "variants_interactive",
    ) -> Optional[Path]:
        """
        Create interactive variant scatter plot.
        
        Args:
            variants: List of variant dicts with pos, af, depth, gene, aa_change
            output_name: Output filename
        
        Returns:
            Path to HTML file
        """
        if not PLOTLY_AVAILABLE:
            return None
        
        if not variants:
            return None
        
        fig = px.scatter(
            variants,
            x="pos",
            y="allele_freq",
            size="depth",
            color="gene",
            hover_data=["ref", "alt", "aa_change", "depth"],
            title="Variant Distribution",
            labels={
                "pos": "Genomic Position",
                "allele_freq": "Allele Frequency",
                "depth": "Read Depth",
                "gene": "Gene",
            },
        )
        
        fig.update_layout(
            template="plotly_white",
            xaxis=dict(
                rangeslider=dict(visible=True),
            ),
        )
        
        # Add consensus threshold line
        fig.add_hline(y=0.5, line_dash="dash", line_color="red",
                      annotation_text="Consensus threshold")
        
        output_path = self.output_dir / f"{output_name}.html"
        fig.write_html(str(output_path), include_plotlyjs='cdn')
        
        return output_path
    
    def lineage_sunburst(
        self,
        lineages: List[Dict],
        output_name: str = "lineage_sunburst",
    ) -> Optional[Path]:
        """
        Create interactive sunburst chart of lineage distribution.
        
        Args:
            lineages: List of dicts with sample_id, lineage, clade
            output_name: Output filename
        
        Returns:
            Path to HTML file
        """
        if not PLOTLY_AVAILABLE:
            return None
        
        if not lineages:
            return None
        
        # Build hierarchy
        hierarchy = []
        for lin in lineages:
            lineage = lin.get("lineage", "Unknown")
            clade = lin.get("clade", "Unknown")
            
            # Parse lineage hierarchy (e.g., BA.2.86.1 -> BA > BA.2 > BA.2.86 > BA.2.86.1)
            parts = lineage.split(".")
            for i in range(1, len(parts) + 1):
                parent = ".".join(parts[:i-1]) if i > 1 else clade
                current = ".".join(parts[:i])
                hierarchy.append({
                    "id": current,
                    "parent": parent,
                    "value": 1 if i == len(parts) else 0,
                })
        
        # Deduplicate and sum values
        unique = {}
        for h in hierarchy:
            key = h["id"]
            if key in unique:
                unique[key]["value"] += h["value"]
            else:
                unique[key] = h
        
        df_data = list(unique.values())
        
        if df_data:
            fig = go.Figure(go.Sunburst(
                ids=[d["id"] for d in df_data],
                labels=[d["id"].split(".")[-1] if "." in d["id"] else d["id"] for d in df_data],
                parents=[d["parent"] for d in df_data],
                values=[d["value"] for d in df_data],
                branchvalues="total",
            ))
            
            fig.update_layout(
                title="Lineage Distribution",
                template="plotly_white",
            )
            
            output_path = self.output_dir / f"{output_name}.html"
            fig.write_html(str(output_path), include_plotlyjs='cdn')
            
            return output_path
        
        return None
    
    def qc_heatmap(
        self,
        qc_data: List[Dict],
        output_name: str = "qc_heatmap",
    ) -> Optional[Path]:
        """
        Create interactive QC metrics heatmap.
        
        Args:
            qc_data: List of QC metric dicts per sample
            output_name: Output filename
        
        Returns:
            Path to HTML file
        """
        if not PLOTLY_AVAILABLE:
            return None
        
        if not qc_data:
            return None
        
        # Extract sample IDs and metrics
        sample_ids = [d.get("sample_id", f"Sample_{i}") for i, d in enumerate(qc_data)]
        
        metrics = ["q30_rate", "gc_content", "mapping_rate", "coverage_10x", "mean_depth"]
        metric_labels = ["Q30 Rate", "GC Content", "Mapping Rate", "Coverage 10x", "Mean Depth"]
        
        # Normalize values for heatmap
        z_values = []
        for metric in metrics:
            row = []
            values = [d.get(metric, 0) for d in qc_data]
            max_val = max(values) if values else 1
            for v in values:
                # Normalize to 0-1
                normalized = v / max_val if max_val > 0 else 0
                row.append(normalized)
            z_values.append(row)
        
        fig = go.Figure(data=go.Heatmap(
            z=z_values,
            x=sample_ids,
            y=metric_labels,
            colorscale="RdYlGn",
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Sample: %{x}<br>"
                "Value: %{z:.2f}<br>"
                "<extra></extra>"
            ),
        ))
        
        fig.update_layout(
            title="QC Metrics Heatmap",
            xaxis_title="Sample",
            yaxis_title="Metric",
            template="plotly_white",
        )
        
        output_path = self.output_dir / f"{output_name}.html"
        fig.write_html(str(output_path), include_plotlyjs='cdn')
        
        return output_path
    
    def phylogenetic_tree(
        self,
        tree_newick: str,
        metadata: Dict[str, Dict],
        output_name: str = "tree_interactive",
    ) -> Optional[Path]:
        """
        Create interactive phylogenetic tree visualization.
        
        Note: Uses a radial layout suitable for web display.
        
        Args:
            tree_newick: Newick tree string
            metadata: Dict mapping sample_id to metadata
            output_name: Output filename
        
        Returns:
            Path to HTML file
        """
        if not PLOTLY_AVAILABLE:
            return None
        
        # For complex tree visualization, we create a simple D3-based HTML
        html_content = f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Phylogenetic Tree</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <script src="https://unpkg.com/phylotree"></script>
    <link rel="stylesheet" href="https://unpkg.com/phylotree/dist/phylotree.css">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 20px; }}
        #tree {{ width: 100%; height: 800px; border: 1px solid #e5e7eb; border-radius: 8px; }}
        h1 {{ color: #1f2937; }}
    </style>
</head>
<body>
    <h1>Phylogenetic Tree</h1>
    <div id="tree"></div>
    <script>
        const newick = `{tree_newick}`;
        const metadata = {json.dumps(metadata)};
        
        const tree = new phylotree.phylotree(newick);
        tree.render({{
            container: "#tree",
            width: 1200,
            height: 800,
            "show-scale": true,
            "align-tips": true,
            compression: 0.3,
        }});
        
        // Color by clade if available
        tree.style_nodes((node) => {{
            const name = node.name;
            if (metadata[name] && metadata[name].lineage) {{
                return {{"fill": "#0ea5e9"}};
            }}
            return {{}};
        }});
    </script>
</body>
</html>
'''
        
        output_path = self.output_dir / f"{output_name}.html"
        with open(output_path, 'w') as f:
            f.write(html_content)
        
        return output_path
    
    def run_progress_chart(
        self,
        run_data: Dict,
        output_name: str = "run_progress",
    ) -> Optional[Path]:
        """
        Create interactive run progress visualization.
        
        Args:
            run_data: Run data with samples and their statuses
            output_name: Output filename
        
        Returns:
            Path to HTML file
        """
        if not PLOTLY_AVAILABLE:
            return None
        
        samples = run_data.get("samples", [])
        if not samples:
            return None
        
        # Create Gantt-like chart
        stages = ["QC", "Mapping", "Variants", "Lineage", "Complete"]
        
        fig = go.Figure()
        
        for i, sample in enumerate(samples):
            sample_id = sample.get("sample_id", f"Sample_{i}")
            status = sample.get("status", "pending")
            
            # Determine progress
            progress = 0
            if status == "qc_complete":
                progress = 1
            elif status == "mapping_complete":
                progress = 2
            elif status == "variants_complete":
                progress = 3
            elif status in ["complete", "completed"]:
                progress = 4
            
            colors = ["#94a3b8", "#0ea5e9", "#22c55e", "#22c55e", "#22c55e"]
            
            fig.add_trace(go.Bar(
                x=[progress],
                y=[sample_id],
                orientation='h',
                marker_color=colors[progress] if progress < len(colors) else "#22c55e",
                name=sample_id,
                showlegend=False,
            ))
        
        fig.update_layout(
            title="Sample Processing Progress",
            xaxis=dict(
                tickmode="array",
                tickvals=[0, 1, 2, 3, 4],
                ticktext=["Pending", "QC", "Mapping", "Variants", "Complete"],
                range=[0, 5],
            ),
            yaxis_title="Sample",
            template="plotly_white",
            height=max(300, len(samples) * 30),
        )
        
        output_path = self.output_dir / f"{output_name}.html"
        fig.write_html(str(output_path), include_plotlyjs='cdn')
        
        return output_path
