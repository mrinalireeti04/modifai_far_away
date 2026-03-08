# Modifai Synthetic Dataset Generation Pipeline

A production-ready, document-agnostic pipeline that converts raw PDF documents into high-quality synthetic datasets optimized for LLM fine-tuning.

## Architecture

This pipeline is 100% domain-agnostic and relies on **Universal Quality Signals** (overlap, structural integrity, length) rather than hardcoded keywords. It uses:
- **PyMuPDF / AWS Textract** for text extraction
- **Amazon Bedrock (Nova Micro)** for generation
- **Hybrid Quality Control** to filter out hallucinations and generic answers

### Project Structure
```text
modifai/
├── core/
│   ├── text_extraction.py      # Extract text locally or via Textract
│   ├── chunking.py             # Max-word smart text chunking
│   ├── dataset_generation.py   # Generate synthetic dataset pairs using AWS Nova
│   ├── validation.py           # Optional strictest LLM grounding validation
│   ├── quality_control.py      # Universal dataset filtering and deduplication
│   ├── scoring.py              # Math for overlap, length, and structure checks
│   └── utils.py                # Logging and helper functions
├── config/
│   └── settings.py             # Configurable settings
├── tests/                      # Pytest definitions
├── pipeline.py                 # Main orchestration logic
└── run_pipeline.py             # CLI Entry point
```

## Prerequisites

- Python 3.9+
- AWS Account with Bedrock `amazon.nova-micro-v1:0` access enabled and Textract access (for fallback).
- Configured AWS Credentials (`~/.aws/credentials`).

### Installation

```bash
pip install -r requirements.txt
```

## AWS Configuration

The pipeline defaults to reading your local AWS environment variables or default AWS CLI profile.

Ensure your profile is set up:
```bash
aws configure
```

Alternatively, set your environment variables explicitly before running the pipeline:
```bash
export AWS_PROFILE="my-profile"
export AWS_REGION="us-east-1"
export AWS_MODEL_ID="amazon.nova-micro-v1:0"
```

## Running the Pipeline

You can run the pipeline directly from the command line on any PDF file:

```bash
python run_pipeline.py path/to/document.pdf --output-dir ./output
```

**Options:**
- `--mode`: Generation mode (`QA` (default), `instruction`, `tutor`).
- `--samples-per-chunk`: Number of target generated samples per text chunk (default `3`).
- `--validation-mode`: Enable strict LLM verification (`fast` (default) or `validated`).
- `--qc-threshold`: Minimum universal score required to pass Quality Control (default `0.6`).

### Outputs
The pipeline generates four files in your output directory:
1. `raw_text.txt`: The raw text extracted from the PDF.
2. `chunks.json`: The chunked segments of the text.
3. `synthetic_dataset.jsonl`: The initial generated samples.
4. `final_dataset.jsonl`: The high-quality, filtered, deduplicated release dataset.

## Running Tests

Tests are written in `pytest` and mock all AWS calls to run purely locally without incurring token costs.

```bash
pytest tests/
```

## Backend Integration

You can easily import the `run_pipeline` function directly into your own backend services:

```python
from modifai.config.settings import PipelineConfig
from modifai.pipeline import run_pipeline

config = PipelineConfig(
    aws_profile="prod",
    aws_region="us-west-2",
    mode="QA",
    samples_per_chunk=5,
    qc_threshold=0.65
)

# Returns the final high-quality dataset as a list of dictionaries
final_dataset = run_pipeline("uploaded_document.pdf", config, output_dir="/mnt/data/job_123")
```
