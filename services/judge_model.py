"""
Judge Model Service – Mistral 7B + LoRA Adapter
─────────────────────────────────────────────────
Loads the fine-tuned Mistral 7B model with QLoRA adapter and runs
bulk inference once ≥10 arguments per side are queued.

Parses the structured model output into:
  • Arguments Summary
  • Per-argument Evaluation & Weighting
  • Final Verdict
  • Winning Side determination
  • Assumptions Check
"""

from __future__ import annotations
import re
import logging
import asyncio
from datetime import datetime
from typing import Optional

from models.schemas import JudgmentResult, ArgumentEvaluation
from config.settings import settings

logger = logging.getLogger(__name__)

# ── Lazy-loaded model references ──────────────────────────────────────────────
_tokenizer = None
_model = None


def _load_judge():
    global _tokenizer, _model

    if _model is not None:
        return

    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
        from peft import PeftModel

        logger.info("Loading Mistral 7B judge model…")

        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )

        _tokenizer = AutoTokenizer.from_pretrained(settings.BASE_MODEL)
        _tokenizer.pad_token = _tokenizer.eos_token

        base = AutoModelForCausalLM.from_pretrained(
            settings.BASE_MODEL,
            quantization_config=bnb_config,
            device_map="auto",
        )
        _model = PeftModel.from_pretrained(base, settings.ADAPTER_PATH)
        _model.eval()

        logger.info("Mistral 7B judge loaded ✓")

    except Exception as exc:
        logger.warning(
            "Judge model unavailable (%s). Judgment will use mock output.", exc
        )


# ── Prompt builder ────────────────────────────────────────────────────────────
def _build_prompt(
    case_title: str,
    case_facts: str,
    args_A: list[str],
    args_B: list[str],
) -> str:
    numbered_A = "\n".join(f"{i+1}. {a}" for i, a in enumerate(args_A))
    numbered_B = "\n".join(f"{i+1}. {b}" for i, b in enumerate(args_B))

    return (
        "<s>[INST] "
        "You are a neutral AI Judge presiding over a simulated courtroom.\n\n"
        "IMPORTANT RULES:\n"
        "- Decide strictly on the basis of stated facts and arguments.\n"
        "- Do NOT assume any unstated facts or external circumstances.\n"
        "- The verdict must be based on cumulative evaluation of all arguments.\n"
        "- No single argument shall be decisive on its own.\n\n"
        f"Case: {case_title}\n\n"
        f"Case facts:\n{case_facts}\n\n"
        f"Lawyer A (Prosecutor/Plaintiff) arguments:\n{numbered_A}\n\n"
        f"Lawyer B (Defendant) arguments:\n{numbered_B}\n\n"
        "Judicial Reasoning Instructions:\n"
        "1. List all arguments from both sides.\n"
        "2. Evaluate each argument independently.\n"
        "3. Assign relative weight (High / Medium / Low).\n"
        "4. Weigh arguments cumulatively.\n"
        "5. Identify the winning side (A or B or Draw).\n"
        "6. Deliver a reasoned verdict.\n\n"
        "OUTPUT FORMAT (use exactly these headers):\n"
        "Arguments Summary:\n"
        "Evaluation & Weighting:\n"
        "Final Verdict:\n"
        "Winning Side: [A / B / Draw]\n"
        "Assumptions Check (Yes/No):\n"
        "[/INST] "
        "Arguments Summary:\n"
    )


