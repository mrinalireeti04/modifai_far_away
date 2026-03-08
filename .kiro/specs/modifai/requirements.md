# Requirements Document: Modifai

## Introduction

Modifai is a no-code platform that automates end-to-end LLM fine-tuning pipeline creation. Users select an execution mode, provide data (documents or datasets), and the platform handles everything — from OCR and chunking to synthetic dataset generation, quality control, fine-tuning on AWS SageMaker, and deployment — orchestrated by AWS Step Functions. The backend (FastAPI) is a thin API layer; all heavy processing runs on Lambda + AWS services.

## Glossary

- **System**: The Modifai platform
- **User**: A person interacting with the platform
- **Mode**: Execution mode — Dataset Only, Fine-Tune Only, Dataset + Fine-Tune, or Full Pipeline
- **Intent**: The task type the model will be fine-tuned for (Q&A, summarization, classification, tone-rewriting, general-assistant)
- **Document**: A file uploaded by the user (PDF, TXT, DOCX, or image format)
- **Chunk**: A semantically meaningful segment of text extracted from a document
- **Training_Example**: A paired instruction-response data point used for fine-tuning
- **Dataset**: A JSONL collection of training examples
- **Confidence_Score**: A quality metric assigned to each generated training example
- **Threshold**: User-defined minimum confidence score; examples below are discarded
- **Presigned_URL**: A time-limited S3 URL that allows the frontend to upload files directly without routing through the backend
- **Step_Function**: AWS Step Functions state machine that orchestrates the pipeline
- **Execution**: A single run of the Step Function state machine for a project

## Requirements

### Requirement 1: Execution Mode Selection

**User Story:** As a user, I want to choose what the platform should do for me so that I only provide the inputs that are needed.

#### Acceptance Criteria

1. THE System SHALL present four execution modes as the first step: Dataset Only, Fine-Tune Only, Dataset + Fine-Tune, Full Pipeline
2. WHEN a user selects a mode, THE System SHALL adapt the input wizard to show only the relevant steps for that mode
3. WHEN the mode is Fine-Tune Only, THE System SHALL skip intent selection and data evaluation, and prompt for a JSONL dataset upload instead
4. WHEN the mode includes dataset generation (Dataset Only, Dataset+FT, Full), THE System SHALL require intent selection, use-case description, and document uploads
5. WHEN the mode includes fine-tuning, THE System SHALL require base model selection
6. WHEN the mode is Full Pipeline, THE System SHALL additionally collect deployment configuration

### Requirement 2: Intent Selection and Use-Case Description

**User Story:** As a user, I want to specify what task my model should perform and how I intend to use it so that the system generates appropriate training data.

#### Acceptance Criteria

1. THE System SHALL provide predefined intent options: question-answering, summarization, tone-rewriting, classification, general-assistant
2. THE System SHALL display a description for each intent option to guide user selection
3. THE System SHALL require a free-text use-case description from the user
4. WHEN a user selects an intent and provides a description, THE System SHALL store both for the data evaluation and generation steps

### Requirement 3: Client-Side Data Evaluation

**User Story:** As a user, I want to know whether my data is suitable for fine-tuning before I commit to uploading so that I don't waste time on bad data.

#### Acceptance Criteria

1. WHEN the user adds files in the browser (dataset generation modes), THE System frontend SHALL parse files locally and extract random content samples
2. THE System SHALL send the samples along with the selected intent and use-case description to the backend evaluation endpoint
3. THE backend SHALL forward the samples + intent to an LLM (Bedrock / Gemini) and request: a quality score (1–10), whether the data fits the intent, and whether fine-tuning or RAG is a better approach
4. THE System SHALL display the quality score, recommendation, and reasoning to the user
5. WHEN the quality score meets the threshold, THE System SHALL allow the user to proceed to upload
6. WHEN the quality score is poor, THE System SHALL display guidance explaining why and suggest alternatives

### Requirement 4: File Upload via Presigned S3 URLs

**User Story:** As a user, I want to upload my files directly to cloud storage so that uploads are fast and don't bottleneck through the backend.

