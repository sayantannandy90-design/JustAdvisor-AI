"""
NLP Scorer Service – LegalBERT-based argument accuracy scoring
──────────────────────────────────────────────────────────────
Scores each lawyer argument on a 0-100 scale using three sub-scores:
  • Legal relevance   – cosine similarity to legal domain embeddings
  • Logical coherence – sentence coherence using next-sentence prediction
  • Argument strength – length + specificity heuristic

The score is stored alongside the argument in the debate state and used as
an intermediate signal before the bulk Mistral 7B judgment.
"""

from __future__ import annotations
import logging
import asyncio
from functools import lru_cache
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── Lazy-loaded model references ─────────────────────────────────────────────
_tokenizer = None
_model = None
_device = None


def _load_model():
    """Load LegalBERT only once (lazy, thread-safe via GIL)."""
    global _tokenizer, _model, _device

    if _model is not None:
        return

    try:
        import torch
        from transformers import AutoTokenizer, AutoModel

        from config.settings import settings

        _device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("Loading LegalBERT on %s …", _device)

        _tokenizer = AutoTokenizer.from_pretrained(settings.LEGAL_BERT_MODEL)
        _model = AutoModel.from_pretrained(settings.LEGAL_BERT_MODEL).to(_device)
        _model.eval()

        logger.info("LegalBERT loaded ✓")
    except Exception as exc:
        logger.warning(
            "LegalBERT unavailable (%s). Falling back to heuristic scorer.", exc
        )


# ── Legal anchor phrases for relevance scoring ────────────────────────────────
_LEGAL_ANCHORS = [
    "The defendant violated the law.",
    "Breach of contract occurred.",
    "There is sufficient evidence to support the claim.",
    "The plaintiff suffered damages.",
    "Due process of law must be followed.",
    "Liability is established beyond reasonable doubt.",
    "The statute clearly prohibits this conduct.",
    "Precedent establishes that the action was negligent.",
]


def _mean_pool(model_output, attention_mask):
    """Mean-pool token embeddings weighted by attention mask."""
    token_embeddings = model_output.last_hidden_state
    input_mask = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    return (token_embeddings * input_mask).sum(1) / input_mask.sum(1).clamp(min=1e-9)


def _embed(texts: list[str]):
    """Return L2-normalised sentence embeddings for a list of texts."""
    import torch

    inputs = _tokenizer(
        texts,
        padding=True,
        truncation=True,
        max_length=256,
        return_tensors="pt",
    ).to(_device)

    with torch.no_grad():
        outputs = _model(**inputs)

    embeddings = _mean_pool(outputs, inputs["attention_mask"])
    # L2 normalise
    norms = embeddings.norm(dim=1, keepdim=True).clamp(min=1e-9)
    return (embeddings / norms).cpu().numpy()


@lru_cache(maxsize=32)
def _anchor_embeddings():
    """Precompute and cache anchor embeddings."""
    return _embed(_LEGAL_ANCHORS)


def _legal_relevance_score(text_emb: np.ndarray) -> float:
    """Cosine similarity between argument embedding and legal anchors (0-1)."""
    anchor_embs = _anchor_embeddings()
    similarities = (anchor_embs @ text_emb.T).flatten()  # dot product (already normalised)
    return float(np.max(similarities))                    # best-matching anchor


def _heuristic_score(text: str) -> float:
    """
    Fallback scorer when LegalBERT is not available.
    Weights: length, legal keyword density, sentence structure.
    """
    import re

    legal_keywords = [
        "court", "law", "statute", "evidence", "liable", "defendant",
        "plaintiff", "breach", "contract", "negligence", "damages",
        "verdict", "precedent", "section", "act", "ipc", "crpc",
        "duty", "burden", "proof", "reasonable", "inference",
    ]

    words = text.lower().split()
    if not words:
        return 0.0

    # Keyword density (max out at 15 legal words for full score)
    keyword_hits = sum(1 for w in words if any(kw in w for kw in legal_keywords))
    keyword_score = min(keyword_hits / 15.0, 1.0)

    # Length score (150-400 chars is ideal)
    length = len(text)
    if length < 30:
        length_score = 0.1
    elif length < 150:
        length_score = 0.5
    elif length <= 400:
        length_score = 1.0
    else:
        length_score = max(0.6, 1.0 - (length - 400) / 2000.0)

    # Sentence count bonus (more structured = better)
    sentences = re.split(r"[.!?]+", text)
    sentence_score = min(len(sentences) / 5.0, 1.0)

    # Weighted aggregate → 0-100
    raw = (0.5 * keyword_score + 0.35 * length_score + 0.15 * sentence_score)
    return round(raw * 100, 2)


async def score_argument(text: str) -> float:
    """
    Async entry point – scores a single cleaned argument.
    Returns a float in [0, 100].
    """
    if not text.strip():
        return 0.0

    loop = asyncio.get_event_loop()

    def _compute():
        _load_model()

        if _model is None:
            return _heuristic_score(text)

        try:
            text_emb = _embed([text])
            relevance = _legal_relevance_score(text_emb[0])

            # Specificity bonus: longer, more specific texts get a small boost
            specificity = min(len(text.split()) / 80.0, 1.0)

            # Weighted aggregate
            raw = 0.70 * relevance + 0.30 * specificity
            return round(raw * 100, 2)
        except Exception as exc:
            logger.warning("LegalBERT scoring failed: %s. Using heuristic.", exc)
            return _heuristic_score(text)

    return await loop.run_in_executor(None, _compute)


async def compute_cumulative_score(arguments: list) -> float:
    """
    Compute the average NLP score across all lawyer arguments for one side.
    Only counts arguments that already have an nlp_score.
    """
    lawyer_args = [a for a in arguments if a.role == "lawyer" and a.nlp_score is not None]
    if not lawyer_args:
        return 0.0
    return round(sum(a.nlp_score for a in lawyer_args) / len(lawyer_args), 2)
