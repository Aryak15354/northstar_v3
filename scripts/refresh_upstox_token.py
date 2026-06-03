#!/usr/bin/env python3
"""
Daily Upstox Token Refresh Script

Run this script each morning before market hours to update your Upstox access token.
The token is valid for 24 hours and must be refreshed daily.

Usage:
    python scripts/refresh_upstox_token.py

The script will:
1. Prompt you to visit the Upstox authorization URL
2. Ask you to paste the redirect URL after authorization
3. Extract and save the new access token to .env.options
"""

import os
import sys
import argparse
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import logging

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.options.config_loader import get_config
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def update_env_file(access_token: str, env_file: Path = Path(".env.options")) -> None:
    """Update the access token in .env.options file"""
    if not env_file.exists():
        logger.error(f"Environment file not found: {env_file}")
        return
    
    # Read existing content
    lines = env_file.read_text().splitlines()
    
    # Update or add UPSTOX_ACCESS_TOKEN
    token_found = False
    new_lines = []
    
    for line in lines:
        if line.startswith("UPSTOX_ACCESS_TOKEN="):
            new_lines.append(f"UPSTOX_ACCESS_TOKEN={access_token}")
            token_found = True
        else:
            new_lines.append(line)
    
    if not token_found:
        new_lines.append(f"UPSTOX_ACCESS_TOKEN={access_token}")
    
    # Write back
    env_file.write_text("\n".join(new_lines) + "\n")
    logger.info(f"✅ Updated access token in {env_file}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh the daily Upstox access token")
    parser.add_argument(
        "--redirect-url",
        default="",
        help="Full redirect URL returned by Upstox after authorization",
    )
    parser.add_argument(
        "--auth-code",
        default="",
        help="Authorization code from the Upstox redirect flow",
    )
    return parser.parse_args()


def main():
    """Main token refresh flow"""
    args = parse_args()
    print("\n" + "="*70)
    print("🔑 UPSTOX TOKEN REFRESH")
    print("="*70 + "\n")
    
    # Load config
    try:
        config = get_config()
        api_key = config.upstox.api_key
        api_secret = config.upstox.api_secret
        redirect_uri = os.getenv("UPSTOX_REDIRECT_URI", "").strip()
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return 1
    
    if not api_key or not api_secret or not redirect_uri:
        logger.error(
            "❌ UPSTOX_API_KEY, UPSTOX_API_SECRET, and UPSTOX_REDIRECT_URI must be set in .env.options"
        )
        return 1
    
    # Generate authorization URL
    auth_url = (
        f"https://api.upstox.com/v2/login/authorization/dialog"
        f"?client_id={api_key}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
    )
    
    print("📋 STEP 1: Visit the authorization URL")
    print("-" * 70)
    print(f"\n{auth_url}\n")
    print("-" * 70)
    print("\n⚠️  This will open Upstox login page in your browser")
    print("   1. Log in with your Upstox credentials")
    print("   2. Authorize the application")
    print("   3. You'll be redirected to a URL starting with your redirect_uri")
    print("   4. Copy the ENTIRE redirect URL\n")
    
    redirect_url = str(args.redirect_url or "").strip()
    auth_code = str(args.auth_code or "").strip()
    if not redirect_url and not auth_code:
        input("Press Enter when you're ready to continue...")
        
        print("\n📋 STEP 2: Paste the redirect URL")
        print("-" * 70)
        redirect_url = input("\nPaste the full redirect URL here: ").strip()
    
    if not redirect_url and not auth_code:
        logger.error("❌ No redirect URL or authorization code provided")
        return 1
    
    # Extract authorization code
    try:
        if not auth_code:
            parsed = urlparse(redirect_url)
            params = parse_qs(parsed.query)
            auth_code = params.get('code', [None])[0]
        
        if not auth_code:
            logger.error("❌ No authorization code found in URL")
            return 1
        
        logger.info(f"✅ Extracted authorization code: {auth_code[:10]}...")
        
    except Exception as e:
        logger.error(f"❌ Failed to parse redirect URL: {e}")
        return 1
    
    # Exchange code for access token
    print("\n📋 STEP 3: Exchanging code for access token...")
    print("-" * 70)
    
    try:
        import requests
        
        token_url = config.upstox.endpoints.get(
            "token_refresh",
            "https://api.upstox.com/v2/login/authorization/token",
        )
        payload = {
            "code": auth_code,
            "client_id": api_key,
            "client_secret": api_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code"
        }
        
        headers = {
            "accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        response = requests.post(token_url, data=payload, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        access_token = data.get("access_token")
        
        if not access_token:
            logger.error(f"❌ No access token in response: {data}")
            return 1
        
        logger.info(f"✅ Received access token: {access_token[:10]}...")
        
        # Update .env.options file
        update_env_file(
            access_token,
            env_file=Path(str(os.getenv("UPSTOX_ENV_FILE", ".env.options")).strip()),
        )
        
        print("\n" + "="*70)
        print("✅ TOKEN REFRESH COMPLETE!")
        print("="*70)
        print("\n📌 Your new access token has been saved to .env.options")
        print("📌 The token is valid for 24 hours")
        print("📌 Run this script again tomorrow before market hours\n")
        
        # Test the token
        print("🧪 Testing token with a quick API call...")
        try:
            profile = requests.get(
                "https://api.upstox.com/v2/user/profile",
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {access_token}",
                },
                timeout=15,
            )
            if profile.status_code == 200:
                payload = profile.json()
                logger.info(
                    "✅ Token is valid! User: %s",
                    payload.get("data", {}).get("user_name", "Unknown"),
                )
            else:
                logger.warning("⚠️  Token test returned HTTP %s", profile.status_code)
        except Exception as e:
            logger.warning(f"⚠️  Token test failed: {e}")
            logger.warning("   This might be normal if markets are closed")
        
        return 0
        
    except requests.exceptions.HTTPError as e:
        logger.error(f"❌ HTTP error during token exchange: {e}")
        if e.response:
            logger.error(f"   Response: {e.response.text}")
        return 1
    except Exception as e:
        logger.error(f"❌ Failed to exchange code for token: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
