# Modifai — Project Roadmap

> A narrative account of how this project evolved from concept to its current architecture, and the step-by-step plan to ship it.

---

## Part 1: The Problem

Fine-tuning language models is powerful — but the pipeline to get there is brutal. A typical user who wants to customize an LLM for their domain (customer support, legal docs, medical records) faces:

1. **Collecting training data** — manually writing hundreds of instruction-response pairs
2. **Formatting the data** — getting it into the right JSONL schema
3. **Setting up infrastructure** — provisioning GPU instances, installing ML frameworks
4. **Running fine-tuning** — configuring LoRA, hyperparameters, training loops
5. **Deploying the model** — creating inference endpoints, managing scaling

Each step requires deep ML expertise. The gap between "I have documents" and "I have a fine-tuned model" is enormous.

**Modifai bridges this gap.** Upload your documents, tell us what you want, and we handle everything.

---

## Part 2: How the Solution Evolved

### Iteration 1 — Local Python Pipeline

The team built the first proof of concept as a **local Python script** (`split-code/dataset/`):

- Extract text from PDFs using PyMuPDF
- Chunk text into segments
- Call Bedrock (Amazon Nova Micro) to generate synthetic QA pairs
- Validate generated pairs using a second LLM call (grounding check)
- Score quality using a weighted formula (overlap + length + structural)
- Export as JSONL

**What worked**: The pipeline logic was sound. The scoring system (3 universal metrics with configurable weights) was well-designed. The grounding validation step was a smart quality gate.

**What didn't work**: Everything ran locally and synchronously. No UI, no cloud deployment, no way for non-technical users to use it.

### Iteration 2 — FastAPI + React Frontend

We wrapped the pipeline in a web app:

- **Frontend** (React + Vite): Dashboard, project list, new project wizard with file upload, model selection, quality threshold config, and a pipeline status tracker
- **Backend** (FastAPI): REST API with SQLAlchemy models for projects and pipeline steps
- **Architecture doc** (`Arch.md`): Defined a 7-step pipeline using S3, Textract, Bedrock, and SageMaker

**What worked**: The frontend was polished — drag-and-drop uploads, model selector, pipeline visualization with per-step status tracking. The backend had clean project/pipeline models.

**What didn't work**: The architecture had misalignments:
- `Arch.md` specified AWS services (S3, Textract, Bedrock, SageMaker) but the Kiro requirements and tasks assumed local libraries (PyMuPDF, OpenAI, HuggingFace PEFT)
- No quality control requirement existed despite `Arch.md` including it
- The backend was trying to be the orchestrator — managing async task queues, polling SageMaker, chaining steps — which made it complex and fragile

### Iteration 3 — Step Functions + AWS-Native Architecture (Current)

The critical insight: **the backend shouldn't orchestrate the pipeline**. AWS Step Functions was built for exactly this.

Key architectural decisions made:

1. **Mode selection comes first** — the user picks what they want (dataset only, fine-tune only, both, or full pipeline) before providing any inputs. This drives the entire UI and pipeline flow.

2. **Client-side data evaluation** — before uploading, the frontend parses files locally, sends random samples to an LLM, and gets a quality/fit assessment. This prevents wasting time on bad data.

3. **Presigned S3 uploads** — the frontend uploads files directly to S3 via presigned URLs. The backend never touches raw files, keeping it thin.

4. **Step Functions orchestrates everything** — each pipeline step is a Lambda function. Choice states branch based on mode. Polling loops handle SageMaker's async nature. The user can close the browser.

5. **Thin FastAPI backend** — reduced to ~8 endpoints: presigned URLs, data evaluation, project CRUD, Step Functions start/poll, and dataset review.

### What the team had already built (`split-code/`)

Three separate codebases that cover most of the pipeline logic:

| Folder | Coverage | Lambda-Ready? |
|--------|----------|---------------|
| `dataset/` | OCR, chunking, generation, validation, QC, scoring | 🟡 Close — needs S3 I/O instead of local file I/O |
| `intent+upload/` | Data evaluation (intent refinement + relevance check) | 🟡 Close — needs `converse` API, numeric scores |
| `sagemaker/` | Model validation, training, deployment | 🔴 Needs work — polling loops must go to Step Functions |

**Critical issues found in code review:**
- Hardcoded IAM ARN with real AWS account ID in sagemaker files
- Synchronous polling loops incompatible with Lambda's 15-min timeout
- Inconsistent Bedrock APIs (`invoke_model` vs `converse`)
- Inconsistent AWS regions (`ap-south-1` vs `us-east-1`)

---

## Part 3: The Implementation Plan

### Phase 1 — Lambda Functions (prepare pipeline steps for deployment)

