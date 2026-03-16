"""
Dataset Generation Collector Lambda — Combines results from the Map state.

The Step Functions Map state invokes the generator Lambda once per chunk.
This collector receives ALL results, flattens them, and writes to S3.

Input (from Step Functions — Map state output + original state):
{
    ...original_state,
    "map_results": [
        { "chunk_id": 1, "samples": [...], "count": 5 },
        { "chunk_id": 2, "samples": [...], "count": 5 },
        ...
    ]
}

Output:
{
    ...original_state,
    "step_results": {
        ...step_results,
        "generation": {
            "examples_key": "temp_processing/examples.json",
            "example_count": 200,
            "chunks_processed": 40,
            "chunks_failed": 0
        }
    }
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
    """Collects Map state results and writes combined examples to S3."""
    logger.info(f"Collector invoked for project: {event.get('project_id')}")

    s3_prefix = event["s3_prefix"]
    map_results = event.get("map_results", [])

    # Flatten all samples from all chunks
    all_examples = []
    chunks_failed = 0
    example_id = 1

    for result in map_results:
        chunk_id = result.get("chunk_id")
        if result.get("error"):
            chunks_failed += 1
            logger.warning(f"Chunk {chunk_id} had error: {result['error']}")
            continue

        # Check if result is stored in S3 (pass-by-reference)
        samples = []
        result_key = result.get("result_key")
        if result_key:
            try:
                logger.info(f"Fetching result for chunk {chunk_id} from {result_key}")
                resp = s3_client.get_object(Bucket=BUCKET_NAME, Key=result_key)
                result_data = json.loads(resp["Body"].read().decode("utf-8"))
                samples = result_data.get("samples", [])
            except Exception as e:
                logger.error(f"Failed to fetch result key {result_key}: {e}")
                chunks_failed += 1
                continue
        else:
            # Fallback for old/direct format
            samples = result.get("samples", [])

        for sample in samples:
            sample["example_id"] = example_id
            all_examples.append(sample)
            example_id += 1

    logger.info(
        f"Collected {len(all_examples)} examples from "
        f"{len(map_results)} chunks ({chunks_failed} failed)"
    )

    # Write to S3
    output_key = f"{s3_prefix}temp_processing/examples.json"
    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=output_key,
        Body=json.dumps(all_examples, ensure_ascii=False),
        ContentType="application/json",
    )

    logger.info(f"Examples written to s3://{BUCKET_NAME}/{output_key}")

    # Clean up map_results from state (don't pass the huge payload downstream)
    event.pop("map_results", None)

    # Return updated state
    event.setdefault("step_results", {})
    event["step_results"]["generation"] = {
        "examples_key": "temp_processing/examples.json",
        "example_count": len(all_examples),
        "chunks_processed": len(map_results) - chunks_failed,
        "chunks_failed": chunks_failed,
    }
    return event
