import boto3
import json
import logging
import uuid
from botocore.exceptions import ClientError
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

s3_client = boto3.client("s3")
sfn_client = boto3.client("stepfunctions")
bedrock_client = boto3.client("bedrock-runtime", region_name="ap-south-1")

BUCKET_NAME = "modifai-bucket"
STATE_MACHINE_ARN = "arn:aws:states:ap-south-1:417772278917:stateMachine:ModifaiPipeline"


class AWSService:
    @staticmethod
    def generate_presigned_url(s3_prefix: str, filename: str) -> str:
        """Generate a presigned URL to temporarily allow uploading a raw document to S3."""
        object_key = f"{s3_prefix}data/{filename}"
        try:
            url = s3_client.generate_presigned_url(
                "put_object",
                Params={"Bucket": BUCKET_NAME, "Key": object_key},
                ExpiresIn=3600,
            )
            return url
        except ClientError as e:
            logger.error(f"Error generating presigned URL: {e}")
            raise

    @staticmethod
    def start_pipeline_execution(project_id: str, s3_prefix: str, mode: str, config: dict) -> str:
        """Starts the Step Functions ModifaiPipeline state machine."""
        
        # Step Functions requires a specific input schema
        execution_input = {
            "project_id": project_id,
            "s3_prefix": s3_prefix,
            "mode": mode,
            "config": config,
            "step_results": {}
        }

        # If it's full or dataset mode, we need to pass the raw_file_keys in upload step
        # For simplicity, we assume the frontend uploaded a file named "document.pdf" into the data/ folder.
        # In a real app, the frontend would pass the exact filename(s) it uploaded.
        if mode in ["dataset_only", "full", "dataset_and_finetune"]:
            execution_input["step_results"]["upload"] = {
                "raw_file_keys": [f"data/document.pdf"]
            }

        execution_name = f"modifai-{project_id}-{uuid.uuid4().hex[:8]}"
        
        try:
            response = sfn_client.start_execution(
                stateMachineArn=STATE_MACHINE_ARN,
                name=execution_name,
                input=json.dumps(execution_input)
            )
            return response["executionArn"]
        except ClientError as e:
            logger.error(f"Error starting Step Functions execution: {e}")
            raise

    @staticmethod
    def get_pipeline_status(execution_arn: str) -> dict:
        """Get the current status of the Step Functions execution."""
        try:
            response = sfn_client.describe_execution(
                executionArn=execution_arn
            )
            return {
                "status": response["status"],
                "startDate": response["startDate"].isoformat() if "startDate" in response else None,
                "stopDate": response["stopDate"].isoformat() if "stopDate" in response else None,
            }
        except ClientError as e:
            logger.error(f"Error describing Step Functions execution: {e}")
            raise

    @staticmethod
    def get_execution_history(execution_arn: str) -> list[dict]:
        """Get the execution history logs of the Step Functions execution."""
        try:
            response = sfn_client.get_execution_history(
                executionArn=execution_arn,
                maxResults=100,
                reverseOrder=True # newest first, but UI might want oldest first. We'll return newest first and let frontend sort or UI reverse it.
            )
            # Format logs for frontend
            logs = []
            for event in response.get("events", []):
                logs.append({
                    "timestamp": event["timestamp"].isoformat(),
                    "type": event["type"],
                    "id": event["id"],
                    "details": event.get(f"{event['type'][0].lower() + event['type'][1:]}EventDetails", {})
                })
            return logs
        except ClientError as e:
            logger.error(f"Error fetching Step Functions history: {e}")
            raise

    @staticmethod
    async def evaluate_text_sample(text: str, intent: str) -> dict:
        """
        Calls Bedrock Nova Micro directly to evaluate if a sample text snippet
        is suitable for fine-tuning based on the desired intent.
        Replaces the old evaluate_data Lambda.
        """
        # Truncate text to avoid massive token counts for a simple check
        text = text[:3000]

        prompt = f"""You are a data quality evaluator for an AI fine-tuning pipeline.
The user wants to fine-tune a model for the following intent/domain: {intent}

Here is a sample text snippet from their dataset:
---
{text}
---

Evaluate this text snippet. Is it high-quality, readable, and relevant to the intent?
Provide a score from 0.0 to 1.0, and a brief 1-sentence explanation.

Respond ONLY with a valid JSON object in this exact format:
{{
    "score": 0.85,
    "explanation": "The text clearly discusses relevant concepts with good structure."
}}"""

        try:
            response = bedrock_client.invoke_model(
                modelId="apac.amazon.nova-micro-v1:0",
                accept="application/json",
                contentType="application/json",
                body=json.dumps({
                    "messages": [
                        {"role": "user", "content": [{"text": prompt}]}
                    ],
                    "inferenceConfig": {
                        "max_new_tokens": 150,
                        "temperature": 0.1
                    }
                })
            )
            
            response_body = json.loads(response["body"].read().decode("utf-8"))
            content = response_body.get("output", {}).get("message", {}).get("content", [])[0].get("text", "")
            
            # Clean up potential markdown formatting in the response
            if content.startswith("```json"):
                content = content[7:-3]
            elif content.startswith("```"):
                content = content[3:-3]
                
            result = json.loads(content.strip())
            return {
                "score": float(result.get("score", 0.0)),
                "explanation": result.get("explanation", "No explanation provided.")
            }
        except Exception as e:
            logger.error(f"Error calling Bedrock for evaluation: {e}")
            return {"score": 0.0, "error": str(e)}

    @staticmethod
    def get_generated_dataset(s3_prefix: str) -> list[dict]:
        """Fetch the final generated dataset (JSONL) from S3."""
        object_key = f"{s3_prefix}clean_dataset.jsonl"
        try:
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=object_key)
            content = response["Body"].read().decode("utf-8")
            
            # Parse JSONL into a list of dictionaries
            dataset = []
            for idx, line in enumerate(content.strip().split("\n")):
                if line:
                    example = json.loads(line)
                    example["id"] = idx  # Assign a positional ID for editing
                    dataset.append(example)
            return dataset
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                return [] # Not ready yet
            logger.error(f"Error fetching dataset from S3: {e}")
            raise

    @staticmethod
    def generate_presigned_get_url(s3_key: str, expires_in: int = 3600) -> str:
        """Generate a presigned GET URL for downloading a file from S3."""
        try:
            url = s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": BUCKET_NAME, "Key": s3_key},
                ExpiresIn=expires_in,
            )
            return url
        except ClientError as e:
            logger.error(f"Error generating presigned GET URL: {e}")
            raise

    @staticmethod
    def get_execution_output(execution_arn: str) -> dict:
        """Get the final output of a completed Step Functions execution."""
        try:
            response = sfn_client.describe_execution(executionArn=execution_arn)
            status = response["status"]
            output = {}
            if status == "SUCCEEDED" and "output" in response:
                output = json.loads(response["output"])
            return {
                "status": status,
                "output": output,
                "start_date": response.get("startDate", "").isoformat() if response.get("startDate") else None,
                "stop_date": response.get("stopDate", "").isoformat() if response.get("stopDate") else None,
            }
        except ClientError as e:
            logger.error(f"Error getting execution output: {e}")
            raise

    @staticmethod
    def update_dataset_example(s3_prefix: str, example_id: int, data: dict) -> dict:
        """Update a single training example in the JSONL file on S3."""
        object_key = f"{s3_prefix}clean_dataset.jsonl"
        try:
            # Read the existing dataset
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=object_key)
            content = response["Body"].read().decode("utf-8")
            lines = [line for line in content.strip().split("\n") if line]

            if example_id < 0 or example_id >= len(lines):
                raise ValueError(f"Example ID {example_id} out of range (0-{len(lines) - 1})")

            # Update the target line
            existing = json.loads(lines[example_id])
            existing.update(data)
            # Remove the 'id' field if present — it's positional, not stored
            existing.pop("id", None)
            lines[example_id] = json.dumps(existing)

            # Write back
            new_content = "\n".join(lines) + "\n"
            s3_client.put_object(Bucket=BUCKET_NAME, Key=object_key, Body=new_content.encode("utf-8"))

            existing["id"] = example_id
            return existing
        except ClientError as e:
            logger.error(f"Error updating dataset example: {e}")
            raise

    @staticmethod
    def delete_dataset_example(s3_prefix: str, example_id: int) -> bool:
        """Delete a single training example from the JSONL file on S3."""
        object_key = f"{s3_prefix}clean_dataset.jsonl"
        try:
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=object_key)
            content = response["Body"].read().decode("utf-8")
            lines = [line for line in content.strip().split("\n") if line]

            if example_id < 0 or example_id >= len(lines):
                raise ValueError(f"Example ID {example_id} out of range (0-{len(lines) - 1})")

            lines.pop(example_id)

            new_content = "\n".join(lines) + "\n" if lines else ""
            s3_client.put_object(Bucket=BUCKET_NAME, Key=object_key, Body=new_content.encode("utf-8"))
            return True
        except ClientError as e:
            logger.error(f"Error deleting dataset example: {e}")
            raise

    @staticmethod
    def search_dataset(s3_prefix: str, query: str) -> list[dict]:
        """Search training examples by content (case-insensitive substring match)."""
        object_key = f"{s3_prefix}clean_dataset.jsonl"
        try:
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=object_key)
            content = response["Body"].read().decode("utf-8")
            query_lower = query.lower()

            results = []
            for idx, line in enumerate(content.strip().split("\n")):
                if line and query_lower in line.lower():
                    example = json.loads(line)
                    example["id"] = idx
                    results.append(example)
            return results
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                return []
            logger.error(f"Error searching dataset: {e}")
            raise

    @staticmethod
    def get_dataset_export_url(s3_prefix: str) -> str:
        """Generate a presigned GET URL for downloading the full JSONL dataset."""
        object_key = f"{s3_prefix}clean_dataset.jsonl"
        return AWSService.generate_presigned_get_url(object_key, expires_in=3600)

    @staticmethod
    def delete_s3_prefix(s3_prefix: str) -> bool:
        """Delete all objects under a given S3 prefix (best-effort)."""
        try:
            paginator = s3_client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=s3_prefix):
                objects = page.get("Contents", [])
                if objects:
                    delete_keys = [{"Key": obj["Key"]} for obj in objects]
                    s3_client.delete_objects(
                        Bucket=BUCKET_NAME,
                        Delete={"Objects": delete_keys}
                    )
            return True
        except ClientError as e:
            logger.error(f"Error deleting S3 prefix {s3_prefix}: {e}")
            return False

    # ── Model Comparison Methods ──────────────────────────────────────────────

    @staticmethod
    def invoke_base_model(prompt: str, system_prompt: str = None) -> dict:
        """Call the base foundation model (Bedrock Nova Micro) with a prompt."""
        messages = []
        if system_prompt:
            messages.append({"role": "user", "content": [{"text": f"System: {system_prompt}\n\nUser: {prompt}"}]})
        else:
            messages.append({"role": "user", "content": [{"text": prompt}]})

        try:
            response = bedrock_client.invoke_model(
                modelId="apac.amazon.nova-micro-v1:0",
                accept="application/json",
                contentType="application/json",
                body=json.dumps({
                    "messages": messages,
                    "inferenceConfig": {
                        "max_new_tokens": 1024,
                        "temperature": 0.7
                    }
                })
            )
            response_body = json.loads(response["body"].read().decode("utf-8"))
            content = response_body.get("output", {}).get("message", {}).get("content", [])
            text = content[0].get("text", "") if content else ""
            return {"response": text}
        except Exception as e:
            logger.error(f"Error calling Bedrock base model: {e}")
            return {"response": "", "error": str(e)}

    @staticmethod
    def invoke_sagemaker_endpoint(endpoint_name: str, prompt: str, system_prompt: str = None) -> dict:
        """Call a fine-tuned model deployed on SageMaker."""
        sagemaker_runtime = boto3.client("sagemaker-runtime", region_name="ap-south-1")

        full_prompt = prompt
        if system_prompt:
            full_prompt = f"### System:\n{system_prompt}\n\n### User:\n{prompt}\n\n### Assistant:\n"

        payload = json.dumps({
            "inputs": full_prompt,
            "parameters": {
                "max_new_tokens": 1024,
                "temperature": 0.7,
                "do_sample": True,
            }
        })

        try:
            response = sagemaker_runtime.invoke_endpoint(
                EndpointName=endpoint_name,
                ContentType="application/json",
                Body=payload,
            )
            result = json.loads(response["Body"].read().decode("utf-8"))
            # HuggingFace TGI returns [{"generated_text": "..."}]
            if isinstance(result, list) and len(result) > 0:
                text = result[0].get("generated_text", "")
            elif isinstance(result, dict):
                text = result.get("generated_text", result.get("output", ""))
            else:
                text = str(result)
            return {"response": text}
        except Exception as e:
            logger.error(f"Error calling SageMaker endpoint {endpoint_name}: {e}")
            return {"response": "", "error": str(e)}
