"""
Preview Site Generator — generates a static single-page website for a business.

Uses the same AI provider stack as ai_email_generator.py:
  1. Groq (Llama)      — GROQ_API_KEY   — FREE
  2. Anthropic (Claude) — ANTHROPIC_API_KEY — paid, higher quality

The generated HTML is a self-contained index.html with all CSS inline,
ready to be deployed to Vercel via vercel_deployer.py.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


def _build_preview_prompt(
    business_name: str,
    website: str,
    city: str,
    category: str,
    phone: Optional[str],
    email: Optional[str],
    seo_score: int,
    problems: list[str],
) -> str:
    """Build the prompt for generating a preview website."""
    from app.core.config import settings

    problems_text = "\n".join(f"  - {p}" for p in problems[:6])

    # Map common categories to curated Unsplash photo IDs
    category_images = {
        "dentist": "photo-1629909613654-28e377c37b09", "dental": "photo-1629909613654-28e377c37b09",
        "plumber": "photo-1585704032915-c3400ca199e7", "plumbing": "photo-1585704032915-c3400ca199e7",
        "restaurant": "photo-1517248135467-4c7edcad34c4", "cafe": "photo-1554118811-1e0d58224f24",
        "lawyer": "photo-1589829545856-d10d557cf95f", "legal": "photo-1589829545856-d10d557cf95f",
        "mechanic": "photo-1619642751034-765dfdf7c58e", "auto": "photo-1619642751034-765dfdf7c58e",
        "salon": "photo-1560066984-138dadb4c035", "beauty": "photo-1560066984-138dadb4c035",
        "gym": "photo-1534438327276-14e5300c3a48", "fitness": "photo-1534438327276-14e5300c3a48",
        "real estate": "photo-1560518883-ce09059eeffa", "property": "photo-1560518883-ce09059eeffa",
        "accountant": "photo-1554224155-6726b3ff858f", "accounting": "photo-1554224155-6726b3ff858f",
        "doctor": "photo-1631217868264-e5b90bb7e133", "medical": "photo-1631217868264-e5b90bb7e133",
    }
    cat_lower = (category or "").lower()
    hero_photo = "photo-1497366216548-37526070297c"  # default professional office
    for key, photo_id in category_images.items():
        if key in cat_lower:
            hero_photo = photo_id
            break

    return f"""You are a premium web design agency. Build a HIGH-END, visually stunning website that would cost $5,000+ if built by a real agency. This must look like a real business website, NOT a template.

BUSINESS: {business_name} | {category or "Local Business"} | {city or "Australia"}
Website: {website} | Phone: {phone or "N/A"} | Email: {email or "N/A"}

OUTPUT: ONLY raw HTML starting with <!DOCTYPE html>. No explanations. No markdown fences.

TECHNICAL RULES:
- Complete index.html with ALL CSS inside <style> in <head>
- Add <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
- Add <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&display=swap" rel="stylesheet">
- Desktop-first CSS. Base = desktop. Add @media (max-width: 768px) for mobile.
- *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
- Include SEO meta tags + LocalBusiness JSON-LD schema
- Hero background image: https://images.unsplash.com/{hero_photo}?w=1600&q=80

YOU MUST USE THESE EXACT CSS PATTERNS:

