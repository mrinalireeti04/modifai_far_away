"""
Local test for the Quality Control Lambda handler.

Creates mock examples and chunks in S3, runs QC, verifies filtering and output format.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


def test_quality_control():
    """Test QC: create examples with varying quality, verify correct filtering."""
    import boto3

    bucket = os.environ.get("S3_BUCKET_NAME", "modifai-bucket")
    region = os.environ.get("AWS_REGION", "ap-south-1")
    s3 = boto3.client("s3", region_name=region)

    prefix = "test-user/test-project/"

    # 1. Create mock chunks in S3
    chunks = [
        {
            "chunk_id": 1,
            "text": (
                "Machine learning is a subset of artificial intelligence that enables "
                "systems to learn and improve from experience without being explicitly "
                "programmed. It focuses on developing algorithms that can access data "
                "and use it to learn for themselves."
            ),
            "source_file": "ai_overview.pdf",
            "word_count": 40,
        }
    ]

    chunks_key = f"{prefix}temp_processing/chunks.json"
    s3.put_object(Bucket=bucket, Key=chunks_key, Body=json.dumps(chunks))

    # 2. Create mock examples with varying quality
    examples = [
        # GOOD: Long, high overlap with chunk, all fields present
        {
            "example_id": 1,
            "instruction": "What is machine learning?",
            "input": "",
            "response": (
                "Machine learning is a subset of artificial intelligence that enables "
                "systems to learn and improve from experience without being explicitly "
                "programmed. It focuses on developing algorithms that can access data."
            ),
            "chunk_id": 1,
            "source_file": "ai_overview.pdf",
        },
        # GOOD: Different question, decent overlap
        {
            "example_id": 2,
            "instruction": "How does machine learning work?",
            "input": "",
            "response": (
                "Machine learning works by developing algorithms that can access data "
                "and use it to learn for themselves, enabling systems to improve from "
                "experience without being explicitly programmed."
            ),
            "chunk_id": 1,
            "source_file": "ai_overview.pdf",
        },
        # BAD: Too short, low quality
        {
            "example_id": 3,
            "instruction": "What is ML?",
            "input": "",
            "response": "AI stuff",
            "chunk_id": 1,
            "source_file": "ai_overview.pdf",
        },
        # BAD: Hallucinated — no overlap with chunk
        {
            "example_id": 4,
            "instruction": "Who invented quantum computing?",
            "input": "",
            "response": (
                "Richard Feynman proposed the concept of quantum computing in 1982 "
                "during a lecture at MIT. He suggested that quantum systems could be "
                "simulated efficiently by other quantum systems."
            ),
            "chunk_id": 1,
            "source_file": "ai_overview.pdf",
        },
        # DUPLICATE of example 1
        {
            "example_id": 5,
            "instruction": "What is machine learning?",
            "input": "",
            "response": (
                "Machine learning is a subset of artificial intelligence that enables "
                "systems to learn and improve from experience without being explicitly "
                "programmed. It focuses on developing algorithms that can access data."
            ),
            "chunk_id": 1,
            "source_file": "ai_overview.pdf",
        },
    ]

    examples_key = f"{prefix}temp_processing/examples.json"
    s3.put_object(Bucket=bucket, Key=examples_key, Body=json.dumps(examples))

    # 3. Build Step Functions event
    event = {
        "project_id": "test-project",
        "s3_prefix": prefix,
        "mode": "dataset_only",
        "config": {
            "quality_threshold": 0.5,
        },
        "step_results": {
            "chunking": {
                "chunks_key": "temp_processing/chunks.json",
                "chunk_count": 1,
            },
            "generation": {
                "examples_key": "temp_processing/examples.json",
                "example_count": 5,
            },
        },
    }

    # 4. Run QC
    print("🔄 Running Quality Control...")
    from handler import handler
    result = handler(event, None)

    qc_result = result["step_results"]["quality_control"]
    print(f"\n✅ QC Result:")
    print(json.dumps(qc_result, indent=2))

    # 5. Verify expectations
    assert qc_result["total_input"] == 5, f"Expected 5 input, got {qc_result['total_input']}"
    assert qc_result["duplicates_removed"] == 1, f"Expected 1 dup removed, got {qc_result['duplicates_removed']}"

    print(f"\n   📊 Input: {qc_result['total_input']} examples")
    print(f"   🔁 Duplicates removed: {qc_result['duplicates_removed']}")
    print(f"   ✅ Kept: {qc_result['kept']}")
    print(f"   ❌ Discarded (below {qc_result['threshold']}): {qc_result['discarded']}")

    # 6. Read and inspect the JSONL output
    clean_key = f"{prefix}{qc_result['clean_dataset_key']}"
    response = s3.get_object(Bucket=bucket, Key=clean_key)
    lines = response["Body"].read().decode("utf-8").strip().split("\n")

    print(f"\n📥 Clean dataset ({len(lines)} lines JSONL):")
    for line in lines:
        item = json.loads(line)
        print(f"   Score {item['confidence_score']:.3f} | Q: {item['instruction'][:60]}...")

    # 7. Cleanup
    print("\n🧹 Cleaning up...")
    for key in [chunks_key, examples_key, clean_key]:
        s3.delete_object(Bucket=bucket, Key=key)
    print("Done!")


if __name__ == "__main__":
    print("=" * 50)
    print("Quality Control Lambda — Local Test")
    print("=" * 50)
    test_quality_control()
