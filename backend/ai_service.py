"""Offline AI study assistant.

Two features, both fully deterministic and both running with no API key, no network
call and no third-party AI library:

1. summarize_notes()  -- turns raw study notes into a fixed three-key JSON shape.
2. mock_embed() + cosine_similarity() -- rank a small set of study notes against a
   query by embedding both and comparing them.

AI_MODE selects the backend. Only "mock" is implemented in this submission; the
variable exists so a real provider could be slotted in later without changing the
endpoints. See the README for the exact prompt a real LLM would be sent.
"""

import math
import os
import re
from typing import Any, Dict, List

AI_MODE = os.getenv("AI_MODE", "mock")

# --------------------------------------------------------------------------- #
# Sample study notes used by the semantic-search feature.
# --------------------------------------------------------------------------- #
notes = [
    {"id": 1, "text": "Binary search requires a sorted array and repeatedly halves the search range using a midpoint comparison."},
    {"id": 2, "text": "Insertion sort builds a sorted list one element at a time by shifting larger elements to the right."},
    {"id": 3, "text": "FastAPI uses Pydantic models to validate request bodies and automatically generates Swagger documentation."},
    {"id": 4, "text": "SQL joins combine rows from two tables using a matching column, such as inner join, left join, and full join."},
    {"id": 5, "text": "Prompt engineering structures a task, context, constraints, and desired output format to guide an LLM's response."},
]


# --------------------------------------------------------------------------- #
# Feature 1: note summarizer (structured output, fixed JSON shape)
# --------------------------------------------------------------------------- #

# Words that are common enough to be useless as a topic label.
_TOPIC_STOPWORDS = frozenset(
    {
        "that", "this", "with", "from", "they", "them", "have", "has", "been", "were",
        "will", "when", "what", "which", "your", "their", "there", "then", "than",
        "into", "using", "used", "also", "such", "only", "more", "some", "each",
        "other", "these", "those", "about", "because", "while", "where", "would",
        "could", "should", "very", "must", "does", "here", "over", "just", "like",
    }
)

# Word-count thresholds for the difficulty label (documented in the README):
#   fewer than 40 words -> "easy", 40..100 inclusive -> "medium", more than 100 -> "hard"
_EASY_MAX_WORDS = 40
_MEDIUM_MAX_WORDS = 100

# The exact keys summarize_notes() always returns -- no more, no fewer.
SUMMARY_KEYS = ("topic", "key_points", "difficulty")


def _derive_topic(raw_text: str) -> str:
    """Topic rule: the most frequent 'non-trivial' word in the text.

    Non-trivial means at least four characters long and not in the stopword list.
    Ties are broken by earliest appearance, which keeps the result deterministic.
    If no word qualifies, fall back to the most frequent token of any length, and
    if the text has no word characters at all, to the literal "untitled".
    """
    tokens = re.findall(r"[a-z0-9]+", raw_text.lower())
    if not tokens:
        return "untitled"

    def most_frequent(candidates: List[str]) -> str:
        counts: Dict[str, int] = {}
        for token in candidates:
            counts[token] = counts.get(token, 0) + 1
        # dicts keep insertion order, and max() keeps the first of equal maxima,
        # so the earliest-appearing word wins a tie.
        return max(counts.items(), key=lambda item: item[1])[0]

    meaningful = [t for t in tokens if len(t) >= 4 and t not in _TOPIC_STOPWORDS]
    return most_frequent(meaningful) if meaningful else most_frequent(tokens)


def _derive_key_points(raw_text: str) -> List[str]:
    """Split the text into sentences on '.', '!' and '?', and keep up to three.

    Each kept sentence is stripped and its internal whitespace runs collapsed, so a
    note pasted across several lines still reads as one clean sentence.
    """
    key_points = []
    for sentence in re.split(r"[.!?]", raw_text):
        cleaned = " ".join(sentence.split())
        if cleaned:
            key_points.append(cleaned)
        if len(key_points) == 3:
            break
    return key_points