:root {{
  --primary: #6366f1;
  --primary-glow: rgba(99,102,241,0.4);
  --accent: #06b6d4;
  --accent-glow: rgba(6,182,212,0.3);
  --bg-hero: #030712;
  --bg-dark: #0a0f1e;
  --bg-card: #111827;
  --bg-card-hover: #1f2937;
  --bg-light: #f9fafb;
  --text-white: #ffffff;
  --text-gray: #9ca3af;
  --text-dark: #111827;
  --gradient-primary: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #06b6d4 100%);
  --gradient-dark: linear-gradient(180deg, #030712 0%, #0a0f1e 100%);
  --border-subtle: rgba(255,255,255,0.06);
  --shadow-glow: 0 0 40px rgba(99,102,241,0.15);
  --shadow-card: 0 4px 24px rgba(0,0,0,0.3);
  --shadow-card-hover: 0 8px 40px rgba(99,102,241,0.2);
  --radius-lg: 20px;
  --radius-xl: 28px;
}}

html {{ scroll-behavior: smooth; }}
body {{ font-family: 'Inter', sans-serif; color: var(--text-white); background: var(--bg-dark); overflow-x: hidden; }}

/* ANIMATION KEYFRAMES - must include */
@keyframes fadeInUp {{ from {{ opacity: 0; transform: translateY(40px); }} to {{ opacity: 1; transform: translateY(0); }} }}
@keyframes glow {{ 0%, 100% {{ box-shadow: 0 0 20px var(--primary-glow); }} 50% {{ box-shadow: 0 0 40px var(--primary-glow), 0 0 80px rgba(99,102,241,0.1); }} }}
@keyframes float {{ 0%, 100% {{ transform: translateY(0); }} 50% {{ transform: translateY(-10px); }} }}
@keyframes shimmer {{ 0% {{ background-position: -200% center; }} 100% {{ background-position: 200% center; }} }}
@keyframes slideDown {{ from {{ opacity: 0; transform: translateY(-20px); }} to {{ opacity: 1; transform: translateY(0); }} }}

[data-reveal] {{ opacity: 0; transform: translateY(40px); transition: opacity 0.8s cubic-bezier(0.16, 1, 0.3, 1), transform 0.8s cubic-bezier(0.16, 1, 0.3, 1); }}
[data-reveal].visible {{ opacity: 1; transform: translateY(0); }}

.container {{ max-width: 1200px; margin: 0 auto; padding: 0 40px; }}

/* GRADIENT TEXT EFFECT for headings */
.gradient-text {{ background: var(--gradient-primary); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }}

/* GLOW BUTTON */
.btn-primary {{ display: inline-flex; align-items: center; gap: 8px; background: var(--gradient-primary); color: white; border: none; padding: 16px 36px; border-radius: 50px; font-size: 16px; font-weight: 600; cursor: pointer; transition: all 0.3s ease; box-shadow: 0 4px 20px var(--primary-glow); }}
.btn-primary:hover {{ transform: translateY(-2px); box-shadow: 0 8px 30px var(--primary-glow); }}
.btn-outline {{ display: inline-flex; align-items: center; gap: 8px; background: transparent; color: white; border: 2px solid rgba(255,255,255,0.2); padding: 14px 36px; border-radius: 50px; font-size: 16px; font-weight: 600; cursor: pointer; transition: all 0.3s ease; }}
.btn-outline:hover {{ border-color: var(--primary); background: rgba(99,102,241,0.1); }}

SECTIONS TO BUILD (9 total):

1. STICKY NAV (position: fixed; top: 0; width: 100%; z-index: 1000; padding: 20px 0; transition: all 0.3s):
   - Background: transparent, becomes rgba(10,15,30,0.95) + backdrop-filter: blur(20px) + border-bottom: 1px solid var(--border-subtle) on scroll (add JS scroll listener)
   - Left: business name in font-weight: 800, font-size: 20px with a small gradient accent bar (4px wide, 24px tall, border-radius 2px, var(--gradient-primary)) to the left of the name
   - Right: nav links (About, Services, Contact) in font-weight: 500; color: var(--text-gray); hover: color white. Plus a "Get Quote" .btn-primary but smaller (padding: 10px 24px, font-size: 14px)
   - Animation: slideDown on page load

2. HERO (min-height: 100vh; display: flex; align-items: center; position: relative):
   - Background: Unsplash image with overlay: linear-gradient(135deg, rgba(3,7,18,0.92) 0%, rgba(10,15,30,0.8) 50%, rgba(3,7,18,0.95) 100%)
   - Add a subtle radial gradient glow effect behind the text: a ::before pseudo-element with background: radial-gradient(ellipse at center, var(--primary-glow) 0%, transparent 70%), width: 600px, height: 600px, positioned behind the heading, filter: blur(80px)
   - Small label above heading: category name in uppercase, letter-spacing: 4px, font-size: 13px, color: var(--accent), font-weight: 600
   - Heading: font-family: 'Playfair Display', serif; font-size: 64px; font-weight: 900; line-height: 1.1; margin-bottom: 24px. The business name should use .gradient-text class
   - Subtitle: "Trusted {category} services in {city}" in font-size: 20px; color: var(--text-gray); max-width: 560px; line-height: 1.6; margin-bottom: 40px
   - Buttons row: .btn-primary "Get a Free Quote" + .btn-outline "Our Services" in a flex row gap: 16px
   - Bottom: animated scroll chevron (position: absolute; bottom: 40px; animation: float 2s ease-in-out infinite)

3. ABOUT (padding: 100px 0; background: var(--bg-dark)):
   - Section label: uppercase small text with gradient accent line (same pattern as hero label)
   - Heading: font-family: 'Playfair Display'; font-size: 42px; font-weight: 700; margin-bottom: 20px
   - Two-column flex layout: left 45% = image (border-radius: var(--radius-xl); box-shadow: var(--shadow-glow)) from Unsplash related to category, right 55% = text
   - Text: 3 sentences about the business in font-size: 17px; line-height: 1.8; color: var(--text-gray)
   - Below text: 3 small feature badges in a row (e.g., "Licensed & Insured", "10+ Years", "5-Star Rated") — each badge: background: rgba(99,102,241,0.1); border: 1px solid rgba(99,102,241,0.2); border-radius: 50px; padding: 8px 20px; font-size: 13px; color: var(--primary)

4. SERVICES (padding: 100px 0; background: var(--bg-hero)):
   - Section heading centered, 'Playfair Display', 42px, with .gradient-text
   - Subtitle: centered, color: var(--text-gray), max-width: 600px, margin: 0 auto 60px
   - Grid: display: grid; grid-template-columns: repeat(3, 1fr); gap: 28px
   - Each card: background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); padding: 40px 32px; transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1)
   - Card hover: transform: translateY(-8px); border-color: rgba(99,102,241,0.3); box-shadow: var(--shadow-card-hover); background: var(--bg-card-hover)
   - Card icon: 48px emoji in a 72px circle with background: rgba(99,102,241,0.1); border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-bottom: 24px
   - Card title: font-size: 20px; font-weight: 700; margin-bottom: 12px
   - Card desc: font-size: 15px; line-height: 1.6; color: var(--text-gray)
   - Use 6 services relevant to {category}

