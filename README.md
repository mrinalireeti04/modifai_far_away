# modifai-reeti — Critic Agent Contribution

> My personal contribution branch for the **Modifai** AWS Hack2Skill hackathon project.
> Main team repo: [AdvityaDua/aws-hack2skill-modifai](https://github.com/AdvityaDua/aws-hack2skill-modifai)

---

## What This Repo Is

This repository contains **only my parts** of the Modifai project — kept separate so my work-in-progress doesn't interfere with the main team repo.

My role on the team: **P1 — Agent Core** (Critic Agent, Day 2).

---

## What I Built

### The Critic Agent

Modifai generates synthetic training data from uploaded documents. The Critic agent is the **quality gate** — it reads every generated (instruction, input, response) training example and decides:

| Verdict | Meaning |
|---------|---------|
| ✅ `accept` | Sample is specific, grounded, and well-formed — keep it |
| ✏️ `rewrite` | Sample has fixable issues — Critic produces a corrected version |
| ❌ `reject` | Sample is hallucinated or too bad to fix — discard it |

This replaces the old heuristic quality-control step (word-overlap scoring) with an **LLM-powered per-sample verdict** using Amazon Bedrock.

---

## Files in This Repo

```
reeti_modifs/
├── critic_agent.py              # Core Critic agent — the reusable Python module
├── utils.py                     # Logger utility
├── test_critic_agent.py         # 23 unit tests (all mocked, no AWS spend)
├── lambda_critic_handler.py     # AWS Lambda wrapper — plugs into Step Functions
├── lambda_critic_test_local.py  # Mocked tests for the Lambda handler
├── README.md                    # Full Modifai project README (for reference)
└── TODO_SIMPLE.md               # Plain-English breakdown of what's left to build
```

---

## How It Fits Into the Pipeline

```
OCR → Chunking → Dataset Generation → [CRITIC AGENT] → Fine-Tune → Deploy
                                             ↑
                                      My contribution
                                  Replaces: QualityControl Lambda
```

The Critic Lambda (`lambda_critic_handler.py`) is a **drop-in replacement** for the existing `lambdas/quality_control/handler.py` in the main repo. The Step Functions state machine and all downstream steps are completely unchanged — the output schema is identical.

---

## Critic Output Schema

Every sample gets back:

```json
{
  "verdict":          "accept" | "rewrite" | "reject",
  "reason":           "One sentence explaining the decision.",
  "rewritten_output": "Corrected response string, or null.",
  "scores": {
    "specificity": 0.9,
    "grounding":   1.0,
    "format":      1.0
  }
}
```

The batch runner also returns aggregate stats that the frontend dashboard uses:

```json
{
  "accepted":       120,
  "rewritten":       40,
  "rejected":        35,
  "accept_pct":    64.5,
  "rewrite_pct":   21.5,
  "reject_pct":    18.8,
  "survivor_count": 160
}
```

---

## Running the Tests

All tests mock AWS — no credentials or Bedrock spend needed.

**For the core module** (run from the repository root):
```bash
pytest reeti_modifs/test_critic_agent.py -v
```

**For the Lambda handler** (run from the repository root):
```bash
python reeti_modifs/lambda_critic_test_local.py
```

Expected output: all green, no AWS calls made.

---

## How to Plug Into the Main Repo

1. **Copy `critic_agent.py`** → `modifai/core/critic_agent.py`
2. **Copy `test_critic_agent.py`** → `modifai/tests/test_critic_agent.py`
3. **Copy `lambda_critic_handler.py`** → `aws-hack2skill-modifai/lambdas/critic/handler.py`
4. **In `infra/state_machine.json`** — the `QualityControl` state should point to `${CriticLambdaArn}` (already updated in main repo)
5. **In `infra/deploy.sh`** — `critic:handler.handler` is already added to `FUNCS` (already updated in main repo)

---

## Environment Variables (Lambda)

| Variable | Default | Description |
|---|---|---|
| `S3_BUCKET_NAME` | `modifai-bucket` | S3 bucket for dataset files |
| `AWS_REGION` | `ap-south-1` | AWS region |
| `BEDROCK_MODEL_ID` | `amazon.nova-micro-v1:0` | Model used for verdicts |
| `DEFAULT_QC_THRESHOLD` | `0.7` | Min accept% before Curriculum loop kicks in |

---

*Built for AWS Hack2Skill Hackathon · June 2026*
