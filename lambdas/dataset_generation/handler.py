"""
Dataset Generation Lambda — Generates training samples for a SINGLE chunk via Bedrock.

This Lambda is invoked by a Step Functions Map state, once per chunk.

Input (from Map state):
{
    "chunk": {
        "chunk_id": 7,
        "text": "...",
        "source_file": "report.pdf",
        "word_count": 342
    },
    "config": {
        "intent": "question-answering",
        "description": "Customer support bot for SaaS docs",
        "samples_per_chunk": 5,
        "model_id": "amazon.nova-micro-v1:0"
    }
}

Output (collected by Map state):
{
    "chunk_id": 7,
    "samples": [
        { "instruction": "...", "input": "", "response": "...", "chunk_id": 7, "source_file": "report.pdf" },
        ...
    ],
    "count": 5
}
"""

import json
import re
import os
import logging
import boto3
import uuid

logger = logging.getLogger()
logger.setLevel(logging.INFO)

AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")
BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "modifai-bucket")
DEFAULT_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "apac.amazon.nova-micro-v1:0")

s3_client = boto3.client("s3", region_name=AWS_REGION)
bedrock_client = boto3.client("bedrock-runtime", region_name=AWS_REGION)


# ---------------------------------------------------------------------------
# Intent-specific prompt templates
# ---------------------------------------------------------------------------

PROMPT_TEMPLATES = {
    "question-answering": """You are an expert training data generator. Based on the following source text, generate exactly {n} high-quality question-answer pairs.

The questions should be specific, clear, and answerable ONLY from the source text.
The answers must be detailed, accurate, and grounded in the source text.

Respond STRICTLY as a JSON array:
[
    {{"instruction": "The question", "input": "", "response": "The detailed answer"}}
]

No markdown, no explanations, just valid JSON.

Source Text:
{text}""",

    "summarization": """You are an expert training data generator. Based on the following source text, generate exactly {n} summarization training pairs.

Each pair should have an instruction asking to summarize a specific aspect of the text, and a response containing a concise, accurate summary grounded in the source.

Respond STRICTLY as a JSON array:
[
    {{"instruction": "Summarize ...", "input": "", "response": "The summary"}}
]

No markdown, no explanations, just valid JSON.

Source Text:
{text}""",

    "classification": """You are an expert training data generator. Based on the following source text, generate exactly {n} classification training pairs.

Each pair should have a text snippet as input and a classification label/category as the response, based on the content in the source text.

Respond STRICTLY as a JSON array:
[
    {{"instruction": "Classify the following text", "input": "The text to classify", "response": "The category/label"}}
]

No markdown, no explanations, just valid JSON.

Source Text:
{text}""",

    "tone-rewriting": """You are an expert training data generator. Based on the following source text, generate exactly {n} tone-rewriting training pairs.

Each pair should take a sentence from or inspired by the source and rewrite it in a different tone (e.g., formal to casual, technical to simple, negative to positive).

Respond STRICTLY as a JSON array:
[
    {{"instruction": "Rewrite the following in a [tone] tone", "input": "Original text", "response": "Rewritten text"}}
]

No markdown, no explanations, just valid JSON.

Source Text:
{text}""",

    "general-assistant": """You are an expert training data generator. Based on the following source text, generate exactly {n} high-quality instruction-response training pairs.

The instructions can be questions, tasks, or requests that a helpful AI assistant should be able to answer using the source text. Responses should be helpful, accurate, and well-structured.

Respond STRICTLY as a JSON array:
[
    {{"instruction": "The instruction or question", "input": "", "response": "The helpful response"}}
]

No markdown, no explanations, just valid JSON.

Source Text:
{text}""",
}


