# Implementation Plan: Modifai

## Overview

This plan reflects the finalized architecture: **AWS Step Functions** orchestrates the pipeline, **FastAPI** is a thin API layer, each pipeline step is a **Lambda function**, and uploads go directly to **S3 via presigned URLs**. The user selects an execution mode first, which determines the inputs and pipeline steps.

**Stack**: FastAPI (backend API) · React + Vite (frontend) · AWS Step Functions (orchestration) · Lambda (step logic) · S3 (storage) · Textract (OCR) · Bedrock/Gemini (LLM) · SageMaker (fine-tuning + deployment)

## Tasks

### A. Backend — FastAPI (thin API layer)

- [x] 1. Core FastAPI infrastructure
  - FastAPI app with CORS, config, env vars, health endpoint
  - SQLAlchemy models for Project and PipelineStep
  - Directory structure (app/, api/, models/, schemas/, services/)
  - requirements.txt with core dependencies
  - _Requirements: 17.1, 17.2_

- [x] 2. S3 presigned URL service
  - [x] 2.1 Create S3Service class (boto3)
    - `generate_presigned_put_urls(filenames, user_uuid, project_uuid)` → list of presigned PUT URLs
    - `generate_presigned_get_url(s3_key)` → presigned GET URL for downloads
    - Enforce bucket prefix: `{user_uuid}/{project_uuid}/data/`
    - _Requirements: 4.1, 4.2_
  - [x] 2.2 Create `POST /api/upload/presign` endpoint
    - Accept list of filenames + project context
    - Return presigned S3 PUT URLs
    - _Requirements: 4.1, 4.2_

- [x] 3. Data evaluation endpoint
  - [x] 3.1 Create `POST /api/evaluate-data` endpoint
    - Accept: random content samples, intent, use-case description
    - Forward to Bedrock / Gemini: score quality (1–10), fit assessment, fine-tune vs RAG recommendation
    - Return: quality_score, recommendation, reasoning
    - _Requirements: 3.2, 3.3, 3.4_

- [x] 4. Project CRUD endpoints
  - [x] 4.1 Create Project schemas (Pydantic)
    - ProjectCreate: name, mode, intent, description, config, s3_keys
    - ProjectResponse: id, name, mode, status, config, created_at, results
    - _Requirements: 5.1, 5.2_
  - [x] 4.2 Create `POST /api/projects` — create project record
    - _Requirements: 5.1, 5.3_
  - [x] 4.3 Create `GET /api/projects` — list user's projects
    - _Requirements: 5.4_
  - [x] 4.4 Create `GET /api/projects/{id}` — get project detail
    - _Requirements: 5.4_
  - [x] 4.5 Create `DELETE /api/projects/{id}` — delete project + S3 data
    - _Requirements: 5.4_

- [x] 5. Pipeline execution endpoints (Step Functions integration)
  - [x] 5.1 Create StepFunctionsService class (boto3)
    - `start_execution(state_machine_arn, input)` → execution_arn
    - `describe_execution(execution_arn)` → status, current step, history
    - `get_execution_history(execution_arn)` → per-step details with durations
    - _Requirements: 6.1, 6.3_
  - [x] 5.2 Create `POST /api/projects/{id}/start` endpoint
    - Validate project is ready (files uploaded, config complete)
    - Start Step Function execution with mode + config + S3 keys
    - Store execution ARN in project record
    - Return execution ARN
    - _Requirements: 6.1, 6.2_
  - [x] 5.3 Create `GET /api/projects/{id}/status` endpoint
    - Poll Step Function execution status
    - Parse execution history into per-step status (pending/running/complete/error + durations)
    - Return structured pipeline state
    - _Requirements: 6.5, 6.6, 13.1, 13.2, 13.3_
  - [x] 5.4 Create `GET /api/projects/{id}/results` endpoint
    - Return final outputs: dataset download URL (presigned), model endpoint, training metrics
    - _Requirements: 13.4_

