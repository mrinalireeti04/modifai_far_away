"""
Intelligent Document Chunking.
Provides configurable max words per chunk and maintains chunk IDs.
"""
import re
from typing import List, Dict, Any
from .utils import get_logger

logger = get_logger(__name__)

def create_chunks(text: str, max_words: int = 500) -> List[Dict[str, Any]]:
    """
    Splits text into chunks of maximum `max_words` words.
    Attempts to split by sentences/paragraphs rather than cutting off mid-sentence.
    """
    logger.info(f"Creating chunks with max_words={max_words}")
    
    # Simple semantic splitting by paragraphs or double newlines (normalized text means splitting by '. ')
    sentences = re.split(r'(?<=[.!?]) +', text)
    
    chunks = []
    current_chunk = []
    current_word_count = 0
    chunk_id = 1
    
    for sentence in sentences:
        words = sentence.split()
        if len(words) > max_words:
            # If a single sentence is longer than max_words, we must split it
            for i in range(0, len(words), max_words):
                sub_part = " ".join(words[i:i+max_words])
                part_words = len(sub_part.split())
                
                if current_word_count + part_words > max_words and current_chunk:
                    chunks.append({
                        "chunk_id": chunk_id,
                        "text": " ".join(current_chunk).strip()
                    })
                    chunk_id += 1
                    current_chunk = [sub_part]
                    current_word_count = part_words
                else:
                    current_chunk.append(sub_part)
                    current_word_count += part_words
        else:
            words_len = len(words)
            if current_word_count + words_len > max_words and current_chunk:
                chunks.append({
                    "chunk_id": chunk_id,
                    "text": " ".join(current_chunk).strip()
                })
                chunk_id += 1
                current_chunk = [sentence]
                current_word_count = words_len
            else:
                current_chunk.append(sentence)
                current_word_count += words_len
            
    if current_chunk:
        chunks.append({
            "chunk_id": chunk_id,
            "text": " ".join(current_chunk).strip()
        })
        
    logger.info(f"Generated {len(chunks)} chunks.")
    return chunks
