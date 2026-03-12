"""
AI Advisor Service
──────────────────
Provides real-time per-role legal hints to each lawyer after they submit
an argument.  Uses a lightweight Mistral Instruct model (or a rule-based
fallback when the GPU model is unavailable).

Each advisor is role-aware:
  • Side A (Prosecutor / Plaintiff) — focuses on establishing liability,
    burden of proof, evidence, and damages.
  • Side B (Defendant) — focuses on refutation, lack of intent, civil
    vs criminal distinction, and procedural defences.
"""

from __future__ import annotations
import logging
import asyncio
import random
from typing import Literal

logger = logging.getLogger(__name__)

LawyerSide = Literal["A", "B"]

# ── Rule-based fallback hints ─────────────────────────────────────────────────
_PROSECUTOR_HINTS = [
    "Strengthen your argument by citing the specific statutory provision violated.",
    "Emphasise how the defendant's action directly caused the plaintiff's loss.",
    "Reference any documentary evidence (invoices, communications, agreements) that supports your claim.",
    "Address the burden of proof – explain why the evidence meets the required standard.",
    "Quote a precedent case where similar conduct was held liable.",
    "Highlight the foreseeability of harm to underline the duty of care.",
    "Counter the defendant's most recent argument point by point.",
    "Quantify the damages claimed and explain the method of calculation.",
    "Point out any inconsistencies in the defendant's narrative.",
    "Invoke any statutory presumptions that shift the burden to the defendant.",
]

_DEFENDANT_HINTS = [
    "Stress that a civil breach does not automatically constitute criminal fraud.",
    "Argue that market conditions beyond your client's control caused the delay.",
    "Emphasise the absence of mens rea (dishonest intent) from the outset.",
    "Point out that the contract was never formally terminated – obligations remain.",
    "Cite precedents where similar commercial disputes were resolved civilly.",
    "Highlight any partial performance or good-faith efforts made by your client.",
    "Challenge the plaintiff's evidence on its admissibility or reliability.",
    "Argue that the plaintiff mitigated damages inadequately.",
    "Demonstrate that your client expressed willingness to refund or renegotiate.",
    "Raise procedural defences: limitation period, jurisdiction, or pre-suit notice.",
]

# ── System prompts ────────────────────────────────────────────────────────────
_PROSECUTOR_SYSTEM = (
    "You are a highly experienced AI Legal Advisor assisting the Prosecutor/Plaintiff's lawyer. "
    "Your role is to provide a concise, actionable tactical hint (2-3 sentences) "
    "to strengthen the lawyer's next argument. Focus on legal principles, evidence strategy, "
    "statutory citations, and case precedents. Be direct and practical."
)

_DEFENDANT_SYSTEM = (
    "You are a highly experienced AI Legal Advisor assisting the Defendant's lawyer. "
    "Your role is to provide a concise, actionable tactical hint (2-3 sentences) "
    "to strengthen the lawyer's next argument or rebut the latest prosecution point. "
    "Focus on refutation strategy, mens rea, civil vs criminal distinctions, and precedents. "
    "Be direct and practical."
)


# ── Lazy-loaded advisor model ─────────────────────────────────────────────────
_advisor_pipeline = None


def _load_advisor():
    global _advisor_pipeline
    if _advisor_pipeline is not None:
        return

    try:
        from transformers import pipeline
        from config.settings import settings

        logger.info("Loading Advisor model (%s)…", settings.ADVISOR_MODEL)
        _advisor_pipeline = pipeline(
            "text-generation",
            model=settings.ADVISOR_MODEL,
            max_new_tokens=settings.ADVISOR_MAX_TOKENS,
            device_map="auto",
            torch_dtype="auto",
        )
        logger.info("Advisor model loaded ✓")
    except Exception as exc:
        logger.warning("Advisor model unavailable (%s). Using rule-based hints.", exc)


def _rule_based_hint(side: LawyerSide) -> str:
    hints = _PROSECUTOR_HINTS if side == "A" else _DEFENDANT_HINTS
    return random.choice(hints)


def _model_based_hint(argument: str, case_context: str, side: LawyerSide) -> str:
    system = _PROSECUTOR_SYSTEM if side == "A" else _DEFENDANT_SYSTEM
    prompt = (
        f"<s>[INST] {system}\n\n"
        f"Case context: {case_context}\n\n"
        f"Lawyer's latest argument: {argument}\n\n"
        f"Provide your tactical hint: [/INST]"
    )
    outputs = _advisor_pipeline(prompt, do_sample=True, temperature=0.7)
    generated = outputs[0]["generated_text"]
    # Strip the prompt from the output
    hint = generated[len(prompt):].strip()
    # Cap at 3 sentences
    sentences = hint.split(". ")
    return ". ".join(sentences[:3]).strip() + ("." if not hint.endswith(".") else "")


async def get_advisor_hint(
    argument: str,
    side: LawyerSide,
    case_context: str = "",
) -> tuple[str, float]:
    """
    Returns (hint_text, confidence_score).
    confidence is 0.9 for model-based, 0.6 for rule-based fallback.
    """
    loop = asyncio.get_event_loop()

    def _compute():
        _load_advisor()
        if _advisor_pipeline is None:
            return _rule_based_hint(side), 0.6
        try:
            hint = _model_based_hint(argument, case_context, side)
            return hint, 0.9
        except Exception as exc:
            logger.warning("Advisor model inference failed: %s", exc)
            return _rule_based_hint(side), 0.6

    return await loop.run_in_executor(None, _compute)
