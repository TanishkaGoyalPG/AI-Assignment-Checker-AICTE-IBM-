"""
analyzer.py  –  Plagiarism Intelligence Engine
=================================================
Orchestrates local similarity metrics + IBM Watsonx.ai Granite analysis.
"""

import json
import re
import textwrap
from datetime import datetime

from config import (
    IBM_API_KEY, IBM_WATSONX_URL, IBM_PROJECT_ID, GRANITE_MODEL_ID,
    ANALYSIS_INSTRUCTIONS, MODEL_PARAMS, RISK_THRESHOLDS,
    INSTITUTION_NAME, INSTITUTION_POLICY,
)
from utils.similarity import (
    exact_overlap_score,
    cosine_similarity,
    suspicious_passages,
    style_shift_score,
    ai_likelihood_heuristic,
)

try:
    from ibm_watsonx_ai import APIClient, Credentials
    from ibm_watsonx_ai.foundation_models import ModelInference
    _WATSONX_AVAILABLE = True
except ImportError:
    _WATSONX_AVAILABLE = False


# ── risk label helper ─────────────────────────────────────────────────────────

def risk_label(score_pct: float) -> str:
    for label, (lo, hi) in RISK_THRESHOLDS.items():
        if lo <= score_pct < hi:
            return label.upper()
    return "CRITICAL"


def risk_color(label: str) -> str:
    return {
        "LOW":      "#22c55e",
        "MODERATE": "#f59e0b",
        "HIGH":     "#ef4444",
        "CRITICAL": "#7c2d12",
    }.get(label, "#6b7280")


# ── Watsonx.ai client factory ─────────────────────────────────────────────────

def _build_model() -> "ModelInference | None":
    if not _WATSONX_AVAILABLE:
        return None
    if not all([IBM_API_KEY, IBM_WATSONX_URL, IBM_PROJECT_ID]):
        return None
    try:
        creds = Credentials(url=IBM_WATSONX_URL, api_key=IBM_API_KEY)
        client = APIClient(credentials=creds, project_id=IBM_PROJECT_ID)
        return ModelInference(
            model_id=GRANITE_MODEL_ID,
            api_client=client,
            params=MODEL_PARAMS,
        )
    except Exception as exc:
        print(f"[Watsonx] Failed to build model: {exc}")
        return None


# ── prompt builder ────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """
You are an expert academic integrity analyst powered by IBM Granite.
You will receive a student assignment and pre-computed similarity metrics.
Your task is to produce a plagiarism intelligence report as a JSON object.

Return ONLY valid JSON matching this schema (no markdown fences, no extra text):
{{
  "overall_risk_score": <integer 0-100>,
  "risk_level": "<LOW|MODERATE|HIGH|CRITICAL>",
  "plagiarism_type": "<NONE|EXACT_COPY|PARAPHRASE|MOSAIC|AI_GENERATED|MIXED>",
  "executive_summary": "<2-3 sentence summary for faculty>",
  "suspicious_passages": [
    {{
      "text": "<quoted suspicious passage>",
      "reason": "<why it is suspicious>",
      "type": "<VERBATIM|PARAPHRASE|AI_GENERATED|STYLE_SHIFT>"
    }}
  ],
  "ai_generation_assessment": {{
    "likelihood": "<LOW|MODERATE|HIGH>",
    "evidence": "<brief explanation>"
  }},
  "style_shift_assessment": {{
    "detected": <true|false>,
    "explanation": "<brief explanation>"
  }},
  "matched_source_summary": "<description of likely source or pattern>",
  "recommendations": ["<action 1>", "<action 2>", "<action 3>"],
  "corrective_actions_for_student": ["<action 1>", "<action 2>"],
  "confidence_level": "<LOW|MEDIUM|HIGH>"
}}
""".strip()


def _build_prompt(submitted_text: str, reference_texts: list[str],
                  baseline_texts: list[str], metrics: dict) -> str:
    instructions = ANALYSIS_INSTRUCTIONS.format(
        institution=INSTITUTION_NAME,
        policy=INSTITUTION_POLICY,
    )

    ref_block = ""
    if reference_texts:
        combined_ref = "\n\n---\n\n".join(reference_texts[:3])  # max 3 refs
        ref_block = f"""
REFERENCE / PRIOR SUBMISSIONS (for comparison):
<reference>
{combined_ref[:4000]}
</reference>
""".strip()

    metric_block = f"""
PRE-COMPUTED SIMILARITY METRICS:
- Exact n-gram overlap (vs references): {metrics['exact_overlap_pct']}%
- Cosine similarity (vs references):    {metrics['cosine_sim_pct']}%
- AI-likelihood heuristic score:        {metrics['ai_heuristic_pct']}%
- Style similarity to student baseline: {metrics['style_sim_pct']}%
- Suspicious sentence count:            {metrics['suspicious_count']}
""".strip()

    submitted_block = f"""
