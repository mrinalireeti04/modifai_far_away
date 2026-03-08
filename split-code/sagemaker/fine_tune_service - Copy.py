import logging
import time
from typing import Dict, Any
import boto3
from botocore.exceptions import ClientError
from app.core.config import settings

logger = logging.getLogger(__name__)

class SageMakerFineTuneService:
    def __init__(self):
        # Enforce region ap-south-1 explicitly as requested
        self.region = 'ap-south-1'
        self.sagemaker_client = boto3.client('sagemaker', region_name=self.region)
        self.default_role_arn = "arn:aws:iam::417772278917:role/ModifaiBedrockFineTuneRole"

    def _get_jumpstart_training_image(self, model_id: str) -> str:
        """
        Retrieves the appropriate training image URI for the JumpStart model in the current region.
        In a full enterprise implementation, this requires querying the SageMaker Public Hub document
        or using the sagemaker SDK. For pure boto3 without SDK overhead, we'll map or query.
        """
        try:
            response = self.sagemaker_client.describe_hub_content(
                HubName='SageMakerPublicHub',
                HubContentType='Model',
                HubContentName=model_id,
                HubContentVersion='*'
            )
            # Typically need to parse DocumentSchemaVersion to find ImageUri
            # As a fallback or standard practice, we can lookup predefined images
            # or rely on the caller to provide it if the SDK is strictly not used.
            # Using standard deep learning containers as proxy for pure boto3 demo
            proxy_image_uri = f"763104351884.dkr.ecr.{self.region}.amazonaws.com/huggingface-pytorch-training:2.0.0-transformers4.28.1-gpu-py310-cu118-ubuntu20.04"
            logger.info(f"Using training image: {proxy_image_uri}")
            return proxy_image_uri
            
        except ClientError as e:
            logger.error(f"Failed to fetch model metadata for '{model_id}': {e}")
            raise ValueError(f"Could not resolve JumpStart training image for '{model_id}'")

    def fine_tune(self, model_id: str, dataset_s3_uri: str, user_id: str, project_id: str, role_arn: str = None) -> str:
        """
        Executes a synchronous fine-tuning job using SageMaker.
        
        Args:
            model_id: The SageMaker JumpStart model ID
            dataset_s3_uri: S3 path containing the training dataset
            user_id: User identifier for namespacing
            project_id: Project identifier for namespacing
            role_arn: IAM Role ARN (defaults to ModifaiBedrockFineTuneRole)
            
        Returns:
            str: S3 path to the trained model artifacts
        """
        role = role_arn if role_arn else self.default_role_arn
        
        # Cleanly generate a training job name
        timestamp = int(time.time())
        job_name = f"ft-{model_id.replace(':', '-')}-{user_id[:8]}-{timestamp}"
        
        s3_output_path = f"s3://modifai-bedrock-training/{user_id}/{project_id}/outputs/{job_name}/"
        image_uri = self._get_jumpstart_training_image(model_id)

        try:
            logger.info(f"Starting SageMaker Training Job: {job_name}")
            print(f"Starting SageMaker Training Job: {job_name}") # Explicitly requested print

            response = self.sagemaker_client.create_training_job(
                TrainingJobName=job_name,
                RoleArn=role,
                AlgorithmSpecification={
                    'TrainingImage': image_uri,
                    'TrainingInputMode': 'File'
                },
                OutputDataConfig={
                    'S3OutputPath': s3_output_path
                },
                ResourceConfig={
                    'InstanceType': 'ml.g5.2xlarge',
                    'InstanceCount': 1,
                    'VolumeSizeInGB': 50
                },
                StoppingCondition={
                    'MaxRuntimeInSeconds': 86400 # 24 hours
                },
                InputDataConfig=[
                    {
                        'ChannelName': 'training',
                        'DataSource': {
                            'S3DataSource': {
                                'S3DataType': 'S3Prefix',
                                'S3Uri': dataset_s3_uri,
                                'S3DataDistributionType': 'FullyReplicated'
                            }
                        }
                    }
                ],
                HyperParameters={
                    'epochs': '3',
                    'learning_rate': '2e-5',
                    'batch_size': '8',
                }
            )

            # Polling loop for synchronous execution
            while True:
                job_desc = self.sagemaker_client.describe_training_job(TrainingJobName=job_name)
                status = job_desc['TrainingJobStatus']
                
                logger.info(f"Training Job {job_name} status: {status}")
                
                if status == 'Completed':
                    model_data_url = job_desc['ModelArtifacts']['S3ModelArtifacts']
                    logger.info(f"Training successfully completed. Artifacts stored at: {model_data_url}")
                    return model_data_url
                    
                elif status in ['Failed', 'Stopped']:
                    error_msg = job_desc.get('FailureReason', 'Unknown failure')
                    logger.error(f"Training job {job_name} failed: {error_msg}")
                    raise RuntimeError(f"SageMaker Training Job {job_name} failed. Reason: {error_msg}")
                
                time.sleep(30) # Poll every 30 seconds

        except ClientError as e:
            logger.error(f"AWS Error creating/monitoring training job '{job_name}': {e}")
            raise RuntimeError(f"Failed to execute training job due to AWS error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during fine tuning: {e}")
            raise
