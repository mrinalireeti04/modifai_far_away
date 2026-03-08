"""
Quality Control Module.
Handles deduplication and threshold filtering based on universal scoring metrics.
"""
from typing import List, Dict, Any
from .scoring import compute_overlap_score, compute_length_score, compute_structural_score
from .utils import get_logger

logger = get_logger(__name__)

def remove_duplicates(dataset: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Removes duplicate generation samples."""
    seen = set()
    unique = []

    for sample in dataset:
        key = (
            str(sample.get("instruction", "")).strip().lower() +
            str(sample.get("input", "")).strip().lower() +
            str(sample.get("response", "")).strip().lower()
        )
        if key not in seen:
            seen.add(key)
            unique.append(sample)

    logger.info(f"Removed duplicates: {len(dataset)} -> {len(unique)}")
    return unique

def score_and_filter_dataset(
    dataset: List[Dict[str, Any]], 
    chunks: List[Dict[str, Any]], 
    threshold: float = 0.6
) -> List[Dict[str, Any]]:
    """
    Scores the dataset using universal metrics and filters out samples below the threshold.
    Final Score Formula: 0.5 * overlap + 0.3 * length + 0.2 * structural
    """
    logger.info("Scoring dataset and applying quality filters.")
    
    chunk_lookup = {c["chunk_id"]: c["text"] for c in chunks}
    scored_dataset = []

    for sample in dataset:
        chunk_text = chunk_lookup.get(sample.get("chunk_id"), "")
        
        overlap_q = compute_overlap_score(sample, chunk_text)
        length_q = compute_length_score(sample)
        structural_q = compute_structural_score(sample)

        final_score = (
            0.5 * overlap_q +
            0.3 * length_q +
            0.2 * structural_q
        )

        scored_dataset.append({
            "sample": sample,
            "score": round(final_score, 3)
        })

    # Filter based on threshold
    filtered = [
        item["sample"] for item in scored_dataset if item["score"] >= threshold
    ]
    
    logger.info(f"Quality Control retained {len(filtered)} out of {len(dataset)} samples (threshold={threshold}).")
    return filtered
