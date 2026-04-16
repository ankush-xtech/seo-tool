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
    hero_image_url: Optional[str] = None,
    about_image_url: Optional[str] = None,
) -> str:
    """Build the prompt for generating a preview website."""
    from app.core.config import settings

    problems_text = "\n".join(f"  - {p}" for p in problems[:6])

    # Map common categories to curated Unsplash photo IDs (hero, about)
    category_images = {
        "dentist":     ("photo-1629909613654-28e377c37b09", "photo-1588776814546-1ffcf47267a5"),
        "dental":      ("photo-1629909613654-28e377c37b09", "photo-1588776814546-1ffcf47267a5"),
        "plumber":     ("photo-1585704032915-c3400ca199e7", "photo-1581578731548-c64695cc6952"),
        "plumbing":    ("photo-1585704032915-c3400ca199e7", "photo-1581578731548-c64695cc6952"),
        "restaurant":  ("photo-1517248135467-4c7edcad34c4", "photo-1414235077428-338989a2e8c0"),
        "cafe":        ("photo-1554118811-1e0d58224f24", "photo-1495474472287-4d71bcdd2085"),
        "lawyer":      ("photo-1589829545856-d10d557cf95f", "photo-1507679799987-c73779587ccf"),
        "legal":       ("photo-1589829545856-d10d557cf95f", "photo-1507679799987-c73779587ccf"),
        "mechanic":    ("photo-1619642751034-765dfdf7c58e", "photo-1530046339160-ce3e530c7d2f"),
        "auto":        ("photo-1619642751034-765dfdf7c58e", "photo-1530046339160-ce3e530c7d2f"),
        "salon":       ("photo-1560066984-138dadb4c035", "photo-1522337360788-8b13dee7a37e"),
        "beauty":      ("photo-1560066984-138dadb4c035", "photo-1522337360788-8b13dee7a37e"),
        "gym":         ("photo-1534438327276-14e5300c3a48", "photo-1571019614242-c5c5dee9f50b"),
        "fitness":     ("photo-1534438327276-14e5300c3a48", "photo-1571019614242-c5c5dee9f50b"),
        "real estate": ("photo-1560518883-ce09059eeffa", "photo-1600596542815-ffad4c1539a9"),
        "property":    ("photo-1560518883-ce09059eeffa", "photo-1600596542815-ffad4c1539a9"),
        "accountant":  ("photo-1554224155-6726b3ff858f", "photo-1450101499163-c8848e968838"),
        "accounting":  ("photo-1554224155-6726b3ff858f", "photo-1450101499163-c8848e968838"),
        "doctor":      ("photo-1631217868264-e5b90bb7e133", "photo-1576091160550-2173dba999ef"),
        "medical":     ("photo-1631217868264-e5b90bb7e133", "photo-1576091160550-2173dba999ef"),
    }
    cat_lower = (category or "").lower()
    hero_photo = "photo-1497366216548-37526070297c"
    about_photo = "photo-1522071820081-009f0129c71c"
    for key, (h_photo, a_photo) in category_images.items():
        if key in cat_lower:
            hero_photo = h_photo
            about_photo = a_photo
            break

    # Use custom image URLs if provided, otherwise use category-based Unsplash
    hero_img = hero_image_url or f"https://images.unsplash.com/{hero_photo}?w=1600&q=80"
    about_img = about_image_url or f"https://images.unsplash.com/{about_photo}?w=800&q=80"

    return f"""Build a dark premium single-page website. Output ONLY raw HTML starting with <!DOCTYPE html>. No explanations.

BUSINESS: {business_name} | {category or "Local Business"} | {city or "Australia"} | Phone: {phone or "N/A"} | Email: {email or "N/A"}
IMAGES: Hero={hero_img} | About={about_img}

RULES: All CSS in <style>. Google Fonts: Inter + Playfair Display. Meta tags + LocalBusiness JSON-LD. Desktop-first, @media(max-width:768px) for mobile. ALL sections MUST be visible (opacity:1). No IntersectionObserver. No data-reveal.

CSS FOUNDATION (paste exactly):
:root{{--pri:#6366f1;--accent:#06b6d4;--bg:#030712;--bg2:#0a0f1e;--card:#111827;--gray:#9ca3af;--border:rgba(255,255,255,0.06);--grad:linear-gradient(135deg,#6366f1,#8b5cf6,#06b6d4);--r:20px;--glow:rgba(99,102,241,0.4)}}
*{{box-sizing:border-box;margin:0;padding:0}}
html{{scroll-behavior:smooth}}body{{font-family:'Inter',sans-serif;color:#fff;background:var(--bg2);overflow-x:hidden}}
.wrap{{max-width:1200px;margin:0 auto;padding:0 40px}}
.grad-text{{background:var(--grad);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.stitle{{font-family:'Playfair Display',serif;font-size:42px;font-weight:800;margin-bottom:20px}}
.card{{background:var(--card);border:1px solid var(--border);border-radius:var(--r);padding:36px;transition:all .4s}}
.card:hover{{transform:translateY(-8px);box-shadow:0 8px 40px var(--glow);border-color:rgba(99,102,241,0.3)}}
.btn{{padding:16px 36px;border-radius:50px;font-weight:600;cursor:pointer;transition:all .3s;text-decoration:none;display:inline-block;font-size:16px}}
.btn-g{{background:var(--grad);color:#fff;border:none;box-shadow:0 4px 20px var(--glow)}}.btn-g:hover{{transform:translateY(-3px);box-shadow:0 8px 30px var(--glow)}}
.btn-o{{background:none;color:#fff;border:2px solid rgba(255,255,255,0.2)}}.btn-o:hover{{border-color:var(--pri);background:rgba(99,102,241,0.1)}}
@keyframes glow{{0%,100%{{box-shadow:0 0 20px var(--glow)}}50%{{box-shadow:0 0 50px var(--glow)}}}}
@keyframes float{{0%,100%{{transform:translateY(0)}}50%{{transform:translateY(-10px)}}}}
section{{opacity:1;visibility:visible}}
@media(max-width:768px){{.wrap{{padding:0 20px}}.stitle{{font-size:28px}}.grid-3{{grid-template-columns:1fr!important}}.grid-4{{grid-template-columns:repeat(2,1fr)!important}}.flex-row{{flex-direction:column!important}}.hero-btns{{flex-direction:column}}.hero-btns .btn{{width:100%}}.nav-links{{display:none!important}}.footer-cols{{flex-direction:column;text-align:center}}.hero h1{{font-size:36px!important}}}}

BUILD THESE 8 SECTIONS (all visible, no hidden elements):

1. NAV: fixed, z-index:1000, transparent bg. Left: "{business_name}" bold white. Right: nav-links (About, Services, Contact) + small btn-g "Get Quote". JS: scroll>50px adds bg rgba(10,15,30,0.95)+backdrop-filter:blur(20px).

2. HERO: 100vh, bg=url('{hero_img}') center/cover. VERY dark overlay: rgba(3,7,18,0.95) — text MUST be clearly readable. Heading: 'Playfair Display' 64px, color:#FFFFFF (pure white, NOT gradient text — white is more readable on images). Write a tagline based on business like "Your Smile, Our Passion". Category label uppercase color:var(--accent). Subtitle color:#e2e8f0. Two buttons: btn-g + btn-o. Scroll chevron at bottom.

3. TITLE SECTION: padding:80px 0, bg:var(--bg), text-align:center. Write a headline for {business_name}: "Delivering Excellence in {category} Services Across {city}". Use .stitle with .grad-text. 2-line description in --gray, max-width:700px, margin:0 auto. Below: 3 pill badges ("Trusted Since 2010", "100% Satisfaction", "Certified Professionals").

4. ABOUT: padding:100px 0. MUST be side-by-side: use display:flex; flex-direction:row; gap:60px; align-items:center. Left div (flex:0 0 45%): img src="{about_img}" style="width:100%;border-radius:20px;box-shadow:0 0 40px var(--glow)". Right div (flex:1): .stitle heading, 3 sentences about the business in --gray. Add 3 pill badges below. Mobile(@media 768px): flex-direction:column, image width:100%.

5. SERVICES: padding:100px 0, bg:var(--bg). Centered .stitle.grad-text. Grid: display:grid; grid-template-columns:repeat(3,1fr); gap:32px (MUST have 32px gap, not less). 6 cards each: emoji in 72px circle, h3 title, p desc. Use 6 REAL service names for a {category} (e.g. for dentist: "General Dentistry","Cosmetic Dentistry","Teeth Whitening","Dental Implants","Orthodontics","Emergency Care"). Mobile: 1col.

6. STATS: padding:80px 0, bg:var(--grad). Use .wrap container (max-width:1200px, margin:0 auto). Grid: display:grid; grid-template-columns:repeat(4,1fr); gap:40px; text-align:center. Each stat: number in 'Playfair Display' 48px white, label in 14px rgba(255,255,255,0.8). No card background — just numbers + labels directly on gradient. Mobile: grid-template-columns:repeat(2,1fr).

7. TESTIMONIALS: padding:100px 0. Centered .stitle. Grid: repeat(3,1fr), gap:32px. 3 cards: quote mark 64px --pri opacity:0.3, gold stars, italic quote, reviewer name. Write realistic reviews for {category}. Mobile: 1col.

8. FOOTER: padding:60px 0 30px, bg:var(--bg). 4-col footer-cols: Company (name + 2-line about), Quick Links (About Us, Our Services, Testimonials, Contact), Services (write 4 REAL service names for {category} like "General Dentistry", "Cosmetic Care", "Dental Implants", "Emergency Services"), Contact (phone/email/city). Use real service names NOT "Service 1". Bottom bar: copyright + "Powered by {settings.COMPANY_NAME}". Mobile: stack centered.

SCRIPT: Only nav scroll (scrollY>50 adds .scrolled class with bg+blur). No IntersectionObserver.

Start with <!DOCTYPE html>."""




