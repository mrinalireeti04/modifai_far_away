"""
Validation Module.
Validates the generated QA pairs using an LLM to ensure absolute strict grounding.
"""
import boto3
from typing import List, Dict, Any
from .utils import get_logger

logger = get_logger(__name__)

def validate_sample_grounding(
    sample: Dict[str, Any], 
    chunk_text: str,
    aws_region: str,
    model_id: str
) -> bool:
    """
    Uses an LLM to explicitly validate if the response is fully grounded in the chunk.
    """
    prompt = f"""
    You are a strict validator. Does the following 'Response' contain ONLY information present in the 'Source Chunk'? 
    Answer strictly with 'YES' or 'NO'.

    Source Chunk:
    {chunk_text}
    
    Instruction: {sample.get("instruction")}
    Response: {sample.get("response")}
    """
    try:
        client = boto3.client('bedrock-runtime', region_name=aws_region)
        response = client.converse(
            modelId=model_id,
            messages=[{
                "role": "user",
                "content": [{"text": prompt}]
            }],
            inferenceConfig={"temperature": 0.0, "maxTokens": 10}
        )
        
        answer = response['output']['message']['content'][0]['text'].strip().upper()
        return "YES" in answer
    except Exception as e:
        logger.error(f"Grounding validation failed: {e}")
        # Default to False on failure to be safe
        return False

def validate_dataset(
    dataset: List[Dict[str, Any]], 
    chunks: List[Dict[str, Any]], 
    config: Any
) -> List[Dict[str, Any]]:
    """Validates the entire dataset if validation_mode is 'validated'."""
    if config.validation_mode != "validated":
        logger.info("Validation mode is 'fast'. Skipping LLM grounding validation.")
        return dataset
        
    logger.info("Running strict grounding validation on dataset.")
    chunk_lookup = {c["chunk_id"]: c["text"] for c in chunks}
    
    validated = []
    for sample in dataset:
        chunk_text = chunk_lookup.get(sample.get("chunk_id"), "")
        if validate_sample_grounding(sample, chunk_text, config.aws_region, config.model_id):
            validated.append(sample)
            
    logger.info(f"Validation retained {len(validated)} out of {len(dataset)} samples.")
    return validated
