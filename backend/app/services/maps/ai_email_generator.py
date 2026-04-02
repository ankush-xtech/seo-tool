"""
AI Email Generator — supports multiple AI providers.

Priority order (first key found in .env wins):
  1. Anthropic (Claude)  — ANTHROPIC_API_KEY  — paid, best quality
  2. Groq (Llama)        — GROQ_API_KEY        — FREE, very good quality
  3. None                — falls back to HTML template in outreach_email.py

Cost guide:
  Claude Haiku  : ~$0.001 per email
  Groq Llama    : FREE (14,400 requests/day free tier)

.env setup:
  # Option A — Claude (paid)
  ANTHROPIC_API_KEY=sk-ant-api03-xxx

  # Option B — Groq (free)
  GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxx
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ── Shared prompt builder (same prompt for all providers) ─────────────────────

def _build_prompt(
    business_name: str,
    website: str,
    city: str,
    category: str,
    seo_score: int,
    problems: list[str],
    from_name: str,
    rating: Optional[float],
    reviews_count: Optional[int],
) -> str:
    top_problems = problems[:5]

    # Build problems as HTML list items (same red style as template)
    problems_html_items = "".join(
        f'<li style="margin-bottom:6px;color:#c0392b;">{p}</li>'
        for p in top_problems
    )

    # Reputation context for AI to reference naturally
    reputation_note = ""
    if rating and reviews_count:
        reputation_note = (
            f"Note: they have {reviews_count} Google reviews with a "
            f"{rating:.1f}-star rating — mention this to show you did your research."
        )
    elif rating:
        reputation_note = f"Note: they have a {rating:.1f}-star Google rating."

    # Urgency phrase based on score
    if seo_score == 0:
        urgency = "critical issues"
    elif seo_score < 30:
        urgency = "major issues"
    elif seo_score < 50:
        urgency = "several issues"
    else:
        urgency = "a few areas for improvement"

    # Build the fixed company info from settings
    from app.core.config import settings as _s

    problems_html_items = "".join(
        f'<li style="margin-bottom:8px;color:#2c3e50;">{p}</li>'
        for p in top_problems
    )

    # Fixed HTML shell — AI only writes the ONE personalised paragraph
    html_shell = f"""<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#2c3e50;line-height:1.6;">

    <p>Hi there,</p>

    <p>We hope you're doing well.</p>

    <p>We are reaching out from <strong>{_s.COMPANY_NAME}</strong>, an {_s.COMPANY_TYPE}
    based in {_s.COMPANY_COUNTRY} specializing in {_s.COMPANY_SPECIALIZATION}.
    We recently conducted a basic audit of your website
    <a href="http://{website}" style="color:#2980b9;">{website}</a>
    and identified several important SEO-related issues that may be impacting
    your online visibility and performance, including:</p>

    <div style="background:#fdf2f2;border-left:4px solid #e74c3c;padding:14px 18px;margin:20px 0;border-radius:4px;">
        <ul style="margin:0;padding-left:20px;">
            {problems_html_items}
        </ul>
    </div>

    <p><<<AI_INSIGHT: Write 2 sentences ONLY. Explain specifically why 1-2 of the above problems
    are especially harmful for a '{category}' business in {city}.
    Be concrete — e.g. mention real impact like losing emergency calls, patients not finding them, etc.
    Do NOT repeat the bullet points. Do NOT add HTML tags.>>></p>

    <p>There is absolutely no obligation — our goal is simply to provide valuable
    insights that can help you improve your website's performance.</p>

    <p>If you'd like us to share your personalized SEO audit report, just reply to
    this email, and we'll send it over.</p>

    <p>Looking forward to your response.</p>

    <p style="margin-top:28px;">
        Best regards,<br><br>
        <strong>{_s.COMPANY_NAME}</strong><br>
        📧 <a href="mailto:{_s.COMPANY_EMAIL}" style="color:#2980b9;">{_s.COMPANY_EMAIL}</a><br>
        🌐 <a href="http://{_s.COMPANY_WEBSITE}" style="color:#2980b9;">{_s.COMPANY_WEBSITE}</a>
    </p>

    <hr style="border:none;border-top:1px solid #ecf0f1;margin:28px 0;">
    <p style="font-size:11px;color:#95a5a6;">
        You are receiving this because your business was found on Google Maps.
        If you do not wish to receive further emails, simply reply with "unsubscribe".
    </p>

