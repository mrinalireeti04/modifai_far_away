"""
Prepare Map Input Lambda — Reads chunks from S3 and injects them into the event
for the Step Functions Map state.

The Map state needs the actual array of chunks in the event JSON.
This Lambda reads chunks.json from S3 and formats each chunk with the
config needed by the dataset_generation handler.

Input:
{
    ...state (from chunking step),
    "step_results": {
        "chunking": { "chunks_key": "temp_processing/chunks.json", ... }
    }
}

Output:
{
    ...state,
    "chunks_for_map": [
        { "chunk": { chunk_1 }, "config": { ... } },
        { "chunk": { chunk_2 }, "config": { ... } },
        ...
    ]
}
"""

import json
import os
import logging
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "modifai-bucket")
AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")

s3_client = boto3.client("s3", region_name=AWS_REGION)


def handler(event, context):
    """Read chunks from S3 and prepare Map state input metadata."""
    s3_prefix = event["s3_prefix"]
    chunks_key = f"{s3_prefix}{event['step_results']['chunking']['chunks_key']}"

    logger.info(f"Reading chunks from s3://{BUCKET_NAME}/{chunks_key}")
    response = s3_client.get_object(Bucket=BUCKET_NAME, Key=chunks_key)
    chunks_data = response["Body"].read().decode("utf-8")
    chunks = json.loads(chunks_data)

    config = event.get("config", {})

    # Build per-chunk input for the Map state (Pass-by-reference)
    # Each item in the Map will now just have the index and the key to the chunks file
    event["chunks_for_map"] = [
        {"chunk_index": i, "chunks_key": chunks_key, "s3_prefix": s3_prefix, "config": config}
        for i in range(len(chunks))
    ]

    logger.info(f"Prepared {len(chunks)} chunk references for Map state")
    return event