def _derive_difficulty(raw_text: str) -> str:
    """Difficulty from the total word count against two fixed thresholds."""
    word_count = len(raw_text.split())
    if word_count < _EASY_MAX_WORDS:
        return "easy"
    if word_count <= _MEDIUM_MAX_WORDS:
        return "medium"
    return "hard"


def summarize_notes(raw_text: str) -> Dict[str, Any]:
    """Summarize study notes into exactly {topic, key_points, difficulty}.

    Deterministic: the same input always produces byte-for-byte the same output.

    Empty or whitespace-only input is handled rather than raising -- there is no
    first line and no word to count, so the normal topic rule has nothing to work
    with and topic falls back to "untitled", key_points is [], and the word count of
    0 puts difficulty in the "easy" band.
    """
    if not raw_text or not raw_text.strip():
        return {"topic": "untitled", "key_points": [], "difficulty": "easy"}

    return {
        "topic": _derive_topic(raw_text),
        "key_points": _derive_key_points(raw_text),
        "difficulty": _derive_difficulty(raw_text),
    }


# --------------------------------------------------------------------------- #
# Feature 2: embeddings + cosine similarity
# --------------------------------------------------------------------------- #

# Fixed 12-word vocabulary. Order matters: it defines each vector position.
VOCABULARY = [
    "sort", "search", "binary", "insertion", "sql", "join",
    "fastapi", "pydantic", "prompt", "llm", "database", "validate",
]


def mock_embed(text: str) -> List[float]:
    """Embed `text` as a 12-dimensional word-count vector over VOCABULARY.

    Tokenization lower-cases the input and splits on any run of characters that are
    not letters or digits, so spaces, punctuation and apostrophes all separate
    tokens ("LLM's" becomes "llm" and "s"). Only exact whole-token matches count --
    "sorted" is a different token from "sort" and contributes nothing.

    The result is always a list of exactly 12 numbers, all zeros for an empty string.
    """
    tokens = [token for token in re.split(r"[^a-z0-9]+", text.lower()) if token]

    counts = {word: 0.0 for word in VOCABULARY}
    for token in tokens:
        if token in counts:
            counts[token] += 1.0

    return [counts[word] for word in VOCABULARY]


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Cosine similarity from first principles: dot product / (|a| * |b|).

    Returns 0.0 when either vector has a magnitude of exactly zero -- which happens
    whenever a text contains none of the 12 vocabulary words (an empty query, or one
    made only of out-of-vocabulary words). That guard means this function can never
    raise ZeroDivisionError.
    """
    if len(vec_a) != len(vec_b):
        raise ValueError("cosine_similarity needs two vectors of the same length.")

    dot_product = 0.0
    sum_squares_a = 0.0
    sum_squares_b = 0.0
    for a, b in zip(vec_a, vec_b):
        dot_product += a * b
        sum_squares_a += a * a
        sum_squares_b += b * b

    magnitude_a = math.sqrt(sum_squares_a)
    magnitude_b = math.sqrt(sum_squares_b)

    if magnitude_a == 0.0 or magnitude_b == 0.0:
        return 0.0

    similarity = dot_product / (magnitude_a * magnitude_b)

    # Cosine similarity is mathematically bounded to [-1, 1], but floating-point
    # rounding can push a vector compared with itself to 1.0000000000000002.
    # Clamping to the true bound keeps the result honest (and makes self-similarity
    # come back as exactly 1.0).
    return max(-1.0, min(1.0, similarity))


def search_notes(query: str) -> List[Dict[str, Any]]:
    """Rank the sample notes against `query`, most similar first.

    A query that embeds to an all-zero vector scores every note 0.0; because
    sorted() is stable, the notes then come back in their original id order rather
    than an arbitrary one, and nothing divides by zero.
    """
    query_vector = mock_embed(query)

    scored = [
        {
            "id": note["id"],
            "text": note["text"],
            "score": cosine_similarity(query_vector, mock_embed(note["text"])),
        }
        for note in notes
    ]

    return sorted(scored, key=lambda item: item["score"], reverse=True)
