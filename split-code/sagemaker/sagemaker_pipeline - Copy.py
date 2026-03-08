import logging
from typing import Dict, Any

from app.infrastructure.aws import (
    ModelSelectorService,
    S3DatasetManager,
    SageMakerFineTuneService,
    SageMakerDeploymentService
)

logger = logging.getLogger(__name__)

def run_finetune_pipeline(user_id: str, project_id: str, model_id: str) -> Dict[str, Any]:
    """
    Orchestrates the entire synchronous SageMaker fine-tuning and deployment pipeline
    using pure infrastructure services without API layer or background workers.
    
    Args:
        user_id: User UUID
        project_id: Project UUID 
        model_id: Target Amazon Bedrock / SageMaker JumpStart Model ID
        
    Returns:
        Dict[str, Any]: Structured JSON response detailing success status and created AWS components
    """
    logger.info(f"Starting pipeline for User: {user_id} | Project: {project_id} | Model: {model_id}")
    print(f"\n--- Starting SageMaker Fine-Tuning Pipeline ---")
    print(f"Model ID: {model_id}")
    print(f"Targeting environment: ap-south-1")

    # Instantiate services natively configured to AWS Region configs
    model_selector = ModelSelectorService()
    dataset_manager = S3DatasetManager()
    fine_tuner = SageMakerFineTuneService()
    deployer = SageMakerDeploymentService()

    try:
        # Step 1: Validate Model Selection
        logger.info(f"Step 1: Validating Model")
        print(f"\n[Step 1/4] Validating JumpStart model presence: {model_id}")
        validated_model = model_selector.validate_model(model_id)

        # Step 2: Ensure Training Metadata & Resolving Dataset Location
        logger.info(f"Step 2: Resolving Dataset Architecture")
        print(f"\n[Step 2/4] Verifying dataset structure in S3 for tenant...")
        dataset_uri = dataset_manager.build_dataset_s3_uri(user_id, project_id)

        # Step 3: Trigger training
        logger.info(f"Step 3: Trigger SageMaker Fine-Tuning Job")
        print(f"\n[Step 3/4] Initializing SageMaker Tuning - Provisioning ml.g5.2xlarge...")
        model_output_s3_path = fine_tuner.fine_tune(
            model_id=validated_model,
            dataset_s3_uri=dataset_uri,
            user_id=user_id,
            project_id=project_id
        )

        # Step 4: Map the custom algorithm onto SageMaker Deployments natively linking endpoints
        logger.info(f"Step 4: Executing endpoint configurations")
        print(f"\n[Step 4/4] Finalizing Execution! Initiating SageMaker Deployments Container.")
        endpoint_details = deployer.deploy(
            trained_model_s3_uri=model_output_s3_path,
            user_id=user_id,
            project_id=project_id,
            model_name_override=validated_model.split(':')[-1] if ':' in validated_model else validated_model
        )

        logger.info(f"Pipeline Succeeded. Orchestration terminated.")
        print(f"\n--- Pipeline Sequence Successful ---")
        return {
            "status": "success",
            "message": "Model trained and deployed successfully",
            "model_id": validated_model,
            "training_artifacts_uri": model_output_s3_path,
            "deployment": endpoint_details
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Pipeline Orchestration Failed: {error_msg}")
        print(f"\n[ERROR] Pipeline Interrupted: {error_msg}")
        return {
            "status": "error",
            "message": "Pipeline initialization or execution failed.",
            "error_details": error_msg,
            "user_id": user_id,
            "project_id": project_id
        }
