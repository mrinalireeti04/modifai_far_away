"""
Local test for the Dataset Generation Lambda.

Tests BOTH the per-chunk generator and the collector.
Requires valid AWS credentials with Bedrock access.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


def test_generation():
    """Test: generate samples for a single chunk, then collect results."""
    import boto3

    bucket = os.environ.get("S3_BUCKET_NAME", "modifai-bucket")
    region = os.environ.get("AWS_REGION", "ap-south-1")
    s3 = boto3.client("s3", region_name=region)

    prefix = "test-user/test-project/"

    # --- Test 1: Per-chunk generation ---
    print("\n--- Test 1: Single chunk generation ---")

    chunk_event = {
        "chunk": {
            "chunk_id": 1,
            "text": (
                "Machine learning is a subset of artificial intelligence that enables "
                "systems to learn and improve from experience without being explicitly "
                "programmed. It focuses on developing algorithms that can access data "
                "and use it to learn for themselves. Common types include supervised "
                "learning, unsupervised learning, and reinforcement learning."
            ),
            "source_file": "ai_overview.pdf",
            "word_count": 48,
        },
        "config": {
            "intent": "question-answering",
            "description": "AI education assistant",
            "samples_per_chunk": 3,
            "model_id": "apac.amazon.nova-micro-v1:0",
        },
    }

    print(f"🔄 Generating 3 QA pairs for chunk 1 via Bedrock...")
    from handler import handler
    result = handler(chunk_event, None)

    print(f"✅ Generated {result['count']} samples")
    for sample in result["samples"]:
        print(f"   Q: {sample['instruction'][:80]}...")
        print(f"   A: {sample['response'][:80]}...")
        print()

    if result.get("error"):
        print(f"❌ Error: {result['error']}")
        return

    # --- Test 2: Collector ---
    print("\n--- Test 2: Collector (combining results) ---")

    # Simulate Map state output with 2 chunks
    chunk2_result = {
        "chunk_id": 2,
        "samples": [
            {
                "instruction": "What is deep learning?",
                "input": "",
                "response": "Deep learning uses neural networks with many layers.",
                "chunk_id": 2,
                "source_file": "ai_overview.pdf",
            }
        ],
        "count": 1,
    }

    collector_event = {
        "project_id": "test-project",
        "s3_prefix": prefix,
        "mode": "dataset_only",
        "config": {},
        "step_results": {
            "ocr": {"raw_text_key": "temp_processing/raw_text.json"},
            "chunking": {"chunks_key": "temp_processing/chunks.json", "chunk_count": 2},
        },
        "map_results": [result, chunk2_result],
    }

    print(f"🔄 Running collector to combine {len(collector_event['map_results'])} chunk results...")
    from collector import handler as collector_handler
    collected = collector_handler(collector_event, None)

    gen_result = collected["step_results"]["generation"]
    print(f"✅ Collector result:")
    print(json.dumps(gen_result, indent=2))

    # Verify S3 output
    examples_key = f"{prefix}{gen_result['examples_key']}"
    print(f"\n📥 Reading examples from s3://{bucket}/{examples_key}")
    response = s3.get_object(Bucket=bucket, Key=examples_key)
    examples = json.loads(response["Body"].read().decode("utf-8"))
    print(f"   Total examples in S3: {len(examples)}")

    # Verify map_results was cleaned from state
    assert "map_results" not in collected, "map_results should be removed from state!"
    print("   ✅ map_results cleaned from downstream state")

    # Cleanup
    print("\n🧹 Cleaning up...")
    s3.delete_object(Bucket=bucket, Key=examples_key)
    print("Done!")


if __name__ == "__main__":
    print("=" * 50)
    print("Dataset Generation Lambda — Local Test")
    print("=" * 50)
    test_generation()