- [x] 6. Dataset review endpoints
  - [x] 6.1 Create `GET /api/projects/{id}/dataset` — list training examples (paginated, from S3 JSONL)
    - _Requirements: 14.1, 14.2_
  - [x] 6.2 Create `PUT /api/projects/{id}/dataset/{example_id}` — edit example
    - _Requirements: 14.2_
  - [x] 6.3 Create `DELETE /api/projects/{id}/dataset/{example_id}` — delete example
    - _Requirements: 14.3_
  - [x] 6.4 Create `GET /api/projects/{id}/dataset/search` — search examples by content
    - _Requirements: 14.5_
  - [x] 6.5 Create `GET /api/projects/{id}/dataset/export` — download JSONL
    - _Requirements: 14.6_

- [x] 7. Error handling middleware
  - Catch all exceptions including boto3 errors
  - Return user-friendly messages, log full details
  - _Requirements: 16.1, 16.2, 16.3, 16.4_

---

### B. AWS Infrastructure — Step Functions + Lambda

- [x] 8. Step Functions state machine definition (ASL / CDK / SAM)
  - [x] 8.1 Define state machine with Choice states for mode branching
    - Input schema: project_id, s3_prefix, mode, config
    - Choice: mode includes dataset gen? → OCR path vs finetune_only path
    - Choice: mode includes fine-tuning? → SageMaker path vs dataset_only end
    - Choice: mode is full? → Deploy vs end
    - _Requirements: 6.2_
  - [x] 8.2 Define Map state for parallel dataset generation across chunks
    - _Requirements: 9.2_
  - [x] 8.3 Define SageMaker training poll loop (check status → wait 60s → repeat)
    - _Requirements: 11.2_
  - [x] 8.4 Deploy state machine to AWS
    - _Requirements: 6.1_

- [x] 9. Lambda: OCR (Textract)
  - Read files from S3 `data/`
  - Invoke Textract for PDFs/images; read TXT/DOCX directly
  - Store raw text in S3 `temp_processing/raw_text.json`
  - Return S3 key in step output
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 10. Lambda: Chunking
  - Read raw text from S3
  - Split into chunks (200–1000 tokens, sentence boundaries, overlap)
  - Store chunks in S3 `temp_processing/chunks.json`
  - Return S3 key + chunk count
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

- [x] 11. Lambda: Dataset Generation (Bedrock / Gemini)
  - Read a chunk from input (called per chunk via Map state)
  - Generate N training samples using intent-specific prompt templates
  - Assign confidence score per example
  - Return examples array
  - _Requirements: 9.1, 9.3, 9.4, 9.5_

- [x] 12. Lambda: Quality Control
  - Read all generated examples
  - Filter by user-defined quality threshold
  - Store clean JSONL dataset in S3 `temp_processing/clean_dataset.jsonl`
  - Return kept/discarded counts
  - _Requirements: 10.1, 10.2, 10.3, 10.4_

- [x] 13. Lambda: Fine-Tune (SageMaker)
  - Submit SageMaker training job with dataset S3 path + base model
  - Return job name for polling loop
  - On completion: store model artifacts in S3 `models/`, return metrics
  - _Requirements: 11.1, 11.3, 11.4, 11.5_

- [x] 14. Lambda: Deploy (SageMaker Endpoint)
  - Create SageMaker inference endpoint from trained model
  - Return endpoint name + URL
  - _Requirements: 12.1, 12.2, 12.4_

- [x] 15. Lambda: Status Checker (for SageMaker poll loop)
  - Check SageMaker training job status
  - Return status + progress metrics
  - Used by Step Functions wait loop
  - _Requirements: 11.2_

---

### C. Frontend — React + Vite

- [x] 16. Core frontend infrastructure
  - React + Vite + React Router
  - Layout, ThemeProvider, shadcn/ui components
  - Pages: Dashboard, ProjectsList, NewProject, ProjectDetail, Settings
  - _Requirements: 17.3_

- [x] 17. File upload component
  - FileUploadZone with drag-and-drop, format/size validation
  - _Requirements: 4.4, 4.6_

- [x] 18. Mode selection step (NewProjectPage — Step 0)
  - Add mode selector as the first wizard step
  - 4 cards: Dataset Only, Fine-Tune Only, Dataset+FT, Full Pipeline
  - Dynamically show/hide subsequent wizard steps based on mode
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

