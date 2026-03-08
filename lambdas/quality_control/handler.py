"""
Quality Control Lambda — Deduplicates, scores, and filters generated training examples.

Input (from Step Functions — output of generation collector):
{
    ...state,
    "step_results": {
        "chunking": { "chunks_key": "temp_processing/chunks.json", ... },
        "generation": { "examples_key": "temp_processing/examples.json", ... }
    }
}

Output:
{
    ...state,
    "step_results": {
        ...step_results,
        "quality_control": {
            "clean_dataset_key": "temp_processing/clean_dataset.jsonl",
            "kept": 160,
            "discarded": 35,
            "duplicates_removed": 5,
            "total_input": 200
        }
    }
}
"""

import json
import re
import os
import logging
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "modifai-bucket")
AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")

s3_client = boto3.client("s3", region_name=AWS_REGION)

DEFAULT_QC_THRESHOLD = 0.6


def handler(event, context):
    """Lambda entry point for quality control step."""
    logger.info(f"QC Lambda invoked for project: {event.get('project_id')}")

    s3_prefix = event["s3_prefix"]
    config = event.get("config", {})
    threshold = config.get("quality_threshold", DEFAULT_QC_THRESHOLD)

    # 1. Read examples from S3
    examples_key = f"{s3_prefix}{event['step_results']['generation']['examples_key']}"
    logger.info(f"Reading examples from s3://{BUCKET_NAME}/{examples_key}")
    response = s3_client.get_object(Bucket=BUCKET_NAME, Key=examples_key)
    examples = json.loads(response["Body"].read().decode("utf-8"))
    total_input = len(examples)

    # 2. Read chunks from S3 (needed for overlap scoring)
    chunks_key = f"{s3_prefix}{event['step_results']['chunking']['chunks_key']}"
    logger.info(f"Reading chunks from s3://{BUCKET_NAME}/{chunks_key}")
    response = s3_client.get_object(Bucket=BUCKET_NAME, Key=chunks_key)
    chunks = json.loads(response["Body"].read().decode("utf-8"))
    chunk_lookup = {c["chunk_id"]: c["text"] for c in chunks}

    # 3. Pass 1: Remove duplicates
    deduped = remove_duplicates(examples)
    duplicates_removed = total_input - len(deduped)
    logger.info(f"Dedup: {total_input} → {len(deduped)} ({duplicates_removed} removed)")

    # 4. Pass 2: Score and filter
    scored = score_examples(deduped, chunk_lookup)
    kept = [item for item in scored if item["confidence_score"] >= threshold]
    discarded = len(scored) - len(kept)
    logger.info(f"Filter (threshold={threshold}): {len(scored)} → {len(kept)} ({discarded} discarded)")

    # 5. Write clean dataset as JSONL to S3
    output_key = f"{s3_prefix}temp_processing/clean_dataset.jsonl"
    jsonl_lines = [json.dumps(item, ensure_ascii=False) for item in kept]
    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=output_key,
        Body="\n".join(jsonl_lines),
        ContentType="application/jsonl",
    )
    logger.info(f"Clean dataset written to s3://{BUCKET_NAME}/{output_key}")

    # 6. Return updated state
    event.setdefault("step_results", {})
    event["step_results"]["quality_control"] = {
        "clean_dataset_key": "temp_processing/clean_dataset.jsonl",
        "total_input": total_input,
        "duplicates_removed": duplicates_removed,
        "kept": len(kept),
        "discarded": discarded,
        "threshold": threshold,
    }
    return event


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def remove_duplicates(examples: list[dict]) -> list[dict]:
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


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def tokenize(text: str) -> set[str]:
    """Tokenize text into a set of lowercased words."""
    return set(re.findall(r"\b\w+\b", str(text).lower()))


def compute_overlap_score(example: dict, chunk_text: str) -> float:
    """
    Measures vocabulary overlap between response and source chunk.
    High overlap = response is grounded in source.
    """
    response_words = tokenize(example.get("response", ""))
    chunk_words = tokenize(chunk_text)

    if not response_words:
        return 0.0

    overlap = response_words & chunk_words
    return len(overlap) / len(response_words)


def compute_length_score(example: dict) -> float:
    """
    Penalizes very short responses.
    A 1-word answer scores ~0.01, an 80+ word answer scores 1.0.
    """
    words = len(str(example.get("response", "")).split())
    return min(words / 80, 1.0)


def compute_structural_score(example: dict) -> float:
    """
    Checks required fields exist and response has minimum length.
    """
    if not all(k in example for k in ("instruction", "input", "response")):
        return 0.0
    if len(str(example.get("response", "")).strip()) < 20:
        return 0.2
    return 1.0


def score_examples(examples: list[dict], chunk_lookup: dict) -> list[dict]:
    """
    Score each example using the 3-metric weighted formula.
    Attaches confidence_score to each example for downstream use.

    Formula: 0.5 * overlap + 0.3 * length + 0.2 * structural
    """
    scored = []

    for ex in examples:
        chunk_text = chunk_lookup.get(ex.get("chunk_id"), "")

        overlap = compute_overlap_score(ex, chunk_text)
        length = compute_length_score(ex)
        structural = compute_structural_score(ex)

        score = round(0.5 * overlap + 0.3 * length + 0.2 * structural, 3)

        # Attach score to the example itself
        ex["confidence_score"] = score
        scored.append(ex)

    return scored
