"""
Critic Lambda — modifai-critic
================================
Replaces the QualityControl Lambda in the Step Functions state machine.

This Lambda wraps the Critic agent (LLM-powered verdict per sample) to run
after dataset generation. It:
  1. Reads generated examples + source chunks from S3
  2. Runs deduplication (same as the old QC Lambda — unchanged)
  3. Runs the Critic agent in batch over all deduplicated samples
  4. Writes survivors (accepted + rewritten) as clean_dataset.jsonl to S3
  5. Returns updated Step Functions state with critic stats

Drop-in replacement for lambdas/quality_control/handler.py.
The output schema is IDENTICAL to the old QC Lambda so nothing downstream breaks.

Input (Step Functions event — identical to QC Lambda):
{
    "project_id": "proj-abc123",
    "s3_prefix": "user-uuid/proj-uuid/",
    "mode": "dataset_only | dataset_and_finetune | full",
    "config": {
        "quality_threshold": 0.7,       # Minimum accept% to skip Curriculum loop
        "bedrock_model_id": "amazon.nova-micro-v1:0",
        ...
    },
    "step_results": {
        "chunking":    { "chunks_key": "temp_processing/chunks.json", ... },
        "generation":  { "examples_key": "temp_processing/examples.json", ... }
    }
}

Output (same shape as old QC Lambda + extra critic_stats for P3 dashboard):
{
    ...event (pass-through),
    "step_results": {
        ...step_results,
        "quality_control": {
            "clean_dataset_key":  "temp_processing/clean_dataset.jsonl",
            "total_input":         200,
            "duplicates_removed":    5,
            "kept":                160,   # survivors (accepted + rewritten)
            "discarded":            35,   # rejected by Critic
            "threshold":           0.7,
            "critic_stats": {             # NEW — for P3 live dashboard chart
                "accepted":   120,
                "rewritten":   40,
                "rejected":    35,
                "accept_pct":  64.5,
                "rewrite_pct": 21.5,
                "reject_pct":  18.8,
                "survivor_count": 160
            }
        }
    }
}
"""

import json
import logging
import os
import re

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ── Environment variables (set by deploy.sh / CDK) ──────────────────────────
BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "modifai-bucket")
AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")
DEFAULT_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-micro-v1:0")
DEFAULT_QC_THRESHOLD = float(os.environ.get("DEFAULT_QC_THRESHOLD", "0.7"))

# ── Lambda entry point ────────────────────────────────────────────────────────

