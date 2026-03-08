import logging
import boto3
from botocore.exceptions import ClientError
from app.core.config import settings

logger = logging.getLogger(__name__)

class S3DatasetManager:
    def __init__(self):
        # We use standard S3 client
        self.s3_client = boto3.client('s3')
        self.bucket_name = "modifai-bucket"
    
    def build_dataset_s3_uri(self, user_id: str, project_id: str) -> str:
        """
        Builds and validates the S3 URI for a given user and project dataset.
        
        Args:
            user_id: The UUID/identifier for the multi-tenant user
            project_id: The UUID/identifier for the specific project
            
        Returns:
            str: The fully qualified S3 URI of the dataset
            
        Raises:
            ValueError: If the dataset file does not exist in the bucket
        """
        key = f"{user_id}/{project_id}/data/train.jsonl"
        s3_uri = f"s3://{self.bucket_name}/{key}"
        
        logger.info(f"Validating dataset existence at {s3_uri}")
        
        try:
            # head_object is the most efficient way to check if an object exists
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            logger.info(f"Dataset successfully located at {s3_uri}")
            return s3_uri
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.error(f"Dataset not found: {s3_uri}")
                raise ValueError(f"Dataset does not exist at expected location: {s3_uri}")
            else:
                logger.error(f"AWS Error accessing dataset {s3_uri}: {e}")
                raise RuntimeError(f"Failed to validate dataset due to AWS S3 error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error validating dataset {s3_uri}: {e}")
            raise