SUBMITTED ASSIGNMENT:
<submission>
{submitted_text[:6000]}
</submission>
""".strip()

    return "\n\n".join([
        _SYSTEM_PROMPT,
        instructions,
        metric_block,
        ref_block if ref_block else "",
        submitted_block,
        "Produce the JSON report now:",
    ])


# ── JSON extraction ───────────────────────────────────────────────────────────

def _extract_json(raw: str) -> dict:
    raw = raw.strip()
    # strip markdown fences if model wrapped output
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"\s*```$", "", raw, flags=re.MULTILINE)
    # find first { … } block
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}


# ── fallback report (no Watsonx / demo mode) ─────────────────────────────────

def _fallback_report(metrics: dict, submitted_text: str) -> dict:
    """
    Returns a demo / offline report when IBM credentials are not configured.
    Useful for development and UI testing.
    """
    score = metrics["combined_score_pct"]
    level = risk_label(score)
    return {
        "overall_risk_score": score,
        "risk_level": level,
        "plagiarism_type": "MIXED" if score > 50 else "NONE",
        "executive_summary": (
            f"[DEMO MODE – Watsonx.ai not configured] "
            f"The pre-computed similarity score is {score}%, "
            f"placing this submission in the {level} risk category. "
            "Configure IBM_API_KEY, IBM_PROJECT_ID and IBM_WATSONX_URL in "
            "your .env file to enable full AI analysis."
        ),
        "suspicious_passages": [
            {
                "text": p["sentence"][:200],
                "reason": f"Shares {p['overlap_count']} matching n-grams with reference material.",
                "type": "VERBATIM",
            }
            for p in metrics.get("suspicious_passage_list", [])[:5]
        ],
        "ai_generation_assessment": {
            "likelihood": "HIGH" if metrics["ai_heuristic_pct"] > 60 else
                          "MODERATE" if metrics["ai_heuristic_pct"] > 35 else "LOW",
            "evidence": f"Heuristic AI-likelihood score: {metrics['ai_heuristic_pct']}%",
        },
        "style_shift_assessment": {
            "detected": metrics["style_sim_pct"] < 65,
            "explanation": f"Style similarity to baseline: {metrics['style_sim_pct']}%",
        },
        "matched_source_summary": "Full source matching requires Watsonx.ai integration.",
        "recommendations": [
            "Configure IBM Watsonx.ai credentials for full AI-powered analysis.",
            "Review flagged passages manually.",
            "Interview the student if similarity score is high.",
        ],
        "corrective_actions_for_student": [
            "Ensure all sources are properly cited.",
            "Rewrite paraphrased sections in your own words.",
        ],
        "confidence_level": "LOW",
        "demo_mode": True,
    }


# ── main public function ──────────────────────────────────────────────────────

def analyze_submission(
    submitted_text: str,
    reference_texts: list[str] | None = None,
    baseline_texts: list[str] | None = None,
    assignment_title: str = "Unknown Assignment",
    student_name: str = "Unknown Student",
    course: str = "Unknown Course",
) -> dict:
    """
    Full plagiarism analysis pipeline.

    Parameters
    ----------
    submitted_text   : The text of the submitted assignment.
    reference_texts  : Optional list of reference/comparison texts
                       (other students' work, known sources).
    baseline_texts   : Optional list of the same student's past submissions
                       (used for style-shift detection).

    Returns
    -------
    A dict containing the full plagiarism intelligence report.
    """
    reference_texts = reference_texts or []
    baseline_texts  = baseline_texts  or []

    # ── 1. local metrics ────────────────────────────────────────────────────
    combined_ref = " ".join(reference_texts) if reference_texts else ""

    exact_overlap   = exact_overlap_score(submitted_text, combined_ref) if combined_ref else 0.0
    cosine_sim      = cosine_similarity(submitted_text, combined_ref)    if combined_ref else 0.0
    ai_heuristic    = ai_likelihood_heuristic(submitted_text)
    style_sim       = style_shift_score(baseline_texts, submitted_text)
    sus_passages    = suspicious_passages(submitted_text, combined_ref)  if combined_ref else []

    # combined plagiarism score (weighted)
    combined_score = (
        exact_overlap  * 0.40 +
        cosine_sim     * 0.35 +
        ai_heuristic   * 0.25
    )

    metrics = {
        "exact_overlap_pct":       round(exact_overlap  * 100, 1),
        "cosine_sim_pct":          round(cosine_sim      * 100, 1),
        "ai_heuristic_pct":        round(ai_heuristic    * 100, 1),
        "style_sim_pct":           round(style_sim        * 100, 1),
        "combined_score_pct":      round(combined_score  * 100, 1),
        "suspicious_count":        len(sus_passages),
        "suspicious_passage_list": sus_passages,
    }

    # ── 2. Watsonx.ai deep analysis ─────────────────────────────────────────
    model = _build_model()
    ai_report = {}

    if model:
        prompt = _build_prompt(submitted_text, reference_texts, baseline_texts, metrics)
        try:
            response = model.generate_text(prompt=prompt)
            ai_report = _extract_json(response)
        except Exception as exc:
            print(f"[Watsonx] Generation error: {exc}")
            ai_report = {}

    if not ai_report:
        ai_report = _fallback_report(metrics, submitted_text)

    # ── 3. assemble final report ─────────────────────────────────────────────
    final_score = ai_report.get("overall_risk_score", metrics["combined_score_pct"])
    final_level = ai_report.get("risk_level", risk_label(final_score))

    report = {
        # meta
        "assignment_title": assignment_title,
        "student_name":     student_name,
        "course":           course,
        "analyzed_at":      datetime.utcnow().isoformat(),
        "model_used":       GRANITE_MODEL_ID if model else "offline-heuristic",
        # scores
        "metrics":          metrics,
        "overall_risk_score": final_score,
        "risk_level":         final_level,
        "risk_color":         risk_color(final_level),
        # AI analysis
        **{k: v for k, v in ai_report.items()
           if k not in ("overall_risk_score", "risk_level")},
        # decision (to be filled by faculty)
        "faculty_decision": None,
        "faculty_notes":    None,
        "faculty_name":     None,
        "decided_at":       None,
    }
    return report