- [x] 19. Intent selection step (NewProjectPage — Step 1, dataset modes)
  - Intent cards: Q&A, summarization, tone-rewriting, classification, general-assistant
  - Use-case description text area
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 20. Client-side data evaluation (NewProjectPage — Step 2, dataset modes)
  - Parse uploaded files in browser, extract random samples
  - Call `POST /api/evaluate-data` with samples + intent
  - Display quality score, recommendation (fine-tune vs RAG), reasoning
  - Gate upload behind good quality score
  - _Requirements: 3.1, 3.2, 3.4, 3.5, 3.6_

- [x] 21. Presigned URL upload integration (NewProjectPage — Step 3)
  - Request presigned URLs from backend
  - Upload files directly to S3 with progress tracking
  - Handle per-file errors with retry
  - Support JSONL upload for finetune_only mode
  - _Requirements: 4.1, 4.3, 4.4, 4.5, 4.6, 4.7_

- [x] 22. Model selection + config step (NewProjectPage — existing config step)
  - Base model selector (4 models)
  - Samples per chunk slider
  - Quality threshold slider
  - _Requirements: 15.1, 15.2, 15.3, 15.4_

- [x] 23. Pipeline start + review step (NewProjectPage — final step)
  - Review summary of all selections
  - "Start Pipeline" button → calls `POST /api/projects` then `POST /api/projects/{id}/start`
  - Navigate to ProjectDetailPage on success
  - _Requirements: 5.1, 6.1_

- [x] 24. Pipeline tracker (ProjectDetailPage — existing)
  - 7-step pipeline visualization with per-step status
  - Progress bars for running steps
  - Retry buttons for failed steps
  - _Requirements: 6.5, 6.6, 13.3_

- [x] 25. Live status polling (ProjectDetailPage enhancement)
  - Poll `GET /api/projects/{id}/status` on interval
  - Update pipeline tracker with real Step Function execution data (replace mock data)
  - Show per-step durations from execution history
  - _Requirements: 6.5, 6.6, 13.1, 13.2, 13.3_

- [x] 26. Results panel (ProjectDetailPage enhancement)
  - When pipeline completes, show results section:
    - Dataset download link (presigned S3 URL)
    - Model endpoint URL (if deployed)
    - Training metrics (loss, duration)
  - _Requirements: 13.4, 13.5_

- [x] 27. Dataset review page
  - Paginated list of training examples with confidence scores
  - Inline edit for instruction + response
  - Delete per example
  - Search/filter by content
  - Export as JSONL download
  - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6_

- [x] 28. Model comparison page (optional, post-deployment)
  - Side-by-side prompt testing: base model vs fine-tuned model via SageMaker endpoints
  - _Requirements: (stretch goal)_

---

### D. Testing & Integration

- [x] 29. Backend unit tests
  - Test S3 presigned URL generation
  - Test data evaluation endpoint
  - Test Step Functions service (mock boto3)
  - Test project CRUD
  - Test dataset review endpoints

- [x] 30. Frontend integration tests
  - Test mode-adaptive wizard flow
  - Test presigned upload flow (mock S3)
  - Test status polling and pipeline tracker updates

- [x] 31. End-to-end integration test
  - Full pipeline: mode select → evaluate → upload → start → poll status → results
  - Verify S3 artifacts at each step
  - Test all 4 modes

- [x] 32. Final checkpoint
  - All tests pass
  - All 4 modes working end-to-end

## Notes

- Tasks prefixed with section letters (A–D) for clarity
- **A (Backend)**: Thin FastAPI layer — presigned URLs, Step Functions start/poll, project CRUD
- **B (AWS)**: Lambda functions + Step Functions state machine — all heavy processing
- **C (Frontend)**: Mode-adaptive wizard, presigned uploads, live pipeline tracking
- **D (Testing)**: Unit, integration, and e2e tests
- Lambda functions may already have pre-tested static code that needs packaging and deployment
- Frontend tasks can proceed in parallel with backend/Lambda development