5. STATS BAR (padding: 80px 0; background: var(--gradient-primary); position: relative):
   - Add a subtle pattern overlay: ::before with background-image: radial-gradient(rgba(255,255,255,0.1) 1px, transparent 1px); background-size: 20px 20px
   - Grid: grid-template-columns: repeat(4, 1fr); gap: 32px; text-align: center
   - Number: font-family: 'Playfair Display'; font-size: 48px; font-weight: 900; color: white
   - Plus sign or suffix after number (e.g., "15+", "500+", "98%", "4.9")
   - Label: font-size: 15px; color: rgba(255,255,255,0.8); text-transform: uppercase; letter-spacing: 2px; margin-top: 8px

6. TESTIMONIALS (padding: 100px 0; background: var(--bg-dark)):
   - Section heading centered, 'Playfair Display', 42px
   - Grid: grid-template-columns: repeat(3, 1fr); gap: 28px
   - Each card: background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); padding: 36px; position: relative
   - Large opening quote mark: font-size: 64px; color: var(--primary); opacity: 0.3; position: absolute; top: 20px; left: 28px; font-family: Georgia, serif
   - Stars: 5 Unicode stars in color: #fbbf24; font-size: 16px; margin-bottom: 16px
   - Quote text: font-size: 16px; line-height: 1.7; color: var(--text-gray); font-style: italic; margin-bottom: 20px
   - Reviewer: font-weight: 600; font-size: 15px; color: white. Below: role/source in color: var(--text-gray); font-size: 13px
   - Use realistic names and review text relevant to {category}

7. CTA BANNER (padding: 100px 0; text-align: center; position: relative; overflow: hidden):
   - Background: var(--bg-hero) with a large radial gradient glow: radial-gradient(ellipse at center, var(--primary-glow) 0%, transparent 60%)
   - Heading: 'Playfair Display', 44px, font-weight: 700, margin-bottom: 20px
   - Subtitle: color: var(--text-gray); font-size: 18px; max-width: 500px; margin: 0 auto 40px
   - .btn-primary with animation: glow 3s ease-in-out infinite

8. CONTACT (padding: 100px 0; background: var(--bg-card)):
   - Two-column layout: left = contact info, right = form
   - Left side: heading, paragraph, then 3 contact items (phone, email, city) each with a 44px circle icon background (same gradient icon style as services) + text. Add gap: 24px between items.
   - Right side form: background: var(--bg-dark); padding: 40px; border-radius: var(--radius-xl); border: 1px solid var(--border-subtle)
   - Inputs: width: 100%; padding: 14px 18px; background: rgba(255,255,255,0.05); border: 1px solid var(--border-subtle); border-radius: 12px; color: white; font-size: 16px; font-family: 'Inter'; outline: none; transition: border-color 0.3s
   - Input focus: border-color: var(--primary)
   - Submit: .btn-primary full width, margin-top: 16px
   - Form is decorative (no action attribute)