def get_default_prompt_template() -> str:
    """Return the default prompt with placeholder variables for the frontend editor.

    Uses placeholders like {business_name}, {category}, {city} etc.
    that will be substituted per-business when generating.
    """
    return _build_preview_prompt(
        business_name="{business_name}",
        website="{website}",
        city="{city}",
        category="{category}",
        phone="{phone}",
        email="{email}",
        seo_score=0,
        problems=[],
    )


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
    custom_prompt: Optional[str] = None,
    hero_image_url: Optional[str] = None,
    about_image_url: Optional[str] = None,
) -> Optional[str]:
    """
    Generate a self-contained HTML website for the business.

    Priority: Groq (free) -> Anthropic (paid) -> None

    Returns HTML string on success, None on failure.
    """
    from app.core.config import settings

    if custom_prompt:
        # Use the custom prompt — substitute business variables
        prompt = custom_prompt
        # Replace image URLs in the custom prompt if custom images provided
        if hero_image_url or about_image_url:
            import re
            if hero_image_url:
                # Replace the hero image URL (appears after Hero= and in bg=url())
                prompt = re.sub(
                    r"(Hero=)https?://[^\s|]+",
                    rf"\1{hero_image_url}",
                    prompt,
                )
                prompt = re.sub(
                    r"(bg=url\(['\"])https?://[^'\"]+(['\"])",
                    rf"\g<1>{hero_image_url}\2",
                    prompt,
                )
            if about_image_url:
                # Replace the about image URL (appears after About= and in img src=)
                prompt = re.sub(
                    r"(About=)https?://[^\s|]+",
                    rf"\1{about_image_url}",
                    prompt,
                )
                prompt = re.sub(
                    r'(img src=")https?://[^"]+(")',
                    rf"\1{about_image_url}\2",
                    prompt,
                )
    else:
        prompt = _build_preview_prompt(
            business_name=business_name,
            website=website,
            city=city,
            category=category,
            phone=phone,
            email=email,
            seo_score=seo_score,
            problems=problems,
            hero_image_url=hero_image_url,
            about_image_url=about_image_url,
        )

    # ── 1. Try Groq first (free) ─────────────────────────────────────────
    groq_error = None
    if settings.GROQ_API_KEY:
        try:
            logger.info(f"Generating preview site with Groq for {business_name}")
            result = _generate_site_with_groq(
                prompt=prompt,
                api_key=settings.GROQ_API_KEY,
                model=settings.GROQ_MODEL,
            )
            if result:
                return result
            groq_error = "Groq returned empty response"
        except Exception as e:
            groq_error = str(e)
            logger.error(f"Groq preview site generation failed: {e}")

    # ── 2. Try Anthropic second (paid) ───────────────────────────────────
    anthropic_error = None
    if settings.ANTHROPIC_API_KEY:
        try:
            logger.info(f"Generating preview site with Anthropic for {business_name}")
            result = _generate_site_with_anthropic(
                prompt=prompt,
                api_key=settings.ANTHROPIC_API_KEY,
                model=settings.AI_EMAIL_MODEL,
            )
            if result:
                return result
            anthropic_error = "Anthropic returned empty response"
        except Exception as e:
            anthropic_error = str(e)
            logger.error(f"Anthropic preview site generation failed: {e}")

    # ── All providers failed — raise with real error ─────────────────────
    if groq_error and ("rate_limit" in groq_error.lower() or "429" in groq_error):
        raise RuntimeError("Groq daily token limit reached. Wait for reset or add ANTHROPIC_API_KEY as fallback.")
    elif groq_error:
        raise RuntimeError(f"Groq failed: {groq_error[:200]}")
    elif anthropic_error:
        raise RuntimeError(f"Anthropic failed: {anthropic_error[:200]}")
    else:
        raise RuntimeError("No AI provider configured. Add GROQ_API_KEY or ANTHROPIC_API_KEY to .env")
