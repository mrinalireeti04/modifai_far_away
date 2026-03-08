"""
Main Pipeline Orchestration Module.
"""
import os
import json
from .config.settings import PipelineConfig
from .core.text_extraction import extract_text
from .core.chunking import create_chunks
from .core.dataset_generation import generate_dataset
from .core.validation import validate_dataset
from .core.quality_control import remove_duplicates, score_and_filter_dataset
from .core.utils import get_logger

logger = get_logger(__name__)

def run_pipeline(input_pdf_path: str, config: PipelineConfig = None, output_dir: str = ".") -> None:
    """Runs the complete Modifai pipeline."""
    if config is None:
        config = PipelineConfig()
        
    logger.info("=========================================")
    logger.info("Starting Modifai Pipeline")
    logger.info("=========================================")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Text Extraction
    logger.info("Step 1: Text Extraction")
    raw_text = extract_text(input_pdf_path)
    with open(os.path.join(output_dir, "raw_text.txt"), "w", encoding="utf-8") as f:
        f.write(raw_text)
        
    # 2. Chunking
    logger.info("Step 2: Intelligent Chunking")
    chunks = create_chunks(raw_text, max_words=config.max_chunk_words)
    with open(os.path.join(output_dir, "chunks.json"), "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=4)
        
    # 3. Dataset Generation
    logger.info("Step 3: Synthetic Dataset Generation")
    dataset = generate_dataset(chunks, config)
    with open(os.path.join(output_dir, "synthetic_dataset.jsonl"), "w", encoding="utf-8") as f:
        for sample in dataset:
            f.write(json.dumps(sample) + "\n")
            
    # 4. Strict Grounding Validation
    logger.info("Step 4: Grounding Validation")
    dataset = validate_dataset(dataset, chunks, config)
    
    # 5. Hybrid Quality Control (Deduplication + Scoring)
    logger.info("Step 5 & 6: Quality Control (Deduplication & Thresholding)")
    dataset = remove_duplicates(dataset)
    final_dataset = score_and_filter_dataset(dataset, chunks, threshold=config.qc_threshold)
    
    # 7. Final Dataset Export
    logger.info("Step 7: Final Dataset Export")
    final_output_path = os.path.join(output_dir, "final_dataset.jsonl")
    with open(final_output_path, "w", encoding="utf-8") as f:
        for sample in final_dataset:
            f.write(json.dumps(sample) + "\n")
            
    logger.info("=========================================")
    logger.info(f"Pipeline Completed Successfully! Final samples: {len(final_dataset)}")
    logger.info(f"Outputs saved to: {output_dir}")
    logger.info("=========================================")
    
    return final_dataset