Each Lambda gets a `handler.py` with a standard interface: receive event from Step Functions → do work → return result for next step.

```
lambdas/
├── evaluate_data/      → Accept samples + intent, return quality score
├── ocr/                → Read files from S3, run Textract, store raw text
├── chunking/           → Read raw text, chunk, store chunks in S3
├── dataset_generation/ → Read one chunk, generate N samples via Bedrock
├── quality_control/    → Read all examples, filter by threshold, store clean JSONL
├── fine_tune/          → Submit SageMaker training job, return job name
├── deploy/             → Create SageMaker endpoint, return endpoint URL
└── status_checker/     → Check SageMaker job/endpoint status (for poll loop)
```

**Order of implementation:**

| # | Lambda | Adapting from | Key changes |
|---|--------|---------------|-------------|
| 1 | `evaluate_data` | `intent+upload/modifai_engine.py` | Switch to `converse` API, accept samples as input (not S3), return numeric score + recommendation |
| 2 | `ocr` | `dataset/core/text_extraction.py` | Read from S3 (not local path), support images, write output to S3 |
| 3 | `chunking` | `dataset/core/chunking.py` | Read raw text from S3, add chunk overlap, write chunks to S3 |
| 4 | `dataset_generation` | `dataset/core/dataset_generation.py` | Process single chunk (Map state handles parallelism), reuse boto3 client, robust JSON parsing |
| 5 | `quality_control` | `dataset/core/quality_control.py` + `scoring.py` | Read examples from S3, score + filter, write clean JSONL to S3 |
| 6 | `fine_tune` | `sagemaker/fine_tune_service.py` | Remove polling loop, submit job only, return job name. Config from env vars |
| 7 | `status_checker` | New (extracted from fine_tune + deploy polling) | Single check: describe training job OR endpoint → return status |
| 8 | `deploy` | `sagemaker/deploy_service.py` | Remove polling loop, create endpoint only
, return endpoint name. Config from env vars |

### Phase 2 — Step Functions State Machine

Define the state machine that wires all Lambdas together:

- **Input**: `{ project_id, s3_prefix, mode, config }`
- **Choice state**: branch on `mode` (skip OCR for finetune_only, skip fine-tune for dataset_only, etc.)
- **Map state**: parallelize dataset generation across chunks
- **Poll loop**: Lambda checks SageMaker status → Wait 60s → Check again → Choice (complete/failed/continue)
- **Output**: accumulated `step_results` with S3 keys, metrics, endpoint URLs

Deploy via CloudFormation, SAM, or CDK (TBD based on team preference).

### Phase 3 — Backend API (FastAPI — thin layer)

Update the existing FastAPI backend to become the thin API layer:

1. `POST /api/evaluate-data` — proxy to `evaluate_data` Lambda (or call Bedrock directly)
2. `POST /api/upload/presign` — generate presigned S3 PUT URLs
3. `POST /api/projects` — create project record
4. `POST /api/projects/{id}/start` — start Step Function execution
5. `GET /api/projects/{id}/status` — poll Step Function status
6. `GET /api/projects/{id}/results` — fetch outputs from S3
7. Dataset review CRUD — read/edit/delete examples from S3 JSONL

### Phase 4 — Frontend Updates

Wire the existing React frontend to the real backend (replace mock data):

1. **Mode selection** — add as first wizard step, adapt subsequent steps dynamically
2. **Intent selection** — add intent cards with descriptions
3. **Data evaluation** — parse files client-side, call evaluate endpoint, display score
4. **Presigned uploads** — replace current mock upload with real S3 presigned flow
5. **Pipeline tracker** — poll real Step Function status instead of mock data
6. **Results panel** — show dataset download link, endpoint URL, training metrics
7. **Dataset review page** — new page for inspecting/editing generated examples

### Phase 5 — Integration Testing & Polish

1. End-to-end test of all 4 modes
2. Error handling across all layers
3. Cost verification — run a real pipeline, measure actual AWS spend
4. UI polish — loading states, error messages, responsive design

---

## Part 4: What We're Building Next (Right Now)

We start with **Phase 1 — Lambda Functions**. The existing `split-code/` provides tested logic for most steps. Our job is to:

1. Adapt each module for Lambda's execution model (event in → result out)
2. Replace local file I/O with S3 reads/writes
3. Standardize on the Bedrock `converse` API
4. Move all secrets/config to environment variables
5. Remove synchronous polling loops (Step Functions handles that)
6. Ensure each Lambda is independently deployable and testable

The Lambda folder structure is already created at `lambdas/`. We proceed one Lambda at a time, starting with the simplest pure-logic ones and building up to the SageMaker integration lambdas.
