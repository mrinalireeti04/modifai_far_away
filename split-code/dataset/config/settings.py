"""
Configuration settings for the Modifai Pipeline.
DO NOT hardcode domain keywords. Keep settings universally applicable.
"""
import os
from dataclasses import dataclass

@dataclass
class PipelineConfig:
    # AWS Settings
    aws_profile: str = os.getenv("AWS_PROFILE", "default")
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    model_id: str = os.getenv("AWS_MODEL_ID", "amazon.nova-micro-v1:0")
    
    # Chunking Settings
    max_chunk_words: int = 500
    
    # Dataset Generation Settings
    mode: str = "QA" # Options: QA, instruction, tutor
    samples_per_chunk: int = 3
    
    # Validation
    validation_mode: str = "fast" # Options: fast, validated
    
    # Quality Control
    qc_threshold: float = 0.6