# ── Output parser ─────────────────────────────────────────────────────────────
def _parse_verdict(raw: str, case_id: str, case_title: str, score_A: float, score_B: float) -> JudgmentResult:
    """Parse the raw model output into a structured JudgmentResult."""

    def _extract_section(text: str, header: str, next_headers: list[str]) -> str:
        pattern = rf"{re.escape(header)}\s*(.*?)(?={'|'.join(re.escape(h) for h in next_headers)}|$)"
        m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        return m.group(1).strip() if m else ""

    all_headers = [
        "Arguments Summary:",
        "Evaluation & Weighting:",
        "Final Verdict:",
        "Winning Side:",
        "Assumptions Check",
    ]

    summary    = _extract_section(raw, "Arguments Summary:", all_headers[1:])
    evaluation = _extract_section(raw, "Evaluation & Weighting:", all_headers[2:])
    verdict    = _extract_section(raw, "Final Verdict:", all_headers[3:])
    winning    = _extract_section(raw, "Winning Side:", all_headers[4:])
    assumption = _extract_section(raw, "Assumptions Check", [])

    # Determine winning side
    winning_side = None
    winning_upper = winning.upper()
    if "DRAW" in winning_upper:
        winning_side = "Draw"
    elif "A" in winning_upper:
        winning_side = "A"
    elif "B" in winning_upper:
        winning_side = "B"

    # Parse evaluation bullets into ArgumentEvaluation objects
    evaluations: list[ArgumentEvaluation] = []
    eval_lines = re.findall(
        r"(?:Lawyer\s*([AB])[^\n]*?:?\s*)([^\n]+?)\s*[–-]\s*(High|Medium|Low)\s*[–-]?\s*([^\n]+)",
        evaluation,
        re.IGNORECASE,
    )
    for side, arg_text, weight, reasoning in eval_lines:
        evaluations.append(ArgumentEvaluation(
            argument=arg_text.strip(),
            side=side.upper(),
            weight=weight.capitalize(),
            reasoning=reasoning.strip(),
        ))

    return JudgmentResult(
        case_id=case_id,
        case_title=case_title,
        status="complete",
        arguments_summary=summary,
        evaluation=evaluations,
        final_verdict=verdict,
        winning_side=winning_side,
        score_A=score_A,
        score_B=score_B,
        assumptions_check=assumption,
        raw_output=raw,
        completed_at=datetime.utcnow(),
    )


def _mock_judgment(case_id: str, case_title: str, score_A: float, score_B: float) -> JudgmentResult:
    """Used when the GPU model is not available (dev / CI environment)."""
    winning_side = "A" if score_A >= score_B else ("B" if score_B > score_A else "Draw")
    return JudgmentResult(
        case_id=case_id,
        case_title=case_title,
        status="complete",
        arguments_summary=(
            "Lawyer A presented arguments focused on breach of duty and damages. "
            "Lawyer B contested liability and cited absence of dishonest intent."
        ),
        evaluation=[
            ArgumentEvaluation(
                argument="Advance payment accepted without delivery capacity",
                side="A", weight="High",
                reasoning="Directly evidences breach of contractual obligation."
            ),
            ArgumentEvaluation(
                argument="Delay alone does not constitute cheating",
                side="B", weight="Medium",
                reasoning="Legally sound but does not address fund diversion allegations."
            ),
        ],
        final_verdict=(
            f"Based on cumulative evaluation, the weight of arguments favours "
            f"Lawyer {'A (Prosecutor)' if winning_side == 'A' else 'B (Defendant)'}. "
            "The court rules accordingly."
        ),
        winning_side=winning_side,
        score_A=score_A,
        score_B=score_B,
        assumptions_check="No external assumptions were made.",
        raw_output="[Mock judgment – model not loaded]",
        completed_at=datetime.utcnow(),
    )


# ── Public API ────────────────────────────────────────────────────────────────
async def generate_judgment(
    case_id: str,
    case_title: str,
    case_facts: str,
    args_A: list[str],
    args_B: list[str],
    score_A: float = 0.0,
    score_B: float = 0.0,
) -> JudgmentResult:
    """
    Async entry point for judgment generation.
    Runs model inference in a thread pool to avoid blocking the event loop.
    """
    loop = asyncio.get_event_loop()

    def _infer() -> JudgmentResult:
        _load_judge()

        if _model is None:
            logger.warning("Judge model not loaded – returning mock judgment.")
            return _mock_judgment(case_id, case_title, score_A, score_B)

        try:
            import torch
            prompt = _build_prompt(case_title, case_facts, args_A, args_B)
            inputs = _tokenizer(prompt, return_tensors="pt").to(_model.device)

            with torch.no_grad():
                output = _model.generate(
                    **inputs,
                    max_new_tokens=settings.MAX_NEW_TOKENS,
                    temperature=settings.JUDGE_TEMPERATURE,
                    do_sample=False,
                    repetition_penalty=1.3,
                    pad_token_id=_tokenizer.eos_token_id,
                )

            raw = _tokenizer.decode(output[0], skip_special_tokens=True)
            # Strip the prompt prefix from decoded output
            if "Arguments Summary:" in raw:
                raw = raw[raw.index("Arguments Summary:"):]

            return _parse_verdict(raw, case_id, case_title, score_A, score_B)

        except Exception as exc:
            logger.error("Judge inference error: %s", exc)
            return JudgmentResult(
                case_id=case_id,
                case_title=case_title,
                status="error",
                error=str(exc),
                score_A=score_A,
                score_B=score_B,
            )

    return await loop.run_in_executor(None, _infer)
