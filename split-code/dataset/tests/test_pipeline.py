import pytest
from unittest.mock import patch
from modifai.pipeline import run_pipeline
from modifai.config.settings import PipelineConfig

@patch("modifai.pipeline.extract_text")
@patch("modifai.pipeline.generate_dataset")
@patch("modifai.pipeline.validate_dataset")
def test_full_pipeline_mocked(mock_validate, mock_generate, mock_extract, tmp_path):
    mock_extract.return_value = "This is a mock PDF text extract. It contains multiple sentences."
    
    mock_generate.return_value = [
        {"chunk_id": 1, "instruction": "What is this?", "input": "", "response": "This is a mock PDF text extract."},
        {"chunk_id": 1, "instruction": "What does it contain?", "input": "", "response": "multiple sentences."}
    ]
    
    mock_validate.return_value = mock_generate.return_value
    
    config = PipelineConfig(qc_threshold=0.1) # low threshold to ensure passages pass
    
    output_dir = tmp_path / "output"
    
    final_dataset = run_pipeline("dummy.pdf", config, str(output_dir))
    
    assert len(final_dataset) == 2
    assert (output_dir / "raw_text.txt").exists()
    assert (output_dir / "chunks.json").exists()
    assert (output_dir / "synthetic_dataset.jsonl").exists()
    assert (output_dir / "final_dataset.jsonl").exists()
