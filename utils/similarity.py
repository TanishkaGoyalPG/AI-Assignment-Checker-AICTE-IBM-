"""
utils/similarity.py
Local (offline) similarity metrics used BEFORE the Watsonx.ai call
so the prompt already contains quantitative evidence.
"""

import re
import math
import string
from collections import Counter

try:
    import nltk
    from nltk.corpus import stopwords
    from nltk.tokenize import word_tokenize, sent_tokenize
    _NLTK = True
except ImportError:
    _NLTK = False


# ── bootstrap NLTK data on first run ─────────────────────────────────────────
def _ensure_nltk():
    if not _NLTK:
        return
    for resource in ("punkt", "stopwords", "punkt_tab"):
        try:
            nltk.data.find(f"tokenizers/{resource}")
        except LookupError:
            try:
                nltk.download(resource, quiet=True)
            except Exception:
                pass


_ensure_nltk()


# ── tokenisation helpers ──────────────────────────────────────────────────────

def _clean(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(text: str) -> list[str]:
    cleaned = _clean(text)
    if _NLTK:
        try:
            tokens = word_tokenize(cleaned)
            sw = set(stopwords.words("english"))
            return [t for t in tokens if t not in sw and len(t) > 1]
        except Exception:
            pass
    return [t for t in cleaned.split() if len(t) > 1]


def _sentences(text: str) -> list[str]:
    if _NLTK:
        try:
            return sent_tokenize(text)
        except Exception:
            pass
    return [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]


def _ngrams(tokens: list[str], n: int) -> list[tuple]:
    return [tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


def _tfidf_vector(text: str, vocab: list[str]) -> list[float]:
    tokens = _tokens(text)
    tf = Counter(tokens)
    total = max(len(tokens), 1)
    vec = [tf.get(w, 0) / total for w in vocab]
    return vec


def _cosine(v1: list[float], v2: list[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    m1  = math.sqrt(sum(a * a for a in v1))
    m2  = math.sqrt(sum(b * b for b in v2))
    if m1 == 0 or m2 == 0:
        return 0.0
    return dot / (m1 * m2)


# ── public API ────────────────────────────────────────────────────────────────

def exact_overlap_score(text_a: str, text_b: str, n: int = 5) -> float:
    """
    Return the fraction of n-grams in text_a that appear in text_b (0–1).
    Default n=5 captures verbatim 5-word sequences.
    """
    ta, tb = _tokens(text_a), _tokens(text_b)
    if not ta:
        return 0.0
    grams_a = set(_ngrams(ta, n))
    grams_b = set(_ngrams(tb, n))
    if not grams_a:
        return 0.0
    return len(grams_a & grams_b) / len(grams_a)


def cosine_similarity(text_a: str, text_b: str) -> float:
    """TF-based cosine similarity between two documents (0–1)."""
    ta, tb = _tokens(text_a), _tokens(text_b)
    vocab  = list(set(ta) | set(tb))
    if not vocab:
        return 0.0
    va = _tfidf_vector(text_a, vocab)
    vb = _tfidf_vector(text_b, vocab)
    return round(_cosine(va, vb), 4)


def suspicious_passages(submitted: str, reference: str,
                         n: int = 6, threshold: int = 3) -> list[dict]:
    """
    Find sentences in *submitted* that share ≥ threshold n-grams with
    any sentence in *reference*.  Returns a list of dicts:
      {sentence, matched_ngrams, overlap_count}
    """
    ref_tokens  = _tokens(reference)
    ref_ngrams  = set(_ngrams(ref_tokens, n))
    results     = []

    for sent in _sentences(submitted):
        st = _tokens(sent)
        sg = set(_ngrams(st, n))
        hits = sg & ref_ngrams
        if len(hits) >= threshold:
            results.append({
                "sentence":      sent.strip(),
                "overlap_count": len(hits),
                "matched_ngrams": [" ".join(g) for g in list(hits)[:5]],
            })
    return results


def style_shift_score(baseline_texts: list[str], new_text: str) -> float:
    """
    Compare new_text against a list of baseline documents (same student).
    Returns average cosine similarity (0–1); lower = more style shift.
    If no baseline is provided, returns 1.0 (no concern).
    """
    if not baseline_texts:
        return 1.0
    scores = [cosine_similarity(b, new_text) for b in baseline_texts]
    return round(sum(scores) / len(scores), 4)


def ai_likelihood_heuristic(text: str) -> float:
    """
    Lightweight heuristic for AI-generated text based on:
    - Very uniform sentence length distribution (low std-dev)
    - Low lexical diversity (type-token ratio)
    - Presence of common AI filler phrases

    Returns a float 0–1 (higher = more likely AI-generated).
    NOTE: This is a heuristic indicator only, not a definitive classifier.
    """
    sentences = _sentences(text)
    if len(sentences) < 3:
        return 0.0

    # 1. sentence length uniformity
    lengths = [len(s.split()) for s in sentences]
    mean_l  = sum(lengths) / len(lengths)
    variance = sum((l - mean_l) ** 2 for l in lengths) / len(lengths)
    std_dev  = math.sqrt(variance)
    # AI text tends to have low std-dev relative to mean
    uniformity_score = max(0.0, 1.0 - (std_dev / max(mean_l, 1)))

    # 2. lexical diversity (type-token ratio)
    all_tokens = _tokens(text)
    ttr = len(set(all_tokens)) / max(len(all_tokens), 1)
    # AI text can have moderate-to-high TTR but very structured phrasing
    diversity_penalty = max(0.0, 0.8 - ttr)  # penalise very low diversity

    # 3. AI-typical filler phrases
    ai_phrases = [
        "it is important to note", "it is worth mentioning",
        "in conclusion", "furthermore", "moreover", "additionally",
        "this essay will", "this paper aims to", "in summary",
        "to summarize", "as mentioned earlier", "as previously stated",
        "plays a crucial role", "it can be seen that",
        "significant impact", "in today's world", "in today's society",
        "it goes without saying", "needless to say",
    ]
    lower_text   = text.lower()
    phrase_hits  = sum(1 for p in ai_phrases if p in lower_text)
    phrase_score = min(1.0, phrase_hits / 5.0)

    score = (uniformity_score * 0.4 + diversity_penalty * 0.3 +
             phrase_score * 0.3)
    return round(min(score, 1.0), 4)