#### Acceptance Criteria

1. WHEN the user is ready to upload, THE System SHALL request presigned S3 PUT URLs from the backend for each file
2. THE backend SHALL generate presigned URLs pointing to `s3://modifai-bucket/{user_uuid}/{project_uuid}/data/`
3. THE frontend SHALL upload each file directly to S3 using the presigned URLs
4. THE System SHALL display upload progress per file
5. WHEN all uploads complete, THE System SHALL confirm success and enable the pipeline start action
6. WHEN an upload fails, THE System SHALL display an error and allow retry
7. WHEN the mode is Fine-Tune Only, THE System SHALL upload a JSONL dataset file instead of documents

### Requirement 5: Project Creation

**User Story:** As a user, I want to create a project to track my pipeline run so that I can manage multiple pipelines and revisit results.

#### Acceptance Criteria

1. THE System SHALL create a project record with: name, mode, intent, description, config, S3 keys, and status
2. THE System SHALL assign a unique project ID
3. THE System SHALL store the project in a persistent database
4. THE System SHALL allow listing, viewing, and deleting projects

### Requirement 6: Pipeline Execution via Step Functions

**User Story:** As a user, I want the pipeline to run independently so that I can close the browser and come back later.

#### Acceptance Criteria

1. WHEN the user starts the pipeline, THE System backend SHALL start an AWS Step Function execution with the project's mode, config, and S3 keys as input
2. THE Step Function SHALL use Choice states to include or skip steps based on the execution mode
3. WHEN the execution starts, THE System SHALL return the execution ARN to the frontend
4. THE System SHALL allow the user to close the browser without affecting the pipeline
5. WHEN the user returns, THE System SHALL display the current pipeline state by polling the Step Function execution status
6. THE System SHALL show per-step progress: which step is running, completed steps with duration, and any errors

### Requirement 7: OCR — Text Extraction (Lambda + Textract)

**User Story:** As a user, I want the system to extract text from my uploaded documents automatically.

#### Acceptance Criteria

1. THE Lambda function SHALL read uploaded files from S3 and invoke AWS Textract for PDF and image files
2. THE Lambda function SHALL read TXT and DOCX files directly without Textract
3. WHEN extraction completes, THE Lambda function SHALL store the raw text in S3 under `temp_processing/`
4. WHEN extraction fails, THE Lambda function SHALL return an error that the Step Function surfaces to the user
5. This step SHALL only execute when the mode includes dataset generation

### Requirement 8: Intelligent Text Chunking (Lambda)

**User Story:** As a user, I want documents broken into meaningful segments so that training examples are coherent.

#### Acceptance Criteria

1. THE Lambda function SHALL split extracted text into chunks based on semantic boundaries
2. THE Lambda function SHALL maintain a target chunk size of 200–1000 tokens
3. THE Lambda function SHALL split at sentence boundaries when exceeding the maximum
4. THE Lambda function SHALL merge undersized chunks with adjacent ones
5. THE Lambda function SHALL include overlapping content between consecutive chunks for context
6. WHEN chunking is complete, THE Lambda function SHALL store all chunks with metadata in S3 under `temp_processing/`

### Requirement 9: Synthetic Dataset Generation (Lambda + Bedrock/Gemini)

**User Story:** As a user, I want the system to automatically create training examples from my documents.

#### Acceptance Criteria

1. THE Lambda function SHALL generate N training samples per chunk (default N=5, configurable by user) using an LLM via Bedrock or Gemini
2. THE Step Function SHALL use a Map state to parallelize generation across chunks
3. THE Lambda function SHALL use intent-specific prompt templates for each generation
4. THE Lambda function SHALL assign a confidence score to each generated training example
5. WHEN generation fails for a chunk, THE Lambda function SHALL log the failure and continue with remaining chunks
6. WHEN generation completes, THE Lambda function SHALL store all examples with confidence scores in S3

### Requirement 10: Quality Control (Lambda)

**User Story:** As a user, I want low-quality training examples filtered out so that my dataset is clean.

#### Acceptance Criteria