def handler(event, context):
    """Lambda entry point — processes one chunk, returns generated samples."""
    chunk_index = event.get("chunk_index")
    chunks_key = event.get("chunks_key")
    config = event.get("config", {})

    # 1. Load chunk data
    # If using pass-by-reference indices to avoid Step Functions payload limits
    if chunk_index is not None and chunks_key:
        try:
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=chunks_key)
            chunks = json.loads(response["Body"].read().decode("utf-8"))
            chunk = chunks[chunk_index]
        except Exception as e:
            logger.error(f"Failed to fetch chunk {chunk_index} from S3: {e}")
            return {"chunk_id": -1, "samples": [], "count": 0, "error": f"S3 fetch failed: {str(e)}"}
    else:
        # Fallback to direct chunk object in event
        chunk = event.get("chunk", {})

    if not chunk:
        logger.error("No chunk data found in event or S3")
        return {"chunk_id": -1, "samples": [], "count": 0, "error": "No chunk data found"}

    chunk_id = chunk["chunk_id"]
    chunk_text = chunk["text"]
    source_file = chunk.get("source_file", "unknown")

    intent = config.get("intent", "question-answering")
    samples_per_chunk = config.get("samples_per_chunk", 5)
    model_id = config.get("model_id", DEFAULT_MODEL_ID)

    logger.info(
        f"Generating {samples_per_chunk} samples for chunk {chunk_id} "
        f"(intent={intent}, model={model_id})"
    )

    try:
        samples = generate_samples(
            text=chunk_text,
            intent=intent,
            n=samples_per_chunk,
            model_id=model_id,
        )

        # Tag each sample with provenance
        for sample in samples:
            sample["chunk_id"] = chunk_id
            sample["source_file"] = source_file

        logger.info(f"Generated {len(samples)} samples for chunk {chunk_id}")

        # NEW: Write results to S3 to avoid Map state output limit
        s3_prefix = event.get("s3_prefix", "temp/")
        result_filename = f"generation_results/result_{chunk_id}_{uuid.uuid4().hex[:8]}.json"
        result_key = f"{s3_prefix}{result_filename}"
        
        result_body = {
            "chunk_id": chunk_id,
            "samples": samples,
            "count": len(samples)
        }
        
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=result_key,
            Body=json.dumps(result_body, ensure_ascii=False),
            ContentType="application/json"
        )

        return {
            "chunk_id": chunk_id,
            "result_key": result_key,
            "count": len(samples),
        }

    except Exception as e:
        logger.error(f"Failed to generate samples for chunk {chunk_id}: {e}")
        return {
            "chunk_id": chunk_id,
            "samples": [], # Keep for backward compatibility if collector isn't updated? No, collector will be.
            "count": 0,
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Generation logic
# ---------------------------------------------------------------------------


def generate_samples(text: str, intent: str, n: int, model_id: str) -> list[dict]:
    """Call Bedrock converse API to generate training samples for a chunk."""

    # Pick the prompt template for this intent
    template = PROMPT_TEMPLATES.get(intent, PROMPT_TEMPLATES["general-assistant"])
    prompt = template.format(n=n, text=text)

    response = bedrock_client.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"temperature": 0.7, "maxTokens": 2000},
    )

    response_text = response["output"]["message"]["content"][0]["text"]
    samples = parse_json_response(response_text)

    # Validate structure
    validated = []
    for sample in samples:
        if isinstance(sample, dict) and "instruction" in sample and "response" in sample:
            validated.append({
                "instruction": str(sample["instruction"]),
                "input": str(sample.get("input", "")),
                "response": str(sample["response"]),
            })

    return validated


def parse_json_response(text: str) -> list:
    """
    Robustly parse JSON from Bedrock response.
    Handles: ```json blocks, ```JSON, ``` blocks, preamble text, etc.
    """
    # Strategy 1: Try direct parse
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Strategy 2: Strip markdown code fences (any casing)
    cleaned = re.sub(r"^```(?:json|JSON)?\s*\n?", "", text.strip())
    cleaned = re.sub(r"\n?```\s*$", "", cleaned)
    try:
        return json.loads(cleaned.strip())
    except json.JSONDecodeError:
        pass

    # Strategy 3: Find the first [ ... ] block in the text
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    logger.error(f"Could not parse JSON from response: {text[:200]}...")
    return []
