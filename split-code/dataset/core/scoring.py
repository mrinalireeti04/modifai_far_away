"""
Scoring module for quality control using universal quality signals.
No hardcoded domain-specific logic.
"""
import re
from typing import Dict, Any

def tokenize(text: str) -> set:
    """Tokenizes text into a set of lowercased alphanumeric words."""
    return set(re.findall(r"\b\w+\b", str(text).lower()))

def compute_overlap_score(sample: Dict[str, Any], chunk_text: str) -> float:
    """
    Measures how much vocabulary from the response appears in the chunk.
    overlap_score = len(overlap) / len(unique_words_in_response)
    """
    response_words = tokenize(sample.get("response", ""))
    chunk_words = tokenize(chunk_text)

    if not response_words:
        return 0.0

    overlap = response_words.intersection(chunk_words)
    return len(overlap) / len(response_words)

def compute_length_score(sample: Dict[str, Any]) -> float:
    """
    Scores the length of the response, penalizing very short answers.
    length_score = min(len(response_words) / 80, 1.0)
    """
    words = len(str(sample.get("response", "")).split())
    return min(words / 80, 1.0)

def compute_structural_score(sample: Dict[str, Any]) -> float:
    """
    Checks for required keys and minimum response formatting.
    """
    if not all(k in sample for k in ["instruction", "input", "response"]):
        return 0.0
    if len(str(sample.get("response", "")).strip()) < 20:
        return 0.2
    return 1.0
