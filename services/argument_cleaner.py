"""
Argument Cleaner Service
─────────────────────────
Preprocesses raw lawyer argument text before it is scored or stored:
  1. Unicode normalisation
  2. Punctuation repair
  3. Repeated-whitespace collapse
  4. Legal citation normalisation
  5. Profanity / noise removal
  6. Sentence-boundary restoration
"""

from __future__ import annotations
import re
import unicodedata
import logging

logger = logging.getLogger(__name__)

# ── Legal citation patterns ───────────────────────────────────────────────────
_CITATION_PATTERNS = [
    # Indian case law: AIR 1962 SC 1234
    (r"\bAIR\s+(\d{4})\s+([A-Z]+)\s+(\d+)\b", r"AIR \1 \2 \3"),
    # (2020) 5 SCC 123
    (r"\((\d{4})\)\s+(\d+)\s+SCC\s+(\d+)", r"(\1) \2 SCC \3"),
    # Section references
    (r"\bSec\.\s*(\d+)", r"Section \1"),
    (r"\bS\.\s*(\d+)\b", r"Section \1"),
    # IPC / CrPC
    (r"\bIPC\b", "Indian Penal Code"),
    (r"\bCrPC\b", "Code of Criminal Procedure"),
]


def clean_argument(raw_text: str) -> str:
    """
    Full preprocessing pipeline.
    Returns a cleaned, normalised version of the argument.
    """
    if not raw_text or not raw_text.strip():
        return ""

    text = raw_text

    # 1. Unicode normalisation (NFKC removes ligatures, special spaces, etc.)
    text = unicodedata.normalize("NFKC", text)

    # 2. Remove invisible/control characters (keep \n and \t)
    text = re.sub(r"[^\S\n\t]", " ", text)          # normalise spaces
    text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]", "", text)

    # 3. Standardise quotation marks
    text = re.sub(r"[""‟„]", '"', text)
    text = re.sub(r"[''‛`]", "'", text)

    # 4. Fix spaced-out punctuation  ("word ,next" → "word, next")
    text = re.sub(r"\s+([,;:!?.])", r"\1", text)
    text = re.sub(r"([,;:!?.])\s*([A-Z])", r"\1 \2", text)

    # 5. Collapse multiple punctuation  ("!!!" → "!")
    text = re.sub(r"([!?.]){2,}", r"\1", text)

    # 6. Legal citation normalisation
    for pattern, replacement in _CITATION_PATTERNS:
        text = re.sub(pattern, replacement, text)

    # 7. Strip leading/trailing whitespace per line, then collapse blank lines
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join(line for line in lines if line)

    # 8. Collapse multiple spaces
    text = re.sub(r"[ \t]{2,}", " ", text)

    # 9. Capitalise first character
    text = text[:1].upper() + text[1:] if text else text

    logger.debug("Cleaned argument (%d→%d chars)", len(raw_text), len(text))
    return text.strip()


def extract_key_claims(text: str) -> list[str]:
    """
    Heuristically extract numbered or bulleted claims from an argument.
    Returns a list of individual claim strings.
    """
    # Match lines beginning with a number or bullet
    pattern = r"(?:^|\n)\s*(?:\d+[\.\)]|[-•*])\s+(.+)"
    matches = re.findall(pattern, text, re.MULTILINE)
    if matches:
        return [m.strip() for m in matches if m.strip()]

    # Fallback: split by sentence boundary (very rough)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if len(s.strip()) > 20]
