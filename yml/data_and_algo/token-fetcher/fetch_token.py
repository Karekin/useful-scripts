#!/usr/bin/env python3
"""
GitHub App Installation Token Fetcher

This script generates short-lived Installation Access Tokens for GitHub App authentication.
Tokens are written to a shared volume for git-sync to consume.

Security:
- Private key is read from Docker secret mount (/run/secrets/github_app_private_key)
- Tokens are valid for ~1 hour; refresh every 50 minutes
- No sensitive data is logged
"""

import os
import sys
import time
import json
import logging
from datetime import datetime, timezone

import jwt
import requests

# ============================================================================
# Configuration (from environment variables)
# ============================================================================
GITHUB_APP_ID = os.environ.get("GITHUB_APP_ID")
GITHUB_INSTALLATION_ID = os.environ.get("GITHUB_INSTALLATION_ID")
PRIVATE_KEY_PATH = os.environ.get("PRIVATE_KEY_PATH", "/run/secrets/github_app_private_key")
TOKEN_OUTPUT_PATH = os.environ.get("TOKEN_OUTPUT_PATH", "/run/git-token/token")
REFRESH_INTERVAL_SECONDS = int(os.environ.get("REFRESH_INTERVAL_SECONDS", "3000"))  # 50 min

# ============================================================================
# Logging Setup
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def load_private_key() -> str:
    """Load GitHub App private key from secret mount."""
    if not os.path.exists(PRIVATE_KEY_PATH):
        raise FileNotFoundError(f"Private key not found at {PRIVATE_KEY_PATH}")
    
    with open(PRIVATE_KEY_PATH, "r") as f:
        return f.read()


def generate_jwt(app_id: str, private_key: str) -> str:
    """
    Generate a JWT for GitHub App authentication.
    
    The JWT is used to authenticate as the GitHub App itself,
    before exchanging it for an Installation Access Token.
    """
    now = int(time.time())
    payload = {
        "iat": now - 60,       # Issued at (60s buffer for clock drift)
        "exp": now + 600,      # Expires in 10 minutes (max allowed)
        "iss": app_id          # GitHub App ID
    }
    
    token = jwt.encode(payload, private_key, algorithm="RS256")
    return token


def fetch_installation_token(jwt_token: str, installation_id: str) -> dict:
    """
    Exchange JWT for Installation Access Token.
    
    Returns:
        dict with 'token' and 'expires_at' keys
    """
    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    response = requests.post(url, headers=headers)
    response.raise_for_status()
    
    data = response.json()
    return {
        "token": data["token"],
        "expires_at": data["expires_at"]
    }


def write_token(token: str):
    """Write token to output file (atomic write using temp file)."""
    os.makedirs(os.path.dirname(TOKEN_OUTPUT_PATH), exist_ok=True)
    
    temp_path = TOKEN_OUTPUT_PATH + ".tmp"
    with open(temp_path, "w") as f:
        f.write(token)
    
    os.replace(temp_path, TOKEN_OUTPUT_PATH)
    os.chmod(TOKEN_OUTPUT_PATH, 0o600)


def main():
    """Main loop: generate and refresh tokens periodically."""
    
    # Validate required configuration
    if not GITHUB_APP_ID:
        logger.error("GITHUB_APP_ID environment variable is required")
        sys.exit(1)
    
    if not GITHUB_INSTALLATION_ID:
        logger.error("GITHUB_INSTALLATION_ID environment variable is required")
        sys.exit(1)
    
    logger.info("GitHub App Token Fetcher starting...")
    logger.info(f"App ID: {GITHUB_APP_ID}")
    logger.info(f"Installation ID: {GITHUB_INSTALLATION_ID}")
    logger.info(f"Token output path: {TOKEN_OUTPUT_PATH}")
    logger.info(f"Refresh interval: {REFRESH_INTERVAL_SECONDS}s ({REFRESH_INTERVAL_SECONDS // 60}min)")
    
    # Load private key once at startup
    try:
        private_key = load_private_key()
        logger.info("Private key loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load private key: {e}")
        sys.exit(1)
    
    while True:
        try:
            # Step 1: Generate JWT
            logger.info("Generating JWT...")
            jwt_token = generate_jwt(GITHUB_APP_ID, private_key)
            
            # Step 2: Exchange for Installation Token
            logger.info("Requesting Installation Access Token...")
            token_data = fetch_installation_token(jwt_token, GITHUB_INSTALLATION_ID)
            
            # Step 3: Write token to shared volume
            write_token(token_data["token"])
            logger.info(f"Token written successfully. Expires at: {token_data['expires_at']}")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP request failed: {e}")
        except Exception as e:
            logger.error(f"Token generation failed: {e}")
        
        # Sleep until next refresh
        logger.info(f"Sleeping for {REFRESH_INTERVAL_SECONDS}s before next refresh...")
        time.sleep(REFRESH_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()

