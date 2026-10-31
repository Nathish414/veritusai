import json
import logging
from typing import Any, Dict, List, Tuple

from services.gemini_service import (
    generate_ai_response,
    GeminiConfigError,
    GeminiAPIError,
)
from services.exa_service import (
    search_web,
    ExaConfigError,
    ExaAPIError,
)

logger = logging.getLogger(__name__)

# Safety limits to avoid excessive API usage
MAX_CLAIMS = 10
MAX_EVIDENCE_PER_CLAIM = 3
MAX_TOTAL_EXA_CALLS = 30


class FactCheckError(Exception):
    """Raised when the fact-check pipeline fails."""
    pass


def _extract_claims(article_text: str) -> List[str]:
    """
    Use Gemini to extract individual factual claims from article text.
    Returns a list of claim strings, capped at MAX_CLAIMS.
    """
    prompt = (
        "You are a fact-checking assistant. Extract individual factual claims "
        "from the following article text. Each claim must be a single, discrete, "
        "verifiable factual statement. Do not include opinions, questions, "
        "hedged statements, or predictions.\n\n"
        "Return ONLY a JSON array of strings, with no markdown formatting, "
        "no code blocks, and no additional text.\n"
        'Example: ["The Eiffel Tower is in Paris.", "Water boils at 100 degrees Celsius."]\n\n'
        f"Article text:\n{article_text}"
    )

    raw = generate_ai_response(prompt)
    claims = _parse_gemini_json_array(raw)

    # Filter and sanitize
    cleaned = []
    for c in claims:
        if isinstance(c, str) and c.strip():
            cleaned.append(c.strip())
    return cleaned[:MAX_CLAIMS]


def _parse_gemini_json_array(raw_text: str) -> List[Any]:
    """Safely parse a JSON array from Gemini response text."""
    text = raw_text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()

    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("claims"), list):
            return data["claims"]
        return []
    except (json.JSONDecodeError, ValueError):
        # Attempt to locate a JSON array within the text
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(text[start:end + 1])
                if isinstance(data, list):
                    return data
            except (json.JSONDecodeError, ValueError):
                pass
        return []


def _parse_gemini_json_object(raw_text: str) -> Dict[str, Any]:
    """Safely parse a JSON object from Gemini response text."""
    text = raw_text.strip()

    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, ValueError):
        pass

    # Attempt to locate a JSON object within the text
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            data = json.loads(text[start:end + 1])
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, ValueError):
            pass



def _search_evidence(claim_text: str, exa_calls_used: int) -> Tuple[List[Dict[str, Any]], int]:
    if exa_calls_used >= MAX_TOTAL_EXA_CALLS:
        logger.warning("Maximum total Exa API calls reached; skipping further searches.")
        return [], exa_calls_used

    try:
        results = search_web(claim_text)
        exa_calls_used += 1
    except ExaConfigError:
        logger.error("Exa API key not configured.")
        return [], exa_calls_used
    except ExaAPIError as err:
        logger.warning(f"Exa API error for claim '{claim_text[:60]}...': {err}")
        return [], exa_calls_used
    except Exception as err:
        logger.warning(f"Unexpected Exa error for claim: {type(err).__name__}")
        return [], exa_calls_used

    limited = results[:MAX_EVIDENCE_PER_CLAIM] if isinstance(results, list) else []
    return limited, exa_calls_used


