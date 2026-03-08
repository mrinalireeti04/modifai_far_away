"""
Fine-Tune Lambda — Submits a SageMaker training job and returns immediately.

Does NOT poll for completion — Step Functions handles the wait loop
via the status_checker Lambda.

Input (from Step Functions):
{
    ...state,
    "step_results": {
        "quality_control": {
            "clean_dataset_key": "temp_processing/clean_dataset.jsonl",
            ...
        }
    }
}

Output:
{
    ...state,
    "step_results": {
        ...step_results,
        "fine_tuning": {
            "job_name": "modifai-ft-abc123-1709856000",
            "status": "Creating",
            "model_output_s3_path": "s3://modifai-bucket/user/proj/models/output/"
        }
    }
}
"""

import json
import time
import os
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "modifai-bucket")
AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")
SAGEMAKER_ROLE_ARN = os.environ.get(
    "SAGEMAKER_ROLE_ARN",
    "arn:aws:iam::417772278917:role/ModifaiBedrockFineTuneRole",
)
TRAINING_IMAGE = os.environ.get(
    "TRAINING_IMAGE",
    "763104351884.dkr.ecr.{region}.amazonaws.com/huggingface-pytorch-training:2.0.0-transformers4.28.1-gpu-py310-cu118-ubuntu20.04",
)
DEFAULT_INSTANCE_TYPE = os.environ.get("TRAINING_INSTANCE_TYPE", "ml.g4dn.xlarge")

sagemaker_client = boto3.client("sagemaker", region_name=AWS_REGION)


def handler(event, context):
    """Lambda entry point — submits SageMaker training job and returns immediately."""
    logger.info(f"Fine-Tune Lambda invoked for project: {event.get('project_id')}")

    s3_prefix = event["s3_prefix"]
    config = event.get("config", {})
    project_id = event.get("project_id", "unknown")

    # Build dataset S3 URI
    dataset_key = event["step_results"]["quality_control"]["clean_dataset_key"]
    dataset_s3_uri = f"s3://{BUCKET_NAME}/{s3_prefix}{dataset_key}"

    # Model output path
    output_s3_path = f"s3://{BUCKET_NAME}/{s3_prefix}models/output/"

    # Generate unique job name
    timestamp = int(time.time())
    base_model = config.get("base_model", "llama-3-8b").replace("/", "-").replace(":", "-")
    job_name = f"modifai-ft-{base_model}-{project_id[:8]}-{timestamp}"
    # SageMaker job names max 63 chars, alphanumeric + hyphens only
    job_name = job_name[:63]

    # Resolve training image URI
    image_uri = TRAINING_IMAGE.format(region=AWS_REGION)

    # Hyperparameters (configurable)
    hyperparameters = {
        "epochs": str(config.get("epochs", 3)),
        "learning_rate": str(config.get("learning_rate", "2e-5")),
        "batch_size": str(config.get("batch_size", 8)),
    }

    logger.info(f"Submitting training job: {job_name}")
    logger.info(f"Dataset: {dataset_s3_uri}")
    logger.info(f"Output: {output_s3_path}")
    logger.info(f"Instance: {DEFAULT_INSTANCE_TYPE}")

    try:
        sagemaker_client.create_training_job(
            TrainingJobName=job_name,
            RoleArn=SAGEMAKER_ROLE_ARN,
            AlgorithmSpecification={
                "TrainingImage": image_uri,
                "TrainingInputMode": "File",
            },
            OutputDataConfig={"S3OutputPath": output_s3_path},
            ResourceConfig={
                "InstanceType": DEFAULT_INSTANCE_TYPE,
                "InstanceCount": 1,
                "VolumeSizeInGB": 50,
            },
            StoppingCondition={
                "MaxRuntimeInSeconds": 86400,  # 24 hours max
            },
            InputDataConfig=[
                {
                    "ChannelName": "training",
                    "DataSource": {
                        "S3DataSource": {
                            "S3DataType": "S3Prefix",
                            "S3Uri": dataset_s3_uri,
                            "S3DataDistributionType": "FullyReplicated",
                        }
                    },
                }
            ],
            HyperParameters=hyperparameters,
        )

        logger.info(f"Training job {job_name} submitted successfully")

        # Return immediately — Step Functions will poll via status_checker
        event.setdefault("step_results", {})
        event["step_results"]["fine_tuning"] = {
            "job_name": job_name,
            "status": "Creating",
            "model_output_s3_path": output_s3_path,
            "instance_type": DEFAULT_INSTANCE_TYPE,
            "dataset_s3_uri": dataset_s3_uri,
        }
        return event

    except ClientError as e:
        error_msg = str(e)
        logger.error(f"Failed to create training job: {error_msg}")
        event.setdefault("step_results", {})
        event["step_results"]["fine_tuning"] = {
            "job_name": job_name,
            "status": "Failed",
            "error": error_msg,
        }
        raise RuntimeError(f"SageMaker CreateTrainingJob failed: {error_msg}")
