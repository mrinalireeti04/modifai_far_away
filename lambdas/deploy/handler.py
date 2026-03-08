"""
Deploy Lambda — Creates a SageMaker inference endpoint and returns immediately.

Does NOT wait for InService — Step Functions handles the wait loop
via the status_checker Lambda.

Input (from Step Functions — after training completes):
{
    ...state,
    "step_results": {
        "fine_tuning": {
            "model_artifacts": "s3://modifai-bucket/.../output/model.tar.gz",
            "job_name": "modifai-ft-...",
            ...
        }
    }
}

Output:
{
    ...state,
    "step_results": {
        ...step_results,
        "deployment": {
            "endpoint_name": "modifai-ep-abc123-1709856000",
            "model_name": "modifai-model-abc123-1709856000",
            "status": "Creating"
        }
    }
}
"""

import time
import os
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")
SAGEMAKER_ROLE_ARN = os.environ.get(
    "SAGEMAKER_ROLE_ARN",
    "arn:aws:iam::417772278917:role/ModifaiBedrockFineTuneRole",
)
INFERENCE_IMAGE = os.environ.get(
    "INFERENCE_IMAGE",
    "763104351884.dkr.ecr.{region}.amazonaws.com/huggingface-pytorch-inference:2.0.0-transformers4.28.1-gpu-py310-cu118-ubuntu20.04",
)
DEFAULT_INSTANCE_TYPE = os.environ.get("INFERENCE_INSTANCE_TYPE", "ml.g5.xlarge")

sagemaker_client = boto3.client("sagemaker", region_name=AWS_REGION)


def handler(event, context):
    """Lambda entry point — creates SageMaker endpoint, returns immediately."""
    logger.info(f"Deploy Lambda invoked for project: {event.get('project_id')}")

    project_id = event.get("project_id", "unknown")
    model_artifacts = event["step_results"]["fine_tuning"]["model_artifacts"]

    # Generate unique names
    timestamp = int(time.time())
    model_name = f"modifai-model-{project_id[:8]}-{timestamp}"
    endpoint_config_name = f"{model_name}-config"
    endpoint_name = f"modifai-ep-{project_id[:8]}-{timestamp}"

    image_uri = INFERENCE_IMAGE.format(region=AWS_REGION)

    try:
        # 1. Create Model
        logger.info(f"Creating SageMaker Model: {model_name}")
        sagemaker_client.create_model(
            ModelName=model_name,
            PrimaryContainer={
                "Image": image_uri,
                "ModelDataUrl": model_artifacts,
                "Environment": {
                    "SAGEMAKER_CONTAINER_LOG_LEVEL": "20",
                    "SAGEMAKER_REGION": AWS_REGION,
                },
            },
            ExecutionRoleArn=SAGEMAKER_ROLE_ARN,
        )

        # 2. Create Endpoint Config
        logger.info(f"Creating Endpoint Config: {endpoint_config_name}")
        sagemaker_client.create_endpoint_config(
            EndpointConfigName=endpoint_config_name,
            ProductionVariants=[
                {
                    "VariantName": "AllTraffic",
                    "ModelName": model_name,
                    "InitialInstanceCount": 1,
                    "InstanceType": DEFAULT_INSTANCE_TYPE,
                    "InitialVariantWeight": 1.0,
                }
            ],
        )

        # 3. Create Endpoint
        logger.info(f"Creating Endpoint: {endpoint_name}")
        sagemaker_client.create_endpoint(
            EndpointName=endpoint_name,
            EndpointConfigName=endpoint_config_name,
        )

        logger.info(f"Endpoint creation initiated: {endpoint_name}")

        # Return immediately — Step Functions polls via status_checker
        event.setdefault("step_results", {})
        event["step_results"]["deployment"] = {
            "endpoint_name": endpoint_name,
            "model_name": model_name,
            "endpoint_config_name": endpoint_config_name,
            "status": "Creating",
            "instance_type": DEFAULT_INSTANCE_TYPE,
        }

        # Set check_type for the status_checker polling loop
        event["check_type"] = "endpoint"

        return event

    except ClientError as e:
        error_msg = str(e)
        logger.error(f"Deployment failed: {error_msg}")

        # Attempt cleanup on failure
        _cleanup_on_failure(model_name, endpoint_config_name, endpoint_name)

        event.setdefault("step_results", {})
        event["step_results"]["deployment"] = {
            "endpoint_name": endpoint_name,
            "status": "Failed",
            "error": error_msg,
        }
        raise RuntimeError(f"SageMaker deployment failed: {error_msg}")


def _cleanup_on_failure(model_name: str, config_name: str, endpoint_name: str):
    """Best-effort cleanup of partially created resources."""
    for name, delete_fn in [
        (endpoint_name, lambda: sagemaker_client.delete_endpoint(EndpointName=endpoint_name)),
        (config_name, lambda: sagemaker_client.delete_endpoint_config(EndpointConfigName=config_name)),
        (model_name, lambda: sagemaker_client.delete_model(ModelName=model_name)),
    ]:
        try:
            delete_fn()
            logger.info(f"Cleaned up: {name}")
        except Exception:
            pass  # Best effort
