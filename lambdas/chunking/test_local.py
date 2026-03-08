"""
Local test for the Chunking Lambda handler.

Creates a test file via the OCR Lambda output format, runs chunking, and verifies results.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


def test_chunking():
    """End-to-end test: upload mock OCR output → run chunking → verify chunks."""
    import boto3

    bucket = os.environ.get("S3_BUCKET_NAME", "modifai-bucket")
    region = os.environ.get("AWS_REGION", "ap-south-1")
    s3 = boto3.client("s3", region_name=region)

    prefix = "test-user/test-project/"

    # 1. Create mock OCR output in S3 (simulates what the OCR Lambda produces)
    # Using a longer text so we get multiple chunks
    sample_text = (
        "Artificial intelligence (AI) is the simulation of human intelligence "
        "processes by computer systems. These processes include learning, reasoning, "
        "and self-correction. AI encompasses several subfields including machine learning, "
        "natural language processing, computer vision, and robotics. "
        "Machine learning is a subset of AI that enables systems to learn and improve "
        "from experience without being explicitly programmed. It focuses on developing "
        "algorithms that can access data and use it to learn for themselves. "
        "Deep learning is a subset of machine learning that uses neural networks with "
        "many layers to analyze various factors of data. It has been responsible for "
        "many breakthroughs in AI including image recognition, speech recognition, and "
        "natural language processing. "
        "Natural language processing allows computers to understand, interpret, and "
        "generate human language. It combines computational linguistics with statistical "
        "and machine learning models. Applications include chatbots, translation services, "
        "and sentiment analysis. "
        "Computer vision enables machines to interpret and understand visual information "
        "from the world. It uses deep learning models trained on large datasets of images. "
        "Applications include autonomous vehicles, medical imaging, and facial recognition. "
        "Reinforcement learning is a type of machine learning where an agent learns to "
        "make decisions by performing actions in an environment to maximize cumulative reward. "
        "It has been used to train AI systems to play games, control robots, and optimize "
        "complex systems. "
        "Transfer learning allows a model trained on one task to be fine-tuned for another "
        "related task. This technique significantly reduces the amount of training data and "
        "compute resources needed. It is the foundation of modern LLM fine-tuning approaches. "
        "Generative AI creates new content including text, images, code, and music. "
        "Large language models like GPT and LLaMA are examples of generative AI systems "
        "that can produce human-like text based on the patterns they learned during training."
    )

    ocr_output = {
        "files": {
            "ai_overview.pdf": {
                "text": sample_text,
                "source_key": "data/ai_overview.pdf",
                "characters": len(sample_text),
            }
        },
        "errors": [],
        "total_characters": len(sample_text),
    }

    raw_text_key = f"{prefix}temp_processing/raw_text.json"
    print(f"📤 Uploading mock OCR output to s3://{bucket}/{raw_text_key}")
    s3.put_object(
        Bucket=bucket,
        Key=raw_text_key,
        Body=json.dumps(ocr_output),
        ContentType="application/json",
    )

    # 2. Build Step Functions event
    event = {
        "project_id": "test-project",
        "s3_prefix": prefix,
        "mode": "dataset_only",
        "config": {
            "max_chunk_words": 100,  # Small chunks to test splitting
            "min_chunk_words": 30,
            "overlap_words": 20,
        },
        "step_results": {
            "ocr": {
                "raw_text_key": "temp_processing/raw_text.json",
                "files_processed": 1,
                "total_characters": len(sample_text),
            }
        },
    }

    # 3. Invoke the handler
    print("🔄 Invoking Chunking handler...")
    from handler import handler
    result = handler(event, None)

    # 4. Print results
    chunking_result = result["step_results"]["chunking"]
    print(f"\n✅ Chunking Lambda result:")
    print(json.dumps(chunking_result, indent=2))

    # 5. Read and display chunks from S3
    chunks_key = f"{prefix}{chunking_result['chunks_key']}"
    print(f"\n📥 Reading chunks from s3://{bucket}/{chunks_key}")
    response = s3.get_object(Bucket=bucket, Key=chunks_key)
    chunks = json.loads(response["Body"].read().decode("utf-8"))

    for chunk in chunks:
        print(f"\n  --- Chunk {chunk['chunk_id']} ({chunk['word_count']} words, from {chunk['source_file']}) ---")
        print(f"  {chunk['text'][:150]}...")

    # 6. Verify overlap
    if len(chunks) >= 2:
        c1_words = set(chunks[0]["text"].split()[-20:])
        c2_words = set(chunks[1]["text"].split()[:30])
        overlap = c1_words & c2_words
        if overlap:
            print(f"\n🔗 Overlap verified between chunks 1-2: {len(overlap)} shared words")
        else:
            print(f"\n⚠️  No overlap detected between chunks 1-2")

    # 7. Cleanup
    print("\n🧹 Cleaning up test files...")
    s3.delete_object(Bucket=bucket, Key=raw_text_key)
    s3.delete_object(Bucket=bucket, Key=chunks_key)
    print("Done!")


if __name__ == "__main__":
    print("=" * 50)
    print("Chunking Lambda — Local Test")
    print("=" * 50)
    test_chunking()
