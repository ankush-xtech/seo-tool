"""
Vercel Deployer — deploys a static HTML file to Vercel via their REST API.

Usage:
    url = deploy_to_vercel(html_content="<html>...</html>", site_name="joes-plumbing")
    # Returns: "https://joes-plumbing-abc123.vercel.app" or None on failure

.env setup:
    VERCEL_API_TOKEN=your-token-from-vercel.com/account/tokens
    VERCEL_TEAM_ID=team_xxx  (optional, for team deployments)
"""

import base64
import logging
import re
from typing import Optional

import requests

logger = logging.getLogger(__name__)

VERCEL_DEPLOY_URL = "https://api.vercel.com/v13/deployments"
VERCEL_PROJECTS_URL = "https://api.vercel.com/v9/projects"


def _slugify(name: str) -> str:
    """Convert a business name to a URL-safe slug for Vercel project naming."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)  # remove special chars
    slug = re.sub(r"[\s]+", "-", slug)  # spaces to hyphens
    slug = re.sub(r"-+", "-", slug)  # collapse multiple hyphens
    slug = slug.strip("-")
    # Vercel project names: max 100 chars, must start with letter/number
    slug = slug[:80] if len(slug) > 80 else slug
    return slug or "preview-site"


def _get_auth_headers():
    from app.core.config import settings
    return {"Authorization": f"Bearer {settings.VERCEL_API_TOKEN}", "Content-Type": "application/json"}


def _get_team_params():
    from app.core.config import settings
    return {"teamId": settings.VERCEL_TEAM_ID} if settings.VERCEL_TEAM_ID else {}


def _disable_sso_protection(project_name: str) -> None:
    """Disable SSO / Deployment Protection so the preview is publicly accessible."""
    try:
        response = requests.patch(
            f"{VERCEL_PROJECTS_URL}/{project_name}",
            headers=_get_auth_headers(),
            params=_get_team_params() or None,
            json={"ssoProtection": None}, 
            timeout=10,
        )
        if response.status_code == 200:
            logger.info(f"SSO protection disabled for project: {project_name}")
        else:
            logger.warning(f"Failed to disable SSO for {project_name}: {response.status_code}")
    except Exception as e:
        logger.warning(f"Could not disable SSO for {project_name}: {e}")


def deploy_to_vercel(
    html_content: str,
    site_name: str,
) -> Optional[str]:
    """
    Deploy a single index.html to Vercel and return the deployment URL.

    Args:
        html_content: Complete HTML string to deploy
        site_name: Human-readable name (will be slugified)

    Returns:
        Deployment URL (e.g. "https://xxx.vercel.app") or None on failure
    """
    from app.core.config import settings

    if not settings.VERCEL_API_TOKEN:
        logger.error("VERCEL_API_TOKEN not configured")
        return None

    slug = _slugify(site_name)
    project_name = f"preview-{slug}"

    # Base64 encode the HTML content
    html_b64 = base64.b64encode(html_content.encode("utf-8")).decode("utf-8")

    payload = {
        "name": project_name,
        "files": [
            {
                "file": "index.html",
                "data": html_b64,
                "encoding": "base64",
            }
        ],
        "projectSettings": {
            "framework": None,
        },
        "target": "production",
    }

    try:
        response = requests.post(
            VERCEL_DEPLOY_URL,
            json=payload,
            headers=_get_auth_headers(),
            params=_get_team_params() or None,
            timeout=30,
        )

        if response.status_code in (200, 201):
            data = response.json()

            # Use the production alias (cleaner URL) if available
            aliases = data.get("alias", [])
            if aliases:
                url = aliases[0]
            else:
                url = data.get("url", "")

            if url and not url.startswith("http"):
                url = f"https://{url}"

            # Disable SSO protection so the preview is publicly accessible
            _disable_sso_protection(project_name)

            logger.info(f"Vercel deployment successful: {url}")
            return url
        else:
            logger.error(
                f"Vercel deployment failed: {response.status_code} — {response.text[:500]}"
            )
            return None

    except requests.exceptions.Timeout:
        logger.error("Vercel deployment timed out")
        return None
    except Exception as e:
        logger.error(f"Vercel deployment error: {e}")
        return None