def _evaluate_claim(claim_text: str, evidence_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    if evidence_list:
        evidence_context = "Retrieved evidence (assess relevance, reliability, and publication date of each):\n"
        for i, ev in enumerate(evidence_list, 1):
            evidence_context += (
                f"\nSource {i}:\n"
                f"  Title: {ev.get('title') or 'N/A'}\n"
                f"  URL: {ev.get('url') or 'N/A'}\n"
                f"  Published date: {ev.get('published_date') or 'N/A'}\n"
                f"  Snippet: {ev.get('text') or 'N/A'}\n"
            )
    else:
        evidence_context = "No external evidence was retrieved for this claim.\n"

    prompt = (
        "You are a rigorous fact-checker. Evaluate the following claim using ONLY "
        "the provided retrieved evidence. Do NOT use your own training knowledge "
        "as evidence.\n\n"
        f"Claim: {claim_text}\n\n"
        f"{evidence_context}\n"
        "Instructions:\n"
        "1. Assess each source's relevance to the claim, its reliability, and its "
        "   publication date (more recent sources are generally preferable).\n"
        "2. Determine whether each source directly supports, directly contradicts, "
        "   or merely provides neutral context for the claim.\n"
        "3. Assign exactly one verdict: 'supported', 'contradicted', or 'unverified'.\n"
        "   - Use 'supported' only if reliable, relevant evidence directly supports the claim.\n"
        "   - Use 'contradicted' only if reliable, relevant evidence directly contradicts the claim.\n"
        "   - Use 'unverified' if evidence is insufficient, conflicting, unreliable, or absent.\n"
        "4. Assign a confidence score from 0.00 to 1.00 reflecting the quality, "
        "   relevance, and consistency of the retrieved evidence — NOT your internal certainty.\n"
        "   - Higher confidence when multiple reliable sources agree.\n"
        "   - Lower confidence when evidence is sparse, conflicting, or from weak sources.\n"
        "5. Provide a brief explanation citing the evidence.\n\n"
        "Return ONLY a JSON object, with no markdown formatting, no code blocks, "
        "and no additional text.\n"
        'Example:\n'
        '{\n'
        '  "verdict": "supported",\n'
        '  "confidence": 0.85,\n'
        '  "explanation": "Two recent, reliable sources directly support the claim.",\n'
        '  "evidence_stances": ["supports", "supports"]\n'
        '}\n'
        "Where evidence_stances aligns with the evidence list order; each entry is "
        "'supports', 'contradicts', or 'context'."
    )

    raw = generate_ai_response(prompt)
    result = _parse_gemini_json_object(raw)

    verdict = result.get("verdict", "unverified")
    if verdict not in ("supported", "contradicted", "unverified"):
        verdict = "unverified"

    confidence = result.get("confidence", 0.50)
    try:
        confidence = float(confidence)
        confidence = max(0.0, min(1.0, confidence))
    except (TypeError, ValueError):
        confidence = 0.50

    explanation = result.get("explanation", "No explanation provided.")
    if not isinstance(explanation, str):
        explanation = str(explanation)

    evidence_stances = result.get("evidence_stances", [])
    if not isinstance(evidence_stances, list):
        evidence_stances = []

    while len(evidence_stances) < len(evidence_list):
        evidence_stances.append("context")
    evidence_stances = evidence_stances[:len(evidence_list)]

    valid_stances = {"supports", "contradicts", "context"}
    evidence_stances = [s if s in valid_stances else "context" for s in evidence_stances]

    return {
        "verdict": verdict,
        "confidence": confidence,
        "explanation": explanation,
        "evidence_stances": evidence_stances,
    }


def _generate_summary(claims: List[Dict[str, Any]], stats: Dict[str, int]) -> str:
    total = stats.get("total", 0)
    if total == 0:
        return "No claims were evaluated."

    parts = [
        f"Evaluated {total} factual claim(s): "
        f"{stats.get('supported', 0)} supported, "
        f"{stats.get('contradicted', 0)} contradicted, "
        f"{stats.get('unverified', 0)} unverified."
    ]

    supported_claims = [c for c in claims if c.get("verdict") == "supported"]
    contradicted_claims = [c for c in claims if c.get("verdict") == "contradicted"]

    if supported_claims:
        samples = "; ".join(c.get("claim_text", "") for c in supported_claims[:3])
        parts.append(f"Claims supported by evidence: {samples}")

    if contradicted_claims:
        samples = "; ".join(c.get("claim_text", "") for c in contradicted_claims[:3])
        parts.append(f"Claims contradicted by evidence: {samples}")

    return " ".join(parts)


def verify_article(article_text: str) -> Dict[str, Any]:
    """
    Run the full fact-check pipeline on article text.

    Pipeline:
      1. Extract claims via Gemini (max MAX_CLAIMS).
      2. For each claim, search evidence via Exa (max MAX_EVIDENCE_PER_CLAIM results).
      3. Evaluate each claim against evidence via Gemini.
      4. Assign verdict (supported/contradicted/unverified), confidence, explanation.

    Returns:
      dict with keys: claims, summary, stats

    Raises:
      ValueError: if article_text is invalid.
      GeminiConfigError / ExaConfigError: if API keys missing.
      FactCheckError: for pipeline failures.
    """
    if not article_text or not isinstance(article_text, str) or not article_text.strip():
        raise ValueError("Article text must be a non-empty string.")

    article_text = article_text.strip()

    # Step 1: Extract claims
    try:
        claims = _extract_claims(article_text)
    except GeminiConfigError:
        raise
    except GeminiAPIError as err:
        raise FactCheckError(f"Failed to extract claims: {err}") from err
    except Exception as err:
        raise FactCheckError(f"Unexpected error extracting claims: {type(err).__name__}") from err

    if not claims:
        return {
            "claims": [],
            "summary": "No factual claims could be extracted from the article.",
            "stats": {"total": 0, "supported": 0, "contradicted": 0, "unverified": 0},
        }

    # Steps 2 & 3: Search evidence and evaluate each claim
    processed_claims = []
    stats = {"supported": 0, "contradicted": 0, "unverified": 0}
    exa_calls_used = 0

    for claim_text in claims:
        evidence_list, exa_calls_used = _search_evidence(claim_text, exa_calls_used)

        try:
            evaluation = _evaluate_claim(claim_text, evidence_list)
        except GeminiConfigError:
            raise
        except GeminiAPIError as err:
            logger.warning(f"Gemini evaluation failed for claim: {err}")
            evaluation = {
                "verdict": "unverified",
                "confidence": 0.00,
                "explanation": "Evaluation failed due to AI service error.",
                "evidence_stances": ["context"] * len(evidence_list),
            }
        except Exception as err:
            logger.warning(f"Unexpected error evaluating claim: {type(err).__name__}")
            evaluation = {
                "verdict": "unverified",
                "confidence": 0.00,
                "explanation": "Evaluation failed due to an unexpected error.",
                "evidence_stances": ["context"] * len(evidence_list),
            }

        verdict = evaluation["verdict"]
        stats[verdict] = stats.get(verdict, 0) + 1

        evidence_entries = []
        for i, ev in enumerate(evidence_list):
            stance = (
                evaluation["evidence_stances"][i]
                if i < len(evaluation["evidence_stances"])
                else "context"
            )
            evidence_entries.append({
                "source_title": ev.get("title", "") or "",
                "source_url": ev.get("url", "") or "",
                "evidence_snippet": ev.get("text", "") or "",
                "evidence_stance": stance,
                "published_date": ev.get("published_date"),
            })

        processed_claims.append({
            "claim_text": claim_text,
            "verdict": verdict,
            "confidence": evaluation["confidence"],
            "explanation": evaluation["explanation"],
            "evidence": evidence_entries,
        })

    # Step 4: Generate summary
    total = len(processed_claims)
    summary = _generate_summary(processed_claims, {
        "total": total,
        "supported": stats["supported"],
        "contradicted": stats["contradicted"],
        "unverified": stats["unverified"],
    })

    return {
        "claims": processed_claims,
        "summary": summary,
        "stats": {
            "total": total,
            "supported": stats["supported"],
            "contradicted": stats["contradicted"],
            "unverified": stats["unverified"],
        },
    }
    return {}