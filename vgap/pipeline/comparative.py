"""
VGAP Comparative Genomics Module

Pairwise distances, mutation sharing, and cluster detection.
"""

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger()


@dataclass
class ClusterResult:
    """Cluster detection result."""
    cluster_id: int
    samples: list[str]
    max_distance: int


def parse_fasta(fasta_path: Path) -> dict[str, str]:
    """Parse FASTA file into dictionary."""
    sequences = {}
    current_id = None
    current_seq = []
    
    with open(fasta_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith('>'):
                if current_id:
                    sequences[current_id] = ''.join(current_seq)
                current_id = line[1:].split()[0]
                current_seq = []
            else:
                current_seq.append(line.upper())
        
        if current_id:
            sequences[current_id] = ''.join(current_seq)
    
    return sequences


def hamming_distance(seq1: str, seq2: str, ignore_n: bool = True) -> int:
    """
    Compute Hamming distance between two sequences.
    
    Args:
        seq1: First sequence
        seq2: Second sequence
        ignore_n: If True, positions with N are not counted
    
    Returns:
        Number of differences
    """
    if len(seq1) != len(seq2):
        raise ValueError(f"Sequence lengths differ: {len(seq1)} vs {len(seq2)}")
    
    distance = 0
    for a, b in zip(seq1, seq2):
        if ignore_n and (a == 'N' or b == 'N'):
            continue
        if a != b:
            distance += 1
    
    return distance


def compute_pairwise_distances(
    sequences: dict[str, str],
    output_path: Optional[Path] = None,
    ignore_n: bool = True,
) -> dict[tuple[str, str], int]:
    """
    Compute pairwise Hamming distances for all sequence pairs.
    
    Args:
        sequences: Dictionary of sample_id -> sequence
        output_path: Optional path to write distance matrix
        ignore_n: Whether to ignore N positions
    
    Returns:
        Dictionary mapping (sample1, sample2) -> distance
    """
    sample_ids = sorted(sequences.keys())
    distances = {}
    
    for i, id1 in enumerate(sample_ids):
        for j, id2 in enumerate(sample_ids[i+1:], i+1):
            dist = hamming_distance(sequences[id1], sequences[id2], ignore_n)
            distances[(id1, id2)] = dist
            distances[(id2, id1)] = dist
    
    # Also set self-distances to 0
    for id1 in sample_ids:
        distances[(id1, id1)] = 0
    
    # Write matrix if requested
    if output_path:
        with open(output_path, 'w') as f:
            writer = csv.writer(f, delimiter='\t')
            writer.writerow([''] + sample_ids)
            for id1 in sample_ids:
                row = [id1] + [str(distances[(id1, id2)]) for id2 in sample_ids]
                writer.writerow(row)
    
    logger.info("Computed pairwise distances", 
               num_sequences=len(sequences),
               num_pairs=len(sample_ids) * (len(sample_ids) - 1) // 2)
    
    return distances


def find_mutations(
    sequences: dict[str, str],
    reference_id: str,
) -> dict[str, set[int]]:
    """
    Find mutations relative to a reference sequence.
    
    Args:
        sequences: Dictionary of sample_id -> sequence
        reference_id: ID of the reference sequence
    
    Returns:
        Dictionary mapping sample_id -> set of mutation positions
    """
    if reference_id not in sequences:
        raise ValueError(f"Reference {reference_id} not found in sequences")
    
    ref_seq = sequences[reference_id]
    mutations = {}
    
    for sample_id, seq in sequences.items():
        if sample_id == reference_id:
            mutations[sample_id] = set()
            continue
        
        sample_mutations = set()
        for pos, (ref_base, sample_base) in enumerate(zip(ref_seq, seq)):
            if sample_base != 'N' and ref_base != 'N' and ref_base != sample_base:
                sample_mutations.add(pos + 1)  # 1-based
        
        mutations[sample_id] = sample_mutations
    
    return mutations


def compute_mutation_sharing_matrix(
    mutations: dict[str, set[int]],
    output_path: Optional[Path] = None,
) -> dict[tuple[str, str], int]:
    """
    Compute pairwise mutation sharing counts.
    
    Args:
        mutations: Dictionary mapping sample_id -> set of mutation positions
        output_path: Optional path to write sharing matrix
    
    Returns:
        Dictionary mapping (sample1, sample2) -> shared mutation count
    """
    sample_ids = sorted(mutations.keys())
    sharing = {}
    
    for i, id1 in enumerate(sample_ids):
        for j, id2 in enumerate(sample_ids):
            shared = len(mutations[id1] & mutations[id2])
            sharing[(id1, id2)] = shared
    
    if output_path:
        with open(output_path, 'w') as f:
            writer = csv.writer(f, delimiter='\t')
            writer.writerow([''] + sample_ids)
            for id1 in sample_ids:
                row = [id1] + [str(sharing[(id1, id2)]) for id2 in sample_ids]
                writer.writerow(row)
    
    return sharing


def single_linkage_clustering(
    distances: dict[tuple[str, str], int],
    sample_ids: list[str],
    threshold: int,
) -> list[ClusterResult]:
    """
    Single-linkage clustering at a given SNP threshold.
    
    Args:
        distances: Pairwise distance dictionary
        sample_ids: List of sample IDs
        threshold: Maximum distance to join clusters
    
    Returns:
        List of ClusterResult objects
    """
    # Initialize each sample as its own cluster
    clusters = {sid: {sid} for sid in sample_ids}
    
    # Sort pairs by distance
    pairs = []
    for i, id1 in enumerate(sample_ids):
        for id2 in sample_ids[i+1:]:
            pairs.append((distances[(id1, id2)], id1, id2))
    
    pairs.sort(key=lambda x: x[0])
    
    # Merge clusters if distance <= threshold
    for dist, id1, id2 in pairs:
        if dist > threshold:
            break
        
        # Find current clusters
        c1 = None
        c2 = None
        for cid, members in clusters.items():
            if id1 in members:
                c1 = cid
            if id2 in members:
                c2 = cid
        
        if c1 != c2 and c1 is not None and c2 is not None:
            # Merge c2 into c1
            clusters[c1].update(clusters[c2])
            del clusters[c2]
    
    # Build results
    results = []
    for cluster_id, (cid, members) in enumerate(clusters.items()):
        if len(members) == 1:
            continue  # Skip singletons
        
        # Find max distance within cluster
        max_dist = 0
        member_list = list(members)
        for i, m1 in enumerate(member_list):
            for m2 in member_list[i+1:]:
                d = distances.get((m1, m2), 0)
                if d > max_dist:
                    max_dist = d
        
        results.append(ClusterResult(
            cluster_id=cluster_id,
            samples=sorted(members),
            max_distance=max_dist,
        ))
    
    logger.info("Clustering complete",
               threshold=threshold,
               clusters=len(results),
               clustered_samples=sum(len(c.samples) for c in results))
    
    return results


def temporal_mutation_analysis(
    variants: list[dict],
    dates: dict[str, str],
) -> dict[str, list[dict]]:
    """
    Analyze mutation emergence over time.
    
    Args:
        variants: List of variant dicts with sample_id, pos, alt, etc.
        dates: Dictionary mapping sample_id -> collection_date
    
    Returns:
        Dictionary mapping mutation -> list of first observations
    """
    from datetime import datetime
    
    mutation_dates = {}
    
    for v in variants:
        sample_id = v.get("sample_id")
        if not sample_id or sample_id not in dates:
            continue
        
        mutation = f"{v['pos']}:{v['ref']}>{v['alt']}"
        date_str = dates[sample_id]
        
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue
        
        if mutation not in mutation_dates:
            mutation_dates[mutation] = []
        
        mutation_dates[mutation].append({
            "sample_id": sample_id,
            "date": date_str,
            "gene": v.get("gene"),
            "aa_change": v.get("aa_change"),
        })
    
    # Sort by date
    for mutation in mutation_dates:
        mutation_dates[mutation].sort(key=lambda x: x["date"])
    
    return mutation_dates


class ComparativeGenomicsPipeline:
    """Complete comparative genomics pipeline."""
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
    
    def run(
        self,
        fasta_path: Path,
        reference_id: Optional[str] = None,
        cluster_thresholds: list[int] = [3, 5, 10],
    ) -> dict:
        """
        Run complete comparative analysis.
        
        Args:
            fasta_path: Path to multi-FASTA file
            reference_id: Optional reference for mutation analysis
            cluster_thresholds: SNP thresholds for clustering
        
        Returns:
            Dictionary with all results
        """
        results = {}
        
        # Parse sequences
        sequences = parse_fasta(fasta_path)
        sample_ids = sorted(sequences.keys())
        
        if len(sequences) < 2:
            logger.warning("Need at least 2 sequences for comparison")
            return results
        
        # Pairwise distances
        distances = compute_pairwise_distances(
            sequences,
            output_path=self.output_dir / "distance_matrix.tsv",
        )
        results["distances"] = distances
        
        # Mutation analysis
        if reference_id or sample_ids:
            ref = reference_id or sample_ids[0]
            mutations = find_mutations(sequences, ref)
            results["mutations"] = mutations
            
            compute_mutation_sharing_matrix(
                mutations,
                output_path=self.output_dir / "mutation_sharing.tsv",
            )
        
        # Clustering at different thresholds
        results["clusters"] = {}
        for threshold in cluster_thresholds:
            clusters = single_linkage_clustering(distances, sample_ids, threshold)
            results["clusters"][threshold] = clusters
            
            # Write clusters
            with open(self.output_dir / f"clusters_snp{threshold}.tsv", 'w') as f:
                writer = csv.writer(f, delimiter='\t')
                writer.writerow(["cluster_id", "size", "max_distance", "samples"])
                for c in clusters:
                    writer.writerow([
                        c.cluster_id,
                        len(c.samples),
                        c.max_distance,
                        ','.join(c.samples)
                    ])
        
        logger.info("Comparative analysis complete",
                   samples=len(sequences),
                   output_dir=str(self.output_dir))
        
        return results
