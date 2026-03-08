import boto3
import json
from botocore.config import Config

# Optimized Configuration for AI APIs (Higher timeout for LLM reasoning)
ai_config = Config(
    region_name='us-east-1',
    signature_version='v4',
    retries={'max_attempts': 3, 'mode': 'standard'},
    connect_timeout=10,
    read_timeout=60  # Bedrock needs time for deep thinking
)

# Initialize Clients
bedrock = boto3.client('bedrock-runtime', config=ai_config)
textract = boto3.client('textract', config=ai_config)

def run_ai_wrapper(bucket, key, user_intent):
    """
    Main entry point for the backend. 
    Returns refined intent, validation status, and best model.
    """
    try:
        print(f"--- Modifai Intelligence Booting for {key} ---")
        
        # Step 1: Intent Refiner
        refined_goal = _call_llm(f"Refine this intent into a technical AI fine-tuning goal: {user_intent}")
        
        # Step 2: Relevance Validator (Fast OCR check)
        # Only reads the first few lines to keep it efficient and cheap
        raw_data = _get_document_sample(bucket, key)
        relevance_check = _call_llm(f"Is this text: '{raw_data}' relevant to: '{refined_goal}'? Answer YES or NO.")
        
        is_valid = "YES" in relevance_check.upper()
        if not is_valid:
            return {"status": "rejected", "reason": "Data does not match intent."}

        # Step 3: Model Strategist
        model_choice = _call_llm(f"Goal: {refined_goal}. Best model? 'Mistral-7B' or 'Llama-3-8B'. Return only name.")

        return {
            "status": "success",
            "refined_intent": refined_goal,
            "model_choice": model_choice,
            "validation_sample": raw_data[:100] + "..."
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

def _call_llm(prompt):
    """Internal helper to hit Bedrock Claude 3 Haiku (The fastest model)"""
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 400,
        "messages": [{"role": "user", "content": prompt}]
    })
    response = bedrock.invoke_model(
        modelId='anthropic.claude-3-haiku-20240307-v1:0',
        body=body
    )
    return json.loads(response.get('body').read())['content'][0]['text']

def _get_document_sample(bucket, key):
    """Efficiently pulls first 15 lines of a document for quick validation"""
    response = textract.detect_document_text(
        Document={'S3Object': {'Bucket': bucket, 'Name': key}}
    )
    lines = [b['Text'] for b in response['Blocks'] if b['BlockType'] == 'LINE']
    return " ".join(lines[:15])