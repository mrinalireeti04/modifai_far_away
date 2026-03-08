"""
Status Checker Lambda — Checks SageMaker training job or endpoint status ONCE.

Called by Step Functions in a polling loop:
    status_checker → Wait 60s → status_checker → Choice (done?) → ...

Supports both training jobs and endpoint deployments via the `check_type` field.

Input (from Step Functions):
{
    ...state,
    "check_type": "training" | "endpoint",
    "step_results": {
        "fine_tuning": { "job_name": "modifai-ft-...", ... }
        -- or --
        "deployment": { "endpoint_name": "modifai-ep-...", ... }
    }
}

Output:
{
    ...state,
    "check_status": "InProgress" | "Completed" | "Failed",
    "check_details": { ... status-specific metadata ... }
}

Step Functions uses `check_status` in a Choice state to decide:
    loop back (InProgress) or proceed (Completed/Failed).
"""

import os
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")

sagemaker_client = boto3.client("sagemaker", region_name=AWS_REGION)


def handler(event, context):
    """Lambda entry point — checks status once and returns."""
    check_type = event.get("check_type", "training")

    if check_type == "training":
        return check_training_job(event)
    elif check_type == "endpoint":
        return check_endpoint(event)
    else:
        raise ValueError(f"Unknown check_type: {check_type}")


def check_training_job(event: dict) -> dict:
    """Check SageMaker training job status."""
    job_name = event["step_results"]["fine_tuning"]["job_name"]
    logger.info(f"Checking training job: {job_name}")

    try:
        response = sagemaker_client.describe_training_job(
            TrainingJobName=job_name
        )

        status = response["TrainingJobStatus"]
        logger.info(f"Training job {job_name} status: {status}")

        details = {
            "status": status,
            "secondary_status": response.get("SecondaryStatus", ""),
        }

        if status == "Completed":
            details["model_artifacts"] = response["ModelArtifacts"]["S3ModelArtifacts"]
            details["duration_seconds"] = (
                response["TrainingEndTime"] - response["TrainingStartTime"]
            ).total_seconds()
            details["billable_seconds"] = response.get("BillableTimeInSeconds", 0)

            # Update fine_tuning results with final data
            event["step_results"]["fine_tuning"]["status"] = "Completed"
            event["step_results"]["fine_tuning"]["model_artifacts"] = details["model_artifacts"]
            event["step_results"]["fine_tuning"]["duration_seconds"] = details["duration_seconds"]

            # Extract final metrics if available
            metrics = response.get("FinalMetricDataList", [])
            if metrics:
                details["final_metrics"] = {
                    m["MetricName"]: m["Value"] for m in metrics
                }
                event["step_results"]["fine_tuning"]["final_metrics"] = details["final_metrics"]

        elif status == "Failed":
            details["failure_reason"] = response.get("FailureReason", "Unknown")
            event["step_results"]["fine_tuning"]["status"] = "Failed"
            event["step_results"]["fine_tuning"]["error"] = details["failure_reason"]

        elif status == "Stopped":
            details["failure_reason"] = "Training job was stopped"
            event["step_results"]["fine_tuning"]["status"] = "Stopped"

        # Normalize to simple status for Step Functions Choice state
        if status in ("Completed",):
            event["check_status"] = "Completed"
        elif status in ("Failed", "Stopped"):
            event["check_status"] = "Failed"
        else:
            event["check_status"] = "InProgress"

        event["check_details"] = details
        return event

    except ClientError as e:
        logger.error(f"Error checking training job {job_name}: {e}")
        event["check_status"] = "Failed"
        event["check_details"] = {"error": str(e)}
        return event


def check_endpoint(event: dict) -> dict:
    """Check SageMaker endpoint deployment status."""
    endpoint_name = event["step_results"]["deployment"]["endpoint_name"]
    logger.info(f"Checking endpoint: {endpoint_name}")

    try:
        response = sagemaker_client.describe_endpoint(
            EndpointName=endpoint_name
        )

        status = response["EndpointStatus"]
        logger.info(f"Endpoint {endpoint_name} status: {status}")

        details = {
            "status": status,
            "endpoint_arn": response.get("EndpointArn", ""),
        }

        if status == "InService":
            creation_time = response.get("CreationTime")
            details["creation_time"] = creation_time.isoformat() if creation_time else None

            event["step_results"]["deployment"]["status"] = "InService"
            event["step_results"]["deployment"]["endpoint_arn"] = details["endpoint_arn"]

        elif status == "Failed":
            details["failure_reason"] = response.get("FailureReason", "Unknown")
            event["step_results"]["deployment"]["status"] = "Failed"
            event["step_results"]["deployment"]["error"] = details["failure_reason"]

        # Normalize status
        if status == "InService":
            event["check_status"] = "Completed"
        elif status in ("Failed", "RollingBack"):
            event["check_status"] = "Failed"
        else:
            event["check_status"] = "InProgress"

        event["check_details"] = details
        return event

    except ClientError as e:
        logger.error(f"Error checking endpoint {endpoint_name}: {e}")
        event["check_status"] = "Failed"
        event["check_details"] = {"error": str(e)}
        return event