def handler(event, context):
    """
    Lambda entry point for the Critic quality-control step.
    Replaces the old QualityControl Lambda — same input/output contract.

    Clients are created inside the handler (not at module level) so that
    unit tests can patch boto3.client cleanly.
    """
    project_id = event.get("project_id", "unknown")
    logger.info(f"Critic Lambda invoked for project: {project_id}")

    s3_prefix = event["s3_prefix"]
    config = event.get("config", {})
    threshold = config.get("quality_threshold", DEFAULT_QC_THRESHOLD)
    model_id = config.get("bedrock_model_id", DEFAULT_MODEL_ID)

    s3_client = boto3.client("s3", region_name=AWS_REGION)

    # ── 1. Read examples from S3 ──────────────────────────────────────────
    examples_key = (
        f"{s3_prefix}{event['step_results']['generation']['examples_key']}"
    )
    logger.info(f"Reading examples from s3://{BUCKET_NAME}/{examples_key}")
    resp = s3_client.get_object(Bucket=BUCKET_NAME, Key=examples_key)
    examples = json.loads(resp["Body"].read().decode("utf-8"))
    total_input = len(examples)
    logger.info(f"Loaded {total_input} examples")

    # ── 2. Read chunks from S3 ────────────────────────────────────────────
    chunks_key = (
        f"{s3_prefix}{event['step_results']['chunking']['chunks_key']}"
    )
    logger.info(f"Reading chunks from s3://{BUCKET_NAME}/{chunks_key}")
    resp = s3_client.get_object(Bucket=BUCKET_NAME, Key=chunks_key)
    chunks = json.loads(resp["Body"].read().decode("utf-8"))
    logger.info(f"Loaded {len(chunks)} chunks")

    # ── 3. Deduplication (unchanged from old QC Lambda) ───────────────────
    deduped = _remove_duplicates(examples)
    duplicates_removed = total_input - len(deduped)
    logger.info(
        f"Deduplication: {total_input} → {len(deduped)} "
        f"({duplicates_removed} duplicates removed)"
    )

    # ── 4. Critic batch ───────────────────────────────────────────────────
    logger.info(
        f"Running Critic batch over {len(deduped)} samples "
        f"using model {model_id}"
    )
    critic_output = _run_critic_batch(deduped, chunks, AWS_REGION, model_id)
    survivors = critic_output["survivors"]
    critic_stats = critic_output["stats"]

    kept = len(survivors)
    discarded = len(deduped) - kept
    logger.info(
        f"Critic complete — kept: {kept}, discarded: {discarded} "
        f"(accept: {critic_stats['accept_pct']}%, "
        f"rewrite: {critic_stats['rewrite_pct']}%, "
        f"reject: {critic_stats['reject_pct']}%)"
    )

    # ── 5. Write clean dataset as JSONL to S3 ────────────────────────────
    output_key = f"{s3_prefix}temp_processing/clean_dataset.jsonl"
    jsonl_lines = [json.dumps(item, ensure_ascii=False) for item in survivors]
    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=output_key,
        Body="\n".join(jsonl_lines),
        ContentType="application/jsonl",
    )
    logger.info(f"Clean dataset written to s3://{BUCKET_NAME}/{output_key}")

    # ── 6. Return updated Step Functions state ────────────────────────────
    event.setdefault("step_results", {})
    event["step_results"]["quality_control"] = {
        # Core fields — same as old QC Lambda (downstream Lambda compatibility)
        "clean_dataset_key":  "temp_processing/clean_dataset.jsonl",
        "total_input":         total_input,
        "duplicates_removed":  duplicates_removed,
        "kept":                kept,
        "discarded":           discarded,
        "threshold":           threshold,
        # Extra field — Critic-specific stats for P3 frontend dashboard
        "critic_stats":        critic_stats,
    }
    return event


# ── Deduplication (copied verbatim from quality_control/handler.py) ──────────
# Kept inline so this Lambda is self-contained and deployable independently.

def _remove_duplicates(examples: list) -> list:
    """Remove exact duplicates based on normalized instruction+input+response."""
    seen = set()
    unique = []
    for ex in examples:
        key = (
            str(ex.get("instruction", "")).strip().lower()
            + str(ex.get("input", "")).strip().lower()
            + str(ex.get("response", "")).strip().lower()
        )
        if key not in seen:
            seen.add(key)
            unique.append(ex)
    return unique


# ── Critic agent (self-contained, no local package dependency) ───────────────
# The full logic from modifai/core/critic_agent.py is inlined here so the
# Lambda ZIP has zero external package dependencies beyond boto3.

CRITIC_SYSTEM_PROMPT = """You are a rigorous training-data quality critic for an LLM fine-tuning pipeline.

Your job is to evaluate a single training example — an (instruction, input, response) triple — against the source document chunk it was generated from.

You must judge three dimensions:

1. SPECIFICITY  (0.0 – 1.0)
   Does the response give a precise, concrete answer, or is it vague and generic?
   - 1.0 = highly specific, mentions entities/numbers/steps from the chunk
   - 0.5 = partially specific but misses key details
   - 0.0 = completely generic ("It depends", "Please refer to the document", etc.)

2. GROUNDING  (0.0 – 1.0)
   Is every claim in the response supported by the source chunk?
   - 1.0 = every fact comes directly from the chunk
   - 0.5 = mostly grounded but includes one unsupported inference
   - 0.0 = fabricates facts not in the chunk

3. FORMAT  (0.0 – 1.0)
   Is the response a complete, well-formed answer to the instruction?
   - 1.0 = grammatically complete, directly answers the question
   - 0.5 = partially answers or has minor truncation/awkward phrasing
   - 0.0 = incomplete sentence, just a list of keywords, or does not answer

VERDICT RULES (apply in order):
- If grounding < 0.4: REJECT — hallucination risk is too high to fix safely
- If specificity < 0.4 AND format < 0.5: REJECT — not worth fixing
- If any score < 0.6: REWRITE — produce a corrected response grounded in the chunk
- Otherwise: ACCEPT

REWRITE RULES (critical — failure here breaks the pipeline):
- ONLY use information present in the source chunk
- Do NOT invent facts, examples, or numbers not in the chunk
- Keep the same instruction; only fix the response
- If you cannot write a grounded rewrite, REJECT instead

Respond with ONLY a valid JSON object. No markdown, no explanation outside the JSON.

JSON schema:
{
  "verdict": "accept" | "rewrite" | "reject",
  "reason": "<one sentence>",
  "rewritten_output": "<corrected response string>" | null,
  "scores": {
    "specificity": <float 0.0-1.0>,
    "grounding": <float 0.0-1.0>,
    "format": <float 0.0-1.0>
  }
}"""


