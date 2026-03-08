"""
Start-and-Stop Validation Test for SageMaker Lambdas.

This test:
1. Uploads a tiny JSONL dataset to S3
2. Calls the fine_tune handler to submit a real SageMaker training job
3. Calls the status_checker to verify the job was accepted
4. IMMEDIATELY stops the training job to avoid charges
5. Cleans up

Expected cost: ~$0.02-0.05 (a minute of ml.g5.2xlarge)

Usage:
    /Volumes/Data/Hacks/Modifai/backend/venv/bin/python test_local.py
"""

import json
import time
import os
import sys
import importlib.util


def _load_handler(folder_name):
    """Load a handler module from a sibling Lambda folder by absolute path."""
    handler_path = os.path.join(
        os.path.dirname(__file__), "..", folder_name, "handler.py"
    )
    handler_path = os.path.abspath(handler_path)
    spec = importlib.util.spec_from_file_location(f"{folder_name}_handler", handler_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.handler


def test_start_and_stop():
    """Submit a real training job, verify it starts, then stop it immediately."""
    import boto3

    bucket = os.environ.get("S3_BUCKET_NAME", "modifai-bucket")
    region = os.environ.get("AWS_REGION", "ap-south-1")
    s3 = boto3.client("s3", region_name=region)
    sagemaker = boto3.client("sagemaker", region_name=region)

    prefix = "test-user/test-project/"

    # 1. Upload a tiny dummy JSONL dataset
    dataset_key = f"{prefix}temp_processing/clean_dataset.jsonl"
    dummy_data = [
        {"instruction": "What is AI?", "input": "", "response": "Artificial intelligence."},
        {"instruction": "What is ML?", "input": "", "response": "Machine learning is a subset of AI."},
    ]
    jsonl = "\n".join(json.dumps(d) for d in dummy_data)

    print(f"📤 Uploading dummy dataset to s3://{bucket}/{dataset_key}")
    s3.put_object(Bucket=bucket, Key=dataset_key, Body=jsonl)

    # 2. Build event and call fine_tune handler
    event = {
        "project_id": "test-proj",
        "s3_prefix": prefix,
        "mode": "dataset_and_finetune",
        "config": {
            "base_model": "test-model",
            "epochs": 1,
            "learning_rate": "2e-5",
            "batch_size": 4,
        },
        "step_results": {
            "quality_control": {
                "clean_dataset_key": "temp_processing/clean_dataset.jsonl",
                "kept": 2,
            }
        },
    }

    print("\n🔄 Submitting training job via fine_tune handler...")
    fine_tune_handler = _load_handler("fine_tune")
    job_name = None
    try:
        result = fine_tune_handler(event, None)

        ft_result = result["step_results"]["fine_tuning"]
        job_name = ft_result["job_name"]
        print(f"✅ Training job submitted: {job_name}")
        print(f"   Status: {ft_result['status']}")
        print(f"   Instance: {ft_result['instance_type']}")
        print(f"   Dataset: {ft_result['dataset_s3_uri']}")
        print(f"   Output: {ft_result['model_output_s3_path']}")

    except Exception as e:
        import traceback
        print(f"❌ Fine-tune handler failed: {e}")
        traceback.print_exc()
        s3.delete_object(Bucket=bucket, Key=dataset_key)
        return

    # 3. Poll status a few times to verify job was accepted
    print("\n🔄 Checking job status via status_checker...")
    status_checker_handler = _load_handler("status_checker")

    result["check_type"] = "training"
    max_checks = 6
    for i in range(max_checks):
        time.sleep(10)
        check_result = status_checker_handler(result, None)
        status = check_result.get("check_status")
        details = check_result.get("check_details", {})
        print(f"   Check {i + 1}/{max_checks}: {status} ({details.get('secondary_status', '')})")

        if status != "InProgress":
            break

    # 4. STOP the training job immediately
    print(f"\n🛑 Stopping training job: {job_name}")
    try:
        sagemaker.stop_training_job(TrainingJobName=job_name)
        print("✅ Stop request sent")
    except Exception as e:
        print(f"⚠️  Stop failed (may already be done): {e}")

    # Wait a moment and check final status
    time.sleep(5)
    final_desc = sagemaker.describe_training_job(TrainingJobName=job_name)
    final_status = final_desc["TrainingJobStatus"]
    print(f"   Final status: {final_status}")

    # 5. Cleanup
    print("\n🧹 Cleaning up...")
    s3.delete_object(Bucket=bucket, Key=dataset_key)
    print("Done!")

    print("\n" + "=" * 50)
    if final_status in ("Stopping", "Stopped"):
        print("✅ VALIDATION PASSED: Job was created, accepted, and stopped.")
        print("   IAM role, S3 paths, instance type, and training image are all valid.")
    elif final_status == "Failed":
        reason = final_desc.get("FailureReason", "Unknown")
        print(f"⚠️  Job failed: {reason}")
        print("   The job was created but failed during execution.")
    else:
        print(f"ℹ️  Job status: {final_status}")


if __name__ == "__main__":
    print("=" * 50)
    print("SageMaker Fine-Tune — Start & Stop Validation")
    print("=" * 50)
    test_start_and_stop()
