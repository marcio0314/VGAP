import pytest
from pydantic import ValidationError
from vgap.api.schemas.parameters import RunParameters, PipelineMode, VirusTarget

def test_run_parameters_defaults():
    """Test default values."""
    params = RunParameters(
        mode=PipelineMode.SHOTGUN,
        virus_target=VirusTarget.SARS_COV_2,
        reference_set="sars-cov-2"
    )
    assert params.min_depth == 10
    assert params.min_allele_freq == 0.05
    assert params.mapper_preset == "sr"

def test_run_parameters_amplicon_primers_required():
    """Test that amplicon mode requires primer_scheme."""
    with pytest.raises(ValidationError) as exc:
        RunParameters(
            mode=PipelineMode.AMPLICON,
            virus_target=VirusTarget.SARS_COV_2,
            reference_set="sars-cov-2"
            # Missing primer_scheme
        )
    assert "primer_scheme is required" in str(exc.value)

def test_run_parameters_influenza_segments():
    """Test Influenza segment validation."""
    params = RunParameters(
        mode=PipelineMode.SHOTGUN,
        virus_target=VirusTarget.INFLUENZA_A,
        reference_set="influenza-a",
        per_segment_coverage_required={"HA": 50.0, "NA": 50.0}
    )
    assert params.per_segment_coverage_required["HA"] == 50.0

def test_run_parameters_validation_limits():
    """Test numeric limits."""
    with pytest.raises(ValidationError):
        RunParameters(
            mode=PipelineMode.SHOTGUN,
            virus_target=VirusTarget.SARS_COV_2,
            reference_set="sars-cov-2",
            min_depth=0 # Too low, min 1
        )