def _build_critic_message(sample: dict, chunk_text: str) -> str:
    return (
        f"SOURCE CHUNK:\n{chunk_text}\n\n"
        f"INSTRUCTION: {sample.get('instruction', '')}\n"
        f"INPUT: {sample.get('input', '')}\n"
        f"RESPONSE: {sample.get('response', '')}"
    )


def _parse_verdict(raw: str):
    """Parse and validate a Critic LLM response. Returns None on failure."""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?", "", text).rstrip("`").strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not {"verdict", "reason", "scores"}.issubset(parsed.keys()):
        return None
    if parsed.get("verdict") not in ("accept", "rewrite", "reject"):
        return None
    parsed.setdefault("rewritten_output", None)
    if parsed["verdict"] != "rewrite":
        parsed["rewritten_output"] = None
    return parsed


def _critique_one(sample: dict, chunk_text: str, region: str, model_id: str) -> dict:
    """Call the Critic LLM on a single sample. Fail-safe to REJECT on error."""
    bedrock = boto3.client("bedrock-runtime", region_name=region)
    user_msg = _build_critic_message(sample, chunk_text)

    for attempt in range(2):  # 1 retry on malformed JSON
        try:
            response = bedrock.converse(
                modelId=model_id,
                system=[{"text": CRITIC_SYSTEM_PROMPT}],
                messages=[{"role": "user", "content": [{"text": user_msg}]}],
                inferenceConfig={"temperature": 0.0, "maxTokens": 600},
            )
            raw = response["output"]["message"]["content"][0]["text"]
            verdict = _parse_verdict(raw)
            if verdict is not None:
                return verdict
            logger.warning(
                f"Malformed Critic response on attempt {attempt + 1}: {raw[:200]}"
            )
        except Exception as exc:
            logger.error(f"Bedrock call failed on attempt {attempt + 1}: {exc}")

    # All retries exhausted
    return {
        "verdict": "reject",
        "reason": "Critic LLM failed to return a valid response after retries.",
        "rewritten_output": None,
        "scores": {"specificity": 0.0, "grounding": 0.0, "format": 0.0},
    }


def _run_critic_batch(
    dataset: list, chunks: list, region: str, model_id: str
) -> dict:
    """
    Run the Critic over every sample. Returns:
      { "survivors": [...], "stats": {...} }
    """
    chunk_lookup = {c["chunk_id"]: c["text"] for c in chunks}
    survivors = []
    accept_count = rewrite_count = reject_count = 0

    for i, sample in enumerate(dataset):
        chunk_id = sample.get("chunk_id")
        chunk_text = chunk_lookup.get(chunk_id, "")

        if not chunk_text:
            logger.warning(
                f"Sample {i} has unknown chunk_id={chunk_id} — auto-rejecting"
            )
            reject_count += 1
            continue

        verdict_dict = _critique_one(sample, chunk_text, region, model_id)
        verdict = verdict_dict["verdict"]

        if verdict == "accept":
            accept_count += 1
            survivors.append(sample)
        elif verdict == "rewrite":
            rewrite_count += 1
            rewritten = dict(sample)
            rewritten["response"] = verdict_dict["rewritten_output"]
            rewritten["_critic_rewritten"] = True
            survivors.append(rewritten)
        else:
            reject_count += 1

    total = len(dataset)
    stats = {
        "accepted":       accept_count,
        "rewritten":      rewrite_count,
        "rejected":       reject_count,
        "accept_pct":     round(accept_count / total * 100, 1) if total else 0.0,
        "rewrite_pct":    round(rewrite_count / total * 100, 1) if total else 0.0,
        "reject_pct":     round(reject_count / total * 100, 1) if total else 0.0,
        "survivor_count": len(survivors),
    }
    return {"survivors": survivors, "stats": stats}
