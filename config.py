"""
config.py  –  Plagiarism Intelligence System
=============================================
Central place for ALL tunable settings.

✏️  EDIT THIS FILE to customise academic policies, risk thresholds,
    language tone, and institution-specific rules without touching
    any other source file.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# IBM Watsonx.ai credentials (loaded from .env)
# ─────────────────────────────────────────────────────────────────────────────
IBM_API_KEY      = os.getenv("IBM_API_KEY", "")
IBM_WATSONX_URL  = os.getenv("IBM_WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
IBM_PROJECT_ID   = os.getenv("IBM_PROJECT_ID", "")
GRANITE_MODEL_ID = os.getenv("GRANITE_MODEL_ID", "ibm/granite-13b-instruct-v2")

FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
MAX_UPLOAD_MB    = int(os.getenv("MAX_UPLOAD_MB", "10"))

# ─────────────────────────────────────────────────────────────────────────────
# RISK THRESHOLDS  ✏️ customise per institution policy
# ─────────────────────────────────────────────────────────────────────────────
RISK_THRESHOLDS = {
    "low":      (0,  30),   # 0–29 %  → LOW   – acceptable similarity
    "moderate": (30, 55),   # 30–54 % → MODERATE – review recommended
    "high":     (55, 75),   # 55–74 % → HIGH  – strong concern
    "critical": (75, 101),  # 75 %+   → CRITICAL – likely plagiarism
}

# ─────────────────────────────────────────────────────────────────────────────
# INSTITUTION INFO  ✏️ change to your university/college details
# ─────────────────────────────────────────────────────────────────────────────
INSTITUTION_NAME   = "AICTE Academic Integrity Office"
INSTITUTION_POLICY = "Academic Integrity Policy v3.2 (2024)"
CONTACT_EMAIL      = "integrity@institution.edu"

# ─────────────────────────────────────────────────────────────────────────────
# ANALYSIS_INSTRUCTIONS  ✏️  PRIMARY CUSTOMISATION BLOCK
#
# This multi-line string is injected verbatim into every Watsonx.ai prompt.
# Adjust tone, depth, language, domain focus, or add institution-specific
# rules here.  Keep instructions clear and concise for best model performance.
# ─────────────────────────────────────────────────────────────────────────────
ANALYSIS_INSTRUCTIONS = """
You are an academic integrity AI analyst for {institution}.
Your role is to evaluate student assignment submissions for potential plagiarism,
AI-generated content, and abnormal writing-style shifts.

ACADEMIC POLICY CONTEXT:
- Policy: {policy}
- Exact-copy threshold triggering concern: ≥ 15 % verbatim overlap
- Paraphrase/mosaic threshold triggering concern: ≥ 30 % restructured overlap
- AI-generation suspicion threshold: ≥ 40 % AI-likelihood score
- Style-shift concern: cosine similarity to baseline < 0.65

ANALYSIS GUIDELINES:
1. Be objective, evidence-based, and avoid assumptions about intent.
2. Quote exact suspicious passages using double-angle brackets «like this».
3. For every flagged passage, briefly explain WHY it is suspicious
   (verbatim copy / paraphrase / unusual vocabulary / AI phrasing, etc.).
4. Distinguish between a well-cited quotation and uncited plagiarism.
5. If the submission appears original, state this clearly and positively.
6. Use formal academic language; avoid accusatory or definitive language
   — your role is to flag, not to convict.
7. Always suggest specific corrective actions the student could take.
8. Consider the assignment context and academic level when assessing severity.

OUTPUT FORMAT:
Return a valid JSON object matching exactly the schema described in the system prompt.
Do not add any text outside the JSON object.
""".strip()

# ─────────────────────────────────────────────────────────────────────────────
# WATSONX MODEL PARAMETERS  ✏️ adjust for speed vs quality trade-off
# ─────────────────────────────────────────────────────────────────────────────
MODEL_PARAMS = {
    "decoding_method": "greedy",
    "max_new_tokens":  2000,
    "min_new_tokens":  100,
    "temperature":     0.1,    # low = more deterministic / factual
    "repetition_penalty": 1.1,
}

# ─────────────────────────────────────────────────────────────────────────────
# SUPPORTED COURSES  ✏️ add / remove courses as needed
# ─────────────────────────────────────────────────────────────────────────────
SUPPORTED_COURSES = [
    "Computer Science",
    "Data Science & AI",
    "Electrical Engineering",
    "Mechanical Engineering",
    "Business Administration",
    "Environmental Science",
    "Mathematics",
    "Physics",
    "Chemistry",
    "Other",
]

# ─────────────────────────────────────────────────────────────────────────────
# FILE HANDLING
# ─────────────────────────────────────────────────────────────────────────────
ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}
UPLOAD_FOLDER      = "uploads"
REPORTS_FOLDER     = "reports"
