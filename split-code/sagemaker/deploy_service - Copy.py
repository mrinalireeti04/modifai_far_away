import logging
import time
from typing import Dict, Any
import boto3
from botocore.exceptions import ClientError
from app.core.config import settings

logger = logging.getLogger(__name__)

class SageMakerDeploymentService:
    def __init__(self):
        self.region = 'ap-south-1'
        self.sagemaker_client = boto3.client('sagemaker', region_name=self.region)
        # Using the same execution role for creating models/endpoints as we did for training
        self.default_role_arn = "arn:aws:iam::417772278917:role/ModifaiBedrockFineTuneRole"

    def _get_inference_image(self, model_id: str = None) -> str:
        """
        Retrieves an appropriate inference image for deployment.
        Normally queried from SageMaker JumpStart public hub for the specific model.
        Using a standard Hugging Face Text Generation Inference (TGI) or PyTorch container.
        """
        # Inference image for Llama/PyTorch models on GPU in ap-south-1
        return f"763104351884.dkr.ecr.{self.region}.amazonaws.com/huggingface-pytorch-inference:2.0.0-transformers4.28.1-gpu-py310-cu118-ubuntu20.04"

    def deploy(self, trained_model_s3_uri: str, user_id: str, project_id: str, model_name_override: str = None) -> Dict[str, Any]:
        """
        Deploys a fine-tuned model synchronously to a SageMaker Endpoint.
        
        Args:
            trained_model_s3_uri: S3 path to the model.tar.gz
            user_id: User identifier for namespacing
            project_id: Project identifier for namespacing
            model_name_override: Optional base name for the deployed model components
            
        Returns:
            Dict[str, Any]: Structured JSON response containing endpoint details and status
        """
        timestamp = int(time.time())
        base_name = model_name_override or "ft-model"
        
        # Cleanly generate unique names for AWS components
        model_name = f"{base_name}-{user_id[:8]}-{timestamp}"
        endpoint_config_name = f"{model_name}-config"
        endpoint_name = f"{model_name}-ep"
        
        image_uri = self._get_inference_image()
        
        try:
            logger.info(f"Creating SageMaker Model: {model_name}")
            print(f"Creating SageMaker Model: {model_name}")
            
            # 1. Create Model
            self.sagemaker_client.create_model(
                ModelName=model_name,
                PrimaryContainer={
                    'Image': image_uri,
                    'ModelDataUrl': trained_model_s3_uri,
                    'Environment': {
                        'SAGEMAKER_CONTAINER_LOG_LEVEL': '20',
                        'SAGEMAKER_REGION': self.region
                    }
                },
                ExecutionRoleArn=self.default_role_arn
            )

            # 2. Create Endpoint Config
            logger.info(f"Creating Endpoint Config: {endpoint_config_name}")
            print(f"Creating Endpoint Config: {endpoint_config_name}")
            
            self.sagemaker_client.create_endpoint_config(
                EndpointConfigName=endpoint_config_name,
                ProductionVariants=[
                    {
                        'VariantName': 'AllTraffic',
                        'ModelName': model_name,
                        'InitialInstanceCount': 1,
                        'InstanceType': 'ml.g5.xlarge',
                        'InitialVariantWeight': 1.0
                    }
                ]
            )

            # 3. Create Endpoint
            logger.info(f"Starting Endpoint Deployment: {endpoint_name}")
            print(f"Starting Endpoint Deployment: {endpoint_name}")
            print("This may take 5-15 minutes...")
            
            self.sagemaker_client.create_endpoint(
                EndpointName=endpoint_name,
                EndpointConfigName=endpoint_config_name
            )

            # 4. Wait for Endpoint to be InService
            # We poll every 30 seconds since endpoints take several minutes
            while True:
                response = self.sagemaker_client.describe_endpoint(EndpointName=endpoint_name)
                status = response['EndpointStatus']
                
                logger.info(f"Endpoint {endpoint_name} Status: {status}")
                
                if status == 'InService':
                    print(f"\nEndpoint successfully deployed and InService: {endpoint_name}")
                    return {
                        "endpoint_name": endpoint_name,
                        "status": status,
                        "endpoint_arn": response.get('EndpointArn', ''),
                        "creation_time": response.get('CreationTime', '').isoformat() if response.get('CreationTime') else None
                    }
                elif status == 'Failed':
                    error_msg = response.get('FailureReason', 'Unknown failure')
                    logger.error(f"Endpoint deployment failed: {error_msg}")
                    raise RuntimeError(f"SageMaker Endpoint {endpoint_name} failed to deploy. Reason: {error_msg}")
                elif status in ['RollingBack', 'SystemUpdating']:
                    logger.warning(f"Endpoint {endpoint_name} experienced an issue and is in status: {status}")
                    
                # Creating an endpoint takes ~5-15 minutes, sleep to avoid throttling
                time.sleep(30)
                
        except ClientError as e:
            logger.error(f"AWS Error creating/monitoring endpoint '{endpoint_name}': {e}")
            raise RuntimeError(f"Failed to execute deployment due to AWS error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during endpoint deployment: {e}")
            raise
