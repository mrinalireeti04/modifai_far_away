# 🤖 Modifai — Automated LLM Fine-Tuning Platform

> **AWS Hack2Skill Hackathon Submission**
>
> Modifai transforms raw documents into fine-tuned, deployed language models — fully automated, fully serverless, on AWS.

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)](https://python.org)
[![AWS Bedrock](https://img.shields.io/badge/AWS-Bedrock%20Nova-orange)](https://aws.amazon.com/bedrock/)
[![AWS SageMaker](https://img.shields.io/badge/AWS-SageMaker-orange)](https://aws.amazon.com/sagemaker/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 🧠 What is Modifai?

Modifai is an end-to-end, serverless MLOps platform that lets anyone — regardless of ML expertise — turn their proprietary documents (PDFs, manuals, reports) into production-ready fine-tuned language models with a single upload.

**The full vision:** A user uploads their documents, selects a base LLM and intent (e.g., Q&A, instruction-following, tutoring), and Modifai automatically:
1. Extracts and understands the document content (OCR via Textract)
2. Generates thousands of high-quality synthetic training pairs (via Amazon Bedrock)
3. Filters and deduplicates the dataset with universal quality signals
4. Fine-tunes a base model on SageMaker
5. Deploys the model to a live inference endpoint

The user can close the browser and come back to a ready-to-use model.

---

## ⚙️ Execution Modes

The platform supports four execution modes, allowing users to run only the stages they need:

| Mode | Pipeline Steps | User Provides |
|------|---------------|---------------|
| **Dataset Only** | OCR → Chunk → Generate → QC → Export JSONL | Intent, description, document files |
| **Fine-Tune Only** | Fine-tune on SageMaker | Pre-built JSONL dataset, base model |
| **Dataset + Fine-Tune** | OCR → Chunk → Generate → QC → Fine-tune | Intent, description, document files, base model |
| **Full Pipeline** | OCR → Chunk → Generate → QC → Fine-tune → Deploy | Intent, description, document files, base model, deployment config |

---

## 🏗️ Architecture

### High-Level System Design

```
┌─────────────────────────────────────────────────────────────────┐
│                 🖥️  Frontend (React + Vite)                      │
│    User Interface  ←→  Client-Side File Parser                  │
└──────────────────────────────┬──────────────────────────────────┘
                               │ REST API calls
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│               ⚙️  Backend (FastAPI — thin layer)                 │
│  /api/evaluate-data  /api/upload/presign  /api/projects/...     │
└──────────────────────────────┬──────────────────────────────────┘
                               │
             ┌─────────────────┼─────────────────┐
             ▼                 ▼                 ▼
         [S3 Bucket]    [Step Functions]    [Bedrock LLM]
         Presigned         Orchestrator       Evaluate data
         PUT uploads                          quality
                               │
                    ┌──────────▼──────────┐
                    │  Lambda Functions   │
                    │  (one per step)     │
                    └──────────┬──────────┘
             ┌────────┬────────┼────────┬────────┐
             ▼        ▼        ▼        ▼        ▼
         Textract  Chunking  Bedrock  SageMaker SageMaker
          (OCR)    Lambda    (GenAI)  Fine-Tune  Deploy
```

### S3 Bucket Layout

```
s3://modifai-bucket/
└── {user_uuid}/
    └── {project_uuid}/
        ├── data/                      # Raw uploaded files (via presigned URLs)
        ├── models/                    # Fine-tuned model artifacts (SageMaker output)
        └── temp_processing/           # Intermediate pipeline artifacts
            ├── raw_text.json          # Textract OCR output
            ├── chunks.json            # Semantic text chunks
            ├── examples.json          # Generated QA pairs (pre-QC)
            └── clean_dataset.jsonl    # Final filtered training dataset
```

### Step Functions State Machine

The AWS Step Functions orchestrator branches execution based on mode:

```
[Start] → CheckMode
             ├── dataset modes → OCR → Chunking → DatasetGeneration → QualityControl → SaveDataset
             │                                                                              │
             │                                                                    CheckFineTune
             │                                                                    ├── finetune modes → FineTune → PollTraining → CheckDeploy
             │                                                                    │                                                  ├── full → Deploy → [Done]
             │                                                                    │                                                  └── no-deploy → [Done]
             │                                                                    └── dataset_only → [Done]
             └── finetune_only → FineTune → PollTraining → CheckDeploy → ...
```

---

## 📁 Repository Structure

### What's Currently Implemented (Local Pipeline Core)

```
modifai/
├── core/
│   ├── text_extraction.py      # PDF text extraction (PyMuPDF primary, Textract fallback)
│   ├── chunking.py             # Max-word smart text chunking
│   ├── dataset_generation.py   # Synthetic QA/instruction pairs via Amazon Bedrock Nova Micro
│   ├── validation.py           # Optional strict LLM grounding validation
│   ├── quality_control.py      # Universal dataset filtering & deduplication
│   ├── scoring.py              # Overlap, length, and structural quality scoring
│   └── utils.py                # Logging helpers
├── config/
│   └── settings.py             # PipelineConfig dataclass with all tunable parameters
├── tests/
│   ├── test_chunking.py
│   ├── test_dataset_generation.py
│   ├── test_pipeline.py
│   ├── test_quality_control.py
│   └── test_text_extraction.py
├── pipeline.py                 # Main orchestration logic (local runner)
├── run_pipeline.py             # CLI entry point
└── requirements.txt
```

---

## 🚀 Quick Start (Local Pipeline)

### Prerequisites

- Python 3.9+
- AWS Account with the following enabled:
  - **Amazon Bedrock** — `amazon.nova-micro-v1:0` model access
  - **AWS Textract** — for OCR fallback on scanned PDFs
- Configured AWS credentials (`~/.aws/credentials`)

### Installation

```bash
git clone https://github.com/AdvityaDua/aws-hack2skill-modifai.git
cd aws-hack2skill-modifai
pip install -r requirements.txt
```

### AWS Configuration

The pipeline reads credentials from your AWS environment automatically:

```bash
aws configure
```

Or set environment variables explicitly:

```bash
export AWS_PROFILE="my-profile"
export AWS_REGION="us-east-1"
export AWS_MODEL_ID="amazon.nova-micro-v1:0"
```

### Run the Pipeline

```bash
python run_pipeline.py path/to/document.pdf --output-dir ./output
```

**CLI Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--mode` | `QA` | Generation mode: `QA`, `instruction`, or `tutor` |
| `--samples-per-chunk` | `3` | Number of synthetic pairs generated per text chunk |
| `--validation-mode` | `fast` | `fast` (heuristic) or `validated` (LLM-verified grounding) |
| `--qc-threshold` | `0.6` | Minimum quality score (0–1) to pass filtering |

### Pipeline Outputs

The pipeline generates 4 files in `--output-dir`:

| File | Description |
|------|-------------|
| `raw_text.txt` | Raw extracted text from the PDF |
| `chunks.json` | Semantically chunked segments (200–500 words each) |
| `synthetic_dataset.jsonl` | All generated samples before quality filtering |
| `final_dataset.jsonl` | Deduplicated, filtered, production-ready training dataset |

---

## 🔧 Backend Integration (Programmatic API)

Import and run the pipeline programmatically in your own services:

```python
from modifai.config.settings import PipelineConfig
from modifai.pipeline import run_pipeline

config = PipelineConfig(
    aws_profile="prod",
    aws_region="us-west-2",
    model_id="amazon.nova-micro-v1:0",
    mode="QA",
    samples_per_chunk=5,
    qc_threshold=0.65,
    validation_mode="validated"
)

# Returns the final high-quality dataset as a list of dicts
final_dataset = run_pipeline("uploaded_document.pdf", config, output_dir="/mnt/data/job_123")
```

---

## 🧪 Running Tests

Tests mock all AWS calls — no credentials or token costs required:

```bash
pytest tests/
```

---

## 🏛️ Full Platform API Design (FastAPI Backend)

The full-stack platform exposes the following REST API (designed, partial implementation remaining):

### Core Project APIs

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/evaluate-data` | POST | Send random document samples + intent to Bedrock; returns quality score + recommendation (fine-tune vs RAG) |
| `/api/upload/presign` | POST | Generate presigned S3 PUT URLs for direct client-side uploads |
| `/api/projects` | POST | Create a new project record in the database |
| `/api/projects` | GET | List all projects for the current user |
| `/api/projects/{id}/start` | POST | Kick off the Step Functions execution with mode + config payload |
| `/api/projects/{id}/status` | GET | Poll Step Function execution status + per-step progress |
| `/api/projects/{id}/results` | GET | Retrieve final outputs (dataset S3 URL, model endpoint URL, download link) |
| `/api/projects/{id}` | DELETE | Delete a project and all associated S3 data |

### Dataset Review & Editing APIs

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/projects/{id}/dataset` | GET | List generated training examples (paginated) |
| `/api/projects/{id}/dataset/{example_id}` | PUT | Edit a specific training example |
| `/api/projects/{id}/dataset/{example_id}` | DELETE | Remove a training example |
| `/api/projects/{id}/dataset/export` | GET | Download the full dataset as JSONL |

### Step Functions Payload Schema

```json
{
  "project_id": "proj-abc123",
  "s3_prefix": "user-uuid/proj-uuid/",
  "mode": "full | dataset_only | finetune_only | dataset_and_finetune",
  "config": {
    "intent": "question-answering",
    "description": "Customer support bot for SaaS docs",
    "samples_per_chunk": 5,
    "quality_threshold": 0.7,
    "base_model": "meta-llama/Llama-3.1-8B"
  },
  "step_results": {
    "ocr": { "raw_text_key": "temp_processing/raw_text.json" },
    "chunking": { "chunks_key": "temp_processing/chunks.json", "chunk_count": 42 },
    "generation": { "examples_key": "temp_processing/examples.json", "example_count": 210 },
    "quality_control": { "clean_dataset_key": "temp_processing/clean_dataset.jsonl", "kept": 180, "discarded": 30 },
    "fine_tuning": { "model_key": "models/adapter/", "job_name": "modifai-ft-abc123", "duration_min": 45, "final_loss": 0.42 },
    "deployment": { "endpoint_name": "modifai-ep-abc123", "endpoint_url": "..." }
  }
}
```

---

## 🔬 How the Quality System Works

Modifai uses **Universal Quality Signals** — no hardcoded domain keywords — making it applicable to any document type:

| Signal | What it Measures | Weight |
|--------|-----------------|--------|
| **Lexical Overlap** | How much of the answer's vocabulary appears in the source chunk | High |
| **Answer Length** | Answers that are too short or too long are penalized | Medium |
| **Structural Integrity** | Checks for complete sentences, not truncated fragments | Medium |
| **Deduplication** | Removes near-duplicate QA pairs using token-level similarity | Filtering |

Samples scoring below `qc_threshold` (default: `0.6`) are discarded. The `validated` mode additionally sends each sample back to the LLM to verify that the answer is genuinely grounded in the source chunk.

---

## ✅ What's Done

- [x] **Local pipeline core** — fully functional end-to-end Python pipeline
  - [x] PDF text extraction (PyMuPDF + Textract fallback)
  - [x] Semantic chunking (max-word sliding window)
  - [x] Synthetic dataset generation via Amazon Bedrock Nova Micro (QA, instruction, tutor modes)
  - [x] LLM-based grounding validation (fast + validated modes)
  - [x] Hybrid quality control (deduplication + universal scoring + threshold filtering)
  - [x] CLI entry point (`run_pipeline.py`)
  - [x] Programmatic API (`run_pipeline()` function)
  - [x] Configuration via `PipelineConfig` dataclass + environment variables
  - [x] Unit tests with mocked AWS calls (5 test files)
  - [x] JSONL export for fine-tuning compatibility

---

## 🚧 What Remains To Be Done

### 🔴 High Priority (Core Platform — Not Yet Started)

#### AWS Infrastructure
- [ ] **AWS Step Functions state machine** — define the full ASL (Amazon States Language) JSON for the orchestrator with all branching logic
- [ ] **Lambda functions** — implement one Lambda per pipeline step:
  - [ ] `lambda_ocr.py` — call Textract on S3 objects (multi-page async)
  - [ ] `lambda_chunking.py` — wrap the local chunking logic for Lambda execution
  - [ ] `lambda_generation.py` — wrap dataset generation for Lambda (Map state for parallel chunk processing)
  - [ ] `lambda_quality_control.py` — wrap QC logic for Lambda
  - [ ] `lambda_finetune.py` — submit and poll SageMaker training jobs
  - [ ] `lambda_deploy.py` — create SageMaker inference endpoints
- [ ] **SageMaker fine-tuning job** — configure training job definitions, instance types, and data channels from S3
- [ ] **SageMaker endpoint deployment** — configure endpoint configs, auto-scaling policies
- [ ] **Infrastructure as Code** — write AWS CDK or Terraform to provision: S3 bucket, Step Functions, Lambda functions, IAM roles, SageMaker roles

#### FastAPI Backend
- [ ] **All API endpoints** listed in the API Design section above — none are implemented yet
- [ ] **Database** — choose and set up a database (e.g., DynamoDB or RDS) to store project records and metadata
- [ ] **Authentication** — user identity and JWT/Cognito-based auth
- [ ] **Presigned URL generation** — S3 presigned PUT URL logic
- [ ] **Step Functions integration** — start execution, poll status, parse execution history

#### Frontend (React + Vite)
- [ ] **Mode selection UI** — step-by-step wizard: Dataset Only / Fine-Tune Only / Dataset+FT / Full Pipeline
- [ ] **Intent & data input forms** — intent selector (QA, instruction, tutor), use-case description, file upload
- [ ] **Client-side file parser** — parse document samples in-browser for the pre-flight data evaluation step
- [ ] **Data evaluation results view** — display quality score + recommendation (Fine-tune vs RAG)
- [ ] **Presigned URL upload** — direct browser-to-S3 file upload using presigned PUT URLs
- [ ] **Project dashboard** — list all projects with status badges
- [ ] **Pipeline progress tracker** — real-time per-step progress display (Step Function polling)
- [ ] **Dataset review & editor** — paginated view of generated examples with inline edit/delete
- [ ] **Results page** — display final dataset download link, model endpoint URL, training metrics

### 🟡 Medium Priority (Quality & Reliability)

- [ ] **Multi-page async Textract** — the current Textract implementation uses synchronous `detect_document_text` which is limited to single-page or small documents; large PDFs need `start_document_text_detection` + polling
- [ ] **Parallel chunk processing** — the current local pipeline processes chunks sequentially; the Lambda Map state should fan out for speed
- [ ] **Error handling & retries** — robust retry logic in Step Functions for transient AWS service errors
- [ ] **Chunking improvements** — current chunking is word-count based; consider sentence-boundary-aware or semantic chunking (e.g., using embeddings)
- [ ] **Support for non-PDF formats** — currently only PDFs are supported; add DOCX, TXT, images
- [ ] **Model selection UI** — allow users to choose from multiple base models (Llama 3.1 8B, Mistral 7B, etc.)
- [ ] **Cost estimation** — display estimated AWS cost before starting the pipeline based on document size and model choice

### 🟢 Lower Priority (Nice-to-Have)

- [ ] **Dataset inspection pre-fine-tune** — allow users to review and curate the generated dataset before submitting the SageMaker training job
- [ ] **Post-deployment inference playground** — a UI widget to test the deployed model endpoint directly in the browser
- [ ] **Email/webhook notifications** — notify users when the pipeline completes (since it runs async)
- [ ] **Multi-file upload** — currently designed for single PDF; extend to support multiple documents per project
- [ ] **Usage analytics dashboard** — track token usage, costs, training metrics per project
- [ ] **Export fine-tuned model** — allow users to download the model adapter weights for local use (e.g., GGUF format)
- [ ] **Bring-your-own Bedrock model** — allow users to specify a custom Bedrock model ID or Gemini endpoint

---

## 🛠️ Configuration Reference

All settings are in [`config/settings.py`](config/settings.py) via the `PipelineConfig` dataclass:

| Parameter | Env Variable | Default | Description |
|-----------|-------------|---------|-------------|
| `aws_profile` | `AWS_PROFILE` | `"default"` | AWS credentials profile |
| `aws_region` | `AWS_REGION` | `"us-east-1"` | AWS region for Bedrock + Textract |
| `model_id` | `AWS_MODEL_ID` | `"amazon.nova-micro-v1:0"` | Bedrock model for generation |
| `max_chunk_words` | — | `500` | Maximum words per text chunk |
| `mode` | — | `"QA"` | Generation mode: `QA`, `instruction`, `tutor` |
| `samples_per_chunk` | — | `3` | Synthetic samples generated per chunk |
| `validation_mode` | — | `"fast"` | `"fast"` (heuristic) or `"validated"` (LLM-verified) |
| `qc_threshold` | — | `0.6` | Minimum quality score to keep a sample |

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m 'Add my feature'`
4. Push to the branch: `git push origin feature/my-feature`
5. Open a Pull Request

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 👥 Team

Built for the **AWS Hack2Skill Hackathon** by [AdvityaDua](https://github.com/AdvityaDua) and contributors.

> *"From documents to deployed models — no ML expertise required."*
