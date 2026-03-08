"""
Local test for the OCR Lambda handler.

Usage:
    1. Set your AWS credentials (AWS_PROFILE or env vars)
    2. Upload a test file to S3: aws s3 cp test.pdf s3://modifai-bucket/test-user/test-project/data/test.pdf
    3. Run: python test_local.py

This simulates the Step Functions event locally.
"""

import json
import os
import sys

# Add the handler directory to the path
sys.path.insert(0, os.path.dirname(__file__))


def test_with_txt():
    """Test with a plain text file — creates a test file in S3, runs OCR, cleans up."""
    import boto3

    bucket = os.environ.get("S3_BUCKET_NAME", "modifai-bucket")
    region = os.environ.get("AWS_REGION", "ap-south-1")
    s3 = boto3.client("s3", region_name=region)

    prefix = "test-user/test-project/"
    test_key = f"{prefix}data/test-sample.txt"

    # 1. Upload a test TXT file
    test_content = (
        "Artificial intelligence (AI) is the simulation of human intelligence "
        "processes by computer systems. These processes include learning, reasoning, "
        "and self-correction. AI has applications in healthcare, finance, education, "
        "and many other fields. Machine learning is a subset of AI that enables "
        "systems to learn and improve from experience without being explicitly programmed."
    )

    print(f"📤 Uploading test file to s3://{bucket}/{test_key}")
    s3.put_object(Bucket=bucket, Key=test_key, Body=test_content.encode("utf-8"))

    # 2. Build the Step Functions event
    event = {
        "project_id": "test-project",
        "s3_prefix": prefix,
        "mode": "dataset_only",
        "config": {
            "intent": "question-answering",
            "description": "Test run",
            "samples_per_chunk": 3,
            "quality_threshold": 0.6,
        },
        "step_results": {
            "upload": {
                "raw_file_keys": ["data/test-sample.txt"]
            }
        },
    }

    # 3. Invoke the handler
    print("🔄 Invoking OCR handler...")
    from handler import handler
    result = handler(event, None)

    # 4. Print results
    print("\n✅ OCR Lambda result:")
    print(json.dumps(result["step_results"]["ocr"], indent=2))

    # 5. Verify output in S3
    output_key = f"{prefix}temp_processing/raw_text.json"
    print(f"\n📥 Reading output from s3://{bucket}/{output_key}")
    response = s3.get_object(Bucket=bucket, Key=output_key)
    output_data = json.loads(response["Body"].read().decode("utf-8"))
    print(f"   Files processed: {len(output_data['files'])}")
    print(f"   Total characters: {output_data['total_characters']}")
    print(f"   Text preview: {list(output_data['files'].values())[0]['text'][:200]}...")

    # 6. Cleanup
    print("\n🧹 Cleaning up test files...")
    s3.delete_object(Bucket=bucket, Key=test_key)
    s3.delete_object(Bucket=bucket, Key=output_key)
    print("Done!")

    return result


def test_with_existing_file():
    """
    Test with a file that already exists in S3. 
    Set these env vars before running:
        S3_PREFIX=your-user-uuid/your-project-uuid/
        FILE_KEY=data/your-file.pdf
    """
    prefix = os.environ.get("S3_PREFIX")
    file_key = os.environ.get("FILE_KEY")

    if not prefix or not file_key:
        print("⚠️  Skipping test_with_existing_file — set S3_PREFIX and FILE_KEY env vars")
        return

    event = {
        "project_id": "test-project",
        "s3_prefix": prefix,
        "mode": "dataset_only",
        "config": {},
        "step_results": {
            "upload": {
                "raw_file_keys": [file_key]
            }
        },
    }

    print(f"🔄 Running OCR on existing file: {prefix}{file_key}")
    from handler import handler
    result = handler(event, None)

    print("\n✅ OCR Lambda result:")
    print(json.dumps(result["step_results"]["ocr"], indent=2))
    return result


if __name__ == "__main__":
    print("=" * 50)
    print("OCR Lambda — Local Test")
    print("=" * 50)

    test_with_txt()

    print("\n" + "=" * 50)
    test_with_existing_file()