1. THE Lambda function SHALL filter examples by the user-defined quality threshold
2. WHEN an example's confidence score is below the threshold, THE Lambda function SHALL discard it
3. THE Lambda function SHALL store the clean dataset as JSONL in S3 under `temp_processing/clean_dataset.jsonl`
4. THE Lambda function SHALL include kept/discarded counts in its output for the Step Function state

### Requirement 11: Model Fine-Tuning (Lambda + SageMaker)

**User Story:** As a user, I want the system to fine-tune a model on my dataset using SageMaker.

#### Acceptance Criteria

1. THE Lambda function SHALL submit a SageMaker training job using the clean dataset from S3 and the selected base model
2. THE Step Function SHALL implement a polling loop (check status → wait → repeat) until the training job completes
3. WHEN training completes, THE Lambda function SHALL store model artifacts in S3 under `models/`
4. WHEN training completes, THE Lambda function SHALL capture metadata: duration, final loss
5. WHEN training fails, THE Lambda function SHALL return the SageMaker failure reason
6. This step SHALL only execute when the mode includes fine-tuning

### Requirement 12: Model Deployment (Lambda + SageMaker)

**User Story:** As a user, I want my fine-tuned model deployed as an API endpoint so I can use it immediately.

#### Acceptance Criteria

1. THE Lambda function SHALL create a SageMaker inference endpoint using the trained model artifacts
2. WHEN the endpoint is live, THE Lambda function SHALL return the endpoint name and URL
3. This step SHALL only execute when the mode is Full Pipeline
4. THE System SHALL surface the endpoint URL to the user in the project results

### Requirement 13: Pipeline Status and Results

**User Story:** As a user, I want to see live progress and final results of my pipeline run.

#### Acceptance Criteria

1. THE System SHALL expose a status endpoint that queries the Step Function execution history
2. THE System SHALL return: current step, per-step status (pending/running/complete/error), step durations, and step outputs
3. THE frontend SHALL render a real-time pipeline tracker with this information
4. WHEN the pipeline completes, THE System SHALL expose results: dataset download URL (presigned), model endpoint URL, and training metrics
5. WHEN any step fails, THE System SHALL display the error reason and allow the user to view logs

### Requirement 14: Dataset Review and Editing

**User Story:** As a user, I want to review and modify generated training examples before fine-tuning.

#### Acceptance Criteria

1. THE System SHALL display all generated training examples in a reviewable interface with confidence scores
2. THE System SHALL allow editing of both instruction and response text
3. THE System SHALL allow deleting individual examples
4. THE System SHALL display the total count of training examples
5. THE System SHALL allow filtering or searching training examples by content
6. THE System SHALL allow exporting the dataset as JSONL download

### Requirement 15: Base Model Selection

**User Story:** As a user, I want to choose which model to fine-tune.

#### Acceptance Criteria

1. THE System SHALL provide a selection interface for available base models compatible with SageMaker
2. THE System SHALL support at least two base model options
3. WHEN displaying models, THE System SHALL show model name, size, and recommended use cases
4. WHEN a user selects a base model, THE System SHALL store the selection in the project config

### Requirement 16: Error Handling and User Feedback

**User Story:** As a user, I want clear feedback when errors occur.

#### Acceptance Criteria

1. WHEN any operation fails, THE System SHALL display a user-friendly error message
2. THE System SHALL avoid exposing stack traces or internal AWS error details to users
3. WHEN an error is recoverable, THE System SHALL provide actionable guidance
4. THE System SHALL log all errors with full detail for debugging
5. WHEN a long-running operation is in progress, THE System SHALL provide progress indicators

### Requirement 17: Project and Session Management

**User Story:** As a user, I want my projects persisted so I can come back anytime.

#### Acceptance Criteria

1. THE System SHALL persist all project data (metadata, config, S3 references, Step Function ARN) in a database
2. THE System SHALL allow users to list all their projects with status
3. THE System SHALL allow navigation between projects without data loss
4. THE System SHALL organize all S3 data under `s3://modifai-bucket/{user_uuid}/{project_uuid}/`