9. FOOTER (padding: 60px 0 30px; background: var(--bg-hero); border-top: 1px solid var(--border-subtle)):
   - Top: flex row, 4 columns — Company (name + 2-line description), Quick Links (4 anchor links), Services (4 anchor links), Contact (phone, email, city)
   - Column heading: font-weight: 700; font-size: 16px; margin-bottom: 20px; color: white
   - Column links: color: var(--text-gray); font-size: 14px; line-height: 2.2; text-decoration: none. Hover: color: var(--primary)
   - Bottom bar: margin-top: 40px; padding-top: 24px; border-top: 1px solid var(--border-subtle); display: flex; justify-content: space-between; font-size: 13px; color: var(--text-gray)
   - Left: copyright. Right: "Website preview powered by {settings.COMPANY_NAME}"

MOBILE (@media max-width: 768px):
- .container {{ padding: 0 20px; }}
- nav links: display: none
- hero heading: 36px; subtitle: 16px; buttons: flex-direction: column; width: 100%
- hero min-height: 85vh
- about: flex-direction: column; image width: 100%
- services grid: grid-template-columns: 1fr
- stats grid: grid-template-columns: repeat(2, 1fr); number: 32px
- testimonials: grid-template-columns: 1fr
- contact: flex-direction: column
- footer top: flex-direction: column; gap: 32px; text-align: center
- all buttons: min-height: 48px

INLINE SCRIPT (at end of body):
- IntersectionObserver: threshold 0.1, adds .visible to [data-reveal] elements
- Nav scroll: on scroll > 50px, add .nav-scrolled class to nav (background becomes solid)

OUTPUT: Return ONLY the complete HTML. No explanations. No markdown. Start with <!DOCTYPE html>."""


def _parse_html_response(raw: str) -> Optional[str]:
    """Strip markdown fences and validate HTML output."""
    raw = raw.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(
            line for line in lines
            if not line.startswith("```")
        ).strip()

    # Validate it looks like HTML
    if not (raw.lower().startswith("<!doctype") or raw.lower().startswith("<html")):
        # Try to extract HTML from response
        match = re.search(r"(<!DOCTYPE html[\s\S]*</html>)", raw, re.IGNORECASE)
        if match:
            return match.group(1)
        logger.warning("AI response does not look like HTML")
        return None

    return raw


def _generate_site_with_groq(prompt: str, api_key: str, model: str) -> Optional[str]:
    """Generate preview site HTML using Groq (Llama)."""
    try:
        from groq import Groq
    except ImportError:
        raise RuntimeError("groq package not installed. Run: pip install groq")

    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        max_tokens=8192,
        temperature=0.7,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.choices[0].message.content
    html = _parse_html_response(raw)
    if html:
        logger.info(
            f"[Groq/{model}] preview site generated "
            f"(in={response.usage.prompt_tokens}, out={response.usage.completion_tokens})"
        )
    return html


def _generate_site_with_anthropic(prompt: str, api_key: str, model: str) -> Optional[str]:
    """Generate preview site HTML using Anthropic (Claude)."""
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic package not installed. Run: pip install anthropic")

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text
    html = _parse_html_response(raw)
    if html:
        logger.info(
            f"[Claude/{model}] preview site generated "
            f"(in={response.usage.input_tokens}, out={response.usage.output_tokens})"
        )
    return html


# ── Public function ──────────────────────────────────────────────────────────

def generate_preview_site(
    business_name: str,
    website: str,
    city: str,
    category: str,
    seo_score: int,
    problems: list[str],
    phone: Optional[str] = None,
    email: Optional[str] = None,
) -> Optional[str]:
    """
    Generate a self-contained HTML website for the business.

    Priority: Groq (free) -> Anthropic (paid) -> None

    Returns HTML string on success, None on failure.
    """
    from app.core.config import settings

    prompt = _build_preview_prompt(
        business_name=business_name,
        website=website,
        city=city,
        category=category,
        phone=phone,
        email=email,
        seo_score=seo_score,
        problems=problems,
    )

    # ── 1. Try Groq first (free) ─────────────────────────────────────────
    if settings.GROQ_API_KEY:
        try:
            logger.info(f"Generating preview site with Groq for {business_name}")
            return _generate_site_with_groq(
                prompt=prompt,
                api_key=settings.GROQ_API_KEY,
                model=settings.GROQ_MODEL,
            )
        except Exception as e:
            logger.error(f"Groq preview site generation failed: {e}")

    # ── 2. Try Anthropic second (paid) ───────────────────────────────────
    if settings.ANTHROPIC_API_KEY:
        try:
            logger.info(f"Generating preview site with Anthropic for {business_name}")
            return _generate_site_with_anthropic(
                prompt=prompt,
                api_key=settings.ANTHROPIC_API_KEY,
                model=settings.AI_EMAIL_MODEL,
            )
        except Exception as e:
            logger.error(f"Anthropic preview site generation failed: {e}")

    logger.warning("No AI provider configured for preview site generation")
    return None
