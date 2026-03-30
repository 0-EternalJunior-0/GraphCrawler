"""Shared text utilities for plugins.

Provides common text processing functions used across multiple plugins.
"""

import re
from typing import List, Optional, Set

# Ukrainian and English stop words for keyword extraction
STOP_WORDS: Set[str] = {
    # Ukrainian
    "і", "та", "або", "а", "але", "що", "як", "це", "на", "в", "у", "з", "із",
    "до", "від", "про", "для", "по", "за", "над", "під", "між", "через",
    "шукаю", "знайти", "потрібно", "хочу", "треба", "сторінки", "сторінка",
    # English
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "need", "dare",
    "to", "of", "in", "for", "on", "with", "at", "by", "from", "about",
    "find", "search", "looking", "want", "pages", "page", "content",
}


def extract_keywords(
    text: str,
    max_keywords: int = 10,
    min_word_length: int = 3,
    custom_stop_words: Optional[Set[str]] = None,
) -> List[str]:
    """
    Extract keywords from text by filtering stop words.

    Args:
        text: Input text to extract keywords from
        max_keywords: Maximum number of keywords to return
        min_word_length: Minimum word length to consider
        custom_stop_words: Additional stop words to filter (merged with defaults)

    Returns:
        List of unique keywords (lowercase)

    Example:
        >>> extract_keywords("Looking for Python developer jobs in Kyiv")
        ['python', 'developer', 'jobs', 'kyiv']
    """
    if not text:
        return []

    stop_words = STOP_WORDS.copy()
    if custom_stop_words:
        stop_words.update(custom_stop_words)

    # Tokenize - extract word characters
    words = re.findall(r"\b\w+\b", text.lower())

    # Filter by length and stop words
    keywords = []
    seen = set()

    for word in words:
        if len(word) >= min_word_length and word not in stop_words and word not in seen:
            keywords.append(word)
            seen.add(word)

            if len(keywords) >= max_keywords:
                break

    return keywords


def normalize_text(text: str, max_length: Optional[int] = None) -> str:
    """
    Normalize text by collapsing whitespace.

    Args:
        text: Input text
        max_length: Optional maximum length to truncate to

    Returns:
        Normalized text
    """
    if not text:
        return ""

    # Collapse multiple whitespace to single space
    normalized = " ".join(text.split())

    if max_length and len(normalized) > max_length:
        normalized = normalized[:max_length]

    return normalized
