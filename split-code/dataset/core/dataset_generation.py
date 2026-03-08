"""
Synthetic Dataset Generation Module using Amazon Nova Micro.
"""
import json
import boto3
from typing import List, Dict, Any
from .utils import get_logger

logger = get_logger(__name__)

def generate_samples_for_chunk(
    chunk: Dict[str, Any], 
    mode: str, 
    samples_per_chunk: int,
    aws_region: str,
    model_id: str
) -> List[Dict[str, Any]]:
    """
    Generates synthetic QA/instruction pairs for a single chunk using AWS Bedrock.
    """
    logger.debug(f"Generating {samples_per_chunk} samples for chunk {chunk['chunk_id']}")
    
    prompt = f"""
    You are an expert data generator. Based on the following source document chunk, 
    generate exactly {samples_per_chunk} high-quality QA pairs. 
    Mode: {mode}.
    
    Respond STRICTLY in the following JSON format as a list of dictionaries:
    [
        {{"instruction": "The question or instruction based on the chunk.", "input": "", "response": "The detailed answer found in the chunk."}}
    ]
    Do not include any other text, markdown blocks, or explanations. Just valid JSON.
    
    Source Document Chunk:
    {chunk['text']}
    """
    
    try:
        client = boto3.client('bedrock-runtime', region_name=aws_region)
        response = client.converse(
            modelId=model_id,
            messages=[{
                "role": "user",
                "content": [{"text": prompt}]
            }],
            inferenceConfig={
                "temperature": 0.7,
                "maxTokens": 1000,
            }
        )
        
        response_text = response['output']['message']['content'][0]['text']
        
        # Strip markdown json block if present
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
            
        json_str = response_text.strip()
        samples = json.loads(json_str)
        
        # Attach chunk_id to each sample
        for sample in samples:
            sample["chunk_id"] = chunk["chunk_id"]
            
        return samples
    except Exception as e:
        logger.error(f"Failed to generate samples for chunk {chunk['chunk_id']}: {e}")
        return []

def generate_dataset(
    chunks: List[Dict[str, Any]], 
    config: Any
) -> List[Dict[str, Any]]:
    """Generates the dataset for all chunks."""
    logger.info(f"Generating dataset using model {config.model_id} for {len(chunks)} chunks.")
    
    dataset = []
    for chunk in chunks:
        samples = generate_samples_for_chunk(
            chunk=chunk,
            mode=config.mode,
            samples_per_chunk=config.samples_per_chunk,
            aws_region=config.aws_region,
            model_id=config.model_id
        )
        dataset.extend(samples)
        
    logger.info(f"Generated a total of {len(dataset)} synthetic samples.")
    return dataset
