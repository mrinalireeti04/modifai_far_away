# What Still Needs to Be Built — Modifai

> Plain-English version. No jargon. Just what needs to happen.

---

## The Big Picture

Right now, Modifai has the **brain** — the Python code that reads a PDF, breaks it into pieces, generates questions and answers from it, and filters out the bad ones. That part works and runs on your laptop.

What it does **not** have yet is everything that makes it a real product:
- A website users can visit
- A server that handles requests
- The cloud infrastructure that runs the heavy work automatically
- A way to actually fine-tune and deploy a model

Think of it like this: **the engine exists, but there's no car around it yet.**

---

## 1. The Website (Frontend) — Build the UI

Users need a place to go. Right now there's no website at all.

**What needs to be built:**

- **A step-by-step wizard** where the user picks what they want to do:
  - Just generate a dataset from my documents
  - Fine-tune a model using a dataset I already have
  - Do both (generate dataset + fine-tune)
  - Do everything (generate + fine-tune + deploy a live model)

- **A file upload page** where the user can drag and drop their PDFs

- **A "checking your data" screen** — before uploading, the app should quickly scan a few pages and tell the user: *"Your data looks good for fine-tuning"* or *"This might work better as a search system (RAG) instead"*

- **A progress tracker** — since the pipeline can take 30–60 minutes, the user needs to see live updates like:
  - ✅ Files uploaded
  - ✅ Text extracted
  - ⏳ Generating training examples...
  - ⏳ Fine-tuning model...

- **A results page** where the user can:
  - Download their generated dataset (a `.jsonl` file)
  - See their live model endpoint URL
  - Test their model right in the browser

- **A dashboard** showing all their past projects and their statuses

---

## 2. The Server (Backend) — Handle Requests

The website needs a server behind it to do things like save projects, talk to AWS, and send back status updates.

**What needs to be built:**

- An API (a set of routes the website calls) that can:
  - Accept a document from the user and give back a secure upload link
  - Save a new "project" record to a database
  - Tell AWS to start the pipeline
  - Answer "what's the status of my pipeline?" when the website asks
  - Return the final results (download link, model URL)
  - Let the user delete a project

- A **database** to store projects — who created it, what mode, what stage it's at, what the results are

- **User login** — right now there's no concept of accounts. Users need to sign in so they only see their own projects

---

## 3. The Cloud Pipeline (AWS) — Run the Heavy Work

The pipeline already runs locally on one computer. It needs to be moved to the cloud so it can run on its own, even after the user closes their browser.

This involves setting up several pieces on AWS:

**a) File Storage (S3)**
- A place in the cloud to store uploaded PDFs, intermediate files, and the final dataset
- Done automatically when a user uploads — the server gives them a special secure link to upload directly

**b) The Orchestrator (Step Functions)**
- Think of this as a **to-do list manager in the cloud**
- It knows the order of steps (extract → chunk → generate → quality check → fine-tune → deploy)
- It handles branching: *"If the user only wants a dataset, stop after quality check. If they want the full pipeline, keep going."*
- It can run for hours without needing anyone to babysit it

**c) The Workers (Lambda Functions)**
- Each step in the pipeline needs its own small cloud function:
  - One function to extract text from the uploaded PDF (using AWS Textract)
  - One function to break the text into chunks
  - One function (actually many running in parallel) to generate the training examples
  - One function to filter out the bad examples
  - One function to kick off the fine-tuning job
  - One function to deploy the finished model

**d) Fine-Tuning (SageMaker)**
- Once we have the clean dataset, we need to actually train the model
- This means telling SageMaker: *"Here's the dataset in S3, here's the base model, start training"*
- Training can take 30–90 minutes depending on data size

**e) Deployment (SageMaker Endpoint)**
- After training, the model needs to be turned into a live API that can answer questions
- This means creating an "endpoint" — a URL that you can send a question to and get an answer back

**f) Infrastructure Setup**
- All of the above cloud resources need to be created and configured
- This is usually done with code (CDK or Terraform) so it's repeatable and not done by hand

---

## 4. A Few Technical Improvements to the Existing Code

Even the parts that already work have a couple of rough edges:

- **Large PDF support** — right now, Textract is used in a mode that only handles small documents. For big PDFs (50+ pages), it needs to use a different, slower-but-capable mode
- **Parallel processing** — right now chunks are processed one by one. In the cloud, they should all be processed at the same time to be much faster
- **More file types** — currently only PDFs work. Ideally, Word docs, plain text files, and images should also be supported

---

## Priority Order

If you're starting fresh, here's the recommended order to tackle things:

1. **AWS infrastructure** — set up S3, Step Functions, and the Lambda functions (this is the backbone everything else depends on)
2. **Backend API** — build the FastAPI server so the frontend has something to talk to
3. **Frontend** — build the website
4. **Polish** — add login, notifications, dataset editor, inference playground

---

## Summary Table

| What | Status | Effort |
|------|--------|--------|
| Python pipeline (local) | ✅ Done | — |
| AWS cloud pipeline (Lambdas + Step Functions) | ❌ Not started | Large |
| SageMaker fine-tuning integration | ❌ Not started | Large |
| SageMaker model deployment | ❌ Not started | Medium |
| Backend API server | ❌ Not started | Large |
| User login / accounts | ❌ Not started | Medium |
| Website / UI | ❌ Not started | Large |
| Large PDF support | ⚠️ Needs fix | Small |
| Parallel processing in cloud | ⚠️ Needs fix | Small |
