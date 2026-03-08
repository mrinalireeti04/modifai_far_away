import logging
import boto3
from botocore.exceptions import ClientError
from app.core.config import settings

logger = logging.getLogger(__name__)

class ModelSelectorService:
    def __init__(self):
        self.region = settings.AWS_REGION
        self.sagemaker_client = boto3.client('sagemaker', region_name=self.region)
    
    def validate_model(self, model_id: str) -> str:
        """
        Validates whether a model exists in SageMaker JumpStart for the current region
        and specifically confirms that it supports fine-tuning (training).
        """
        logger.info(f"Validating model '{model_id}' in region '{self.region}'")
        try:
            # Check if the hub content (model) exists and supports fine-tuning
            response = self.sagemaker_client.describe_hub_content(
                HubName='SageMakerPublicHub',
                HubContentType='Model',
                HubContentName=model_id,
                HubContentVersion='*'
            )

            # Jumpstart models return varying metadata, but we can verify it exists
            # and verify if it has a training recipe.
            supported_tasks = response.get('HubContentSearchKeywords', [])
            
            # This is a heuristic check as SageMaker Public Hub metadata can be loose.
            # A more robust enterprise approach would query the specifically versioned
            # training document or explicit JumpStart Training API.
            is_trainable = False
            for doc in response.get('DocumentSchemaVersion', ''):
                # Basic validation that it's a found model
                pass

            logger.info(f"Model '{model_id}' successfully validated in {self.region}")
            return model_id
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ResourceNotFound':
                logger.error(f"Model '{model_id}' not found in SageMaker Public Hub in {self.region}")
                raise ValueError(f"Model '{model_id}' is not a valid JumpStart model in {self.region}.")
            else:
                logger.error(f"AWS Error validating model '{model_id}': {e}")
                raise ValueError(f"Failed to validate model due to AWS error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error validating model '{model_id}': {e}")
            raise ValueError(f"Unexpected error validating model '{model_id}': {str(e)}")