</div>"""

    return f"""You are an SEO expert at {_s.COMPANY_NAME}.

Business details:
- Name: {business_name}
- Category: {category or 'Local Business'}
- City: {city or 'Australia'}
- Website: {website}
- SEO Score: {seo_score}/100 ({urgency})
{reputation_note}

SEO problems found:
{chr(10).join(f"  - {p}" for p in top_problems)}

TASK: Fill in ONLY the <<<AI_INSIGHT>>> placeholder in the HTML below.
Rules:
- Do NOT change any other part of the HTML
- Replace <<<AI_INSIGHT...>>> with 2 plain-text sentences (no HTML tags inside)
- Be specific to the business category and the actual problems listed
- Friendly, helpful tone — not salesy

HTML TO FILL IN:
{html_shell}

Return ONLY valid JSON — no markdown, no extra text:
{{"subject": "{_s.OUTREACH_SUBJECT}", "body_html": "THE COMPLETE HTML WITH PLACEHOLDER REPLACED"}}"""


def _parse_json_response(raw: str) -> dict:
    """Strip markdown fences and parse JSON from AI response."""
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(
            line for line in lines
            if not line.startswith("```")
        ).strip()
    result = json.loads(raw)
    if "subject" not in result or "body_html" not in result:
        raise ValueError("AI response missing 'subject' or 'body_html' keys")
    return result


# ── Provider: Anthropic (Claude) ──────────────────────────────────────────────

def _generate_with_anthropic(prompt: str, api_key: str, model: str) -> dict:
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic package not installed. Run: pip install anthropic")

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text
    result = _parse_json_response(raw)
    logger.info(
        f"[Claude] email generated "
        f"(model={model}, in={response.usage.input_tokens}, out={response.usage.output_tokens})"
    )
    return result


# ── Provider: Groq (Llama) — FREE ─────────────────────────────────────────────

def _generate_with_groq(prompt: str, api_key: str, model: str) -> dict:
    try:
        from groq import Groq
    except ImportError:
        raise RuntimeError("groq package not installed. Run: pip install groq")

    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.choices[0].message.content
    result = _parse_json_response(raw)
    logger.info("Groq result==========>>>>: %s", result)
    logger.info(
        f"[Groq/{model}] email generated "
        f"(in={response.usage.prompt_tokens}, out={response.usage.completion_tokens})"
    )
    return result


# ── Public function ───────────────────────────────────────────────────────────

def generate_ai_email(
    business_name: str,
    website: str,
    city: str,
    category: str,
    seo_score: int,
    problems: list[str],
    from_name: str = "SEO Agency",
    rating: Optional[float] = None,
    reviews_count: Optional[int] = None,
) -> Optional[dict]:
    """
    Generate a personalised outreach email using the best available AI provider.

    Priority: Anthropic → Groq → None (caller falls back to template)

    Returns {"subject": str, "body_html": str} on success, raises on failure.
    """
    from app.core.config import settings

    prompt = _build_prompt(
        business_name=business_name,
        website=website,
        city=city,
        category=category,
        seo_score=seo_score,
        problems=problems,
        from_name=from_name,
        rating=rating,
        reviews_count=reviews_count,
    )

    # ── 1. Try Anthropic first ────────────────────────────────────────────
    if settings.ANTHROPIC_API_KEY:
        logger.info(f"Generating email with Anthropic for {business_name}")
       

        return _generate_with_anthropic(
            prompt=prompt,
            api_key=settings.ANTHROPIC_API_KEY,
            model=settings.AI_EMAIL_MODEL,
        )

    # ── 2. Try Groq second (free) ─────────────────────────────────────────
    if settings.GROQ_API_KEY:
        logger.info(f"Generating email with Groq for {business_name}")
        return _generate_with_groq(
            prompt=prompt,
            api_key=settings.GROQ_API_KEY,
            model=settings.GROQ_MODEL,
        )

    # ── 3. No AI provider configured ─────────────────────────────────────
    logger.info("No AI provider configured — returning None (template fallback)")
    return None
