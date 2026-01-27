import os
import json
import time
import requests
from typing import Optional, Dict

GITHUB_API_URL = "https://api.github.com/repos/anthonypdawson/vector-inspector/releases/latest"
CACHE_FILE = os.path.expanduser("~/.vector_inspector_update_cache.json")
CACHE_TTL = 24 * 60 * 60  # 1 day in seconds


class UpdateService:
    @staticmethod
    def get_latest_release(force_refresh: bool = False) -> Optional[Dict]:
        """
        Fetch the latest release info from GitHub, with caching and rate limit handling.
        Returns None on error or if rate limited.
        """
        now = int(time.time())
        # Check cache for rate limit state or valid release
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    cache = json.load(f)
                # If rate limited, respect the reset time
                if cache.get("rate_limited_until", 0) > now:
                    return None
                if not force_refresh and now - cache.get("timestamp", 0) < CACHE_TTL:
                    return cache.get("release")
            except Exception:
                pass
        try:
            resp = requests.get(GITHUB_API_URL, timeout=5)
            if resp.status_code == 200:
                release = resp.json()
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump({"timestamp": now, "release": release}, f)
                return release
            elif resp.status_code == 403:
                # Check for rate limit headers
                reset = resp.headers.get("X-RateLimit-Reset")
                if reset:
                    rate_limited_until = int(reset)
                else:
                    # Default to 1 hour if no header
                    rate_limited_until = now + 3600
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump({"rate_limited_until": rate_limited_until}, f)
                return None
        except Exception:
            pass
        return None

    @staticmethod
    def compare_versions(current_version: str, latest_version: str) -> bool:
        """
        Returns True if latest_version is newer than current_version.
        """

        def parse(v):
            return [int(x) for x in v.strip("v").split(".") if x.isdigit()]

        return parse(latest_version) > parse(current_version)

    @staticmethod
    def get_update_instructions() -> Dict[str, str]:
        """
        Returns update instructions for both PyPI and GitHub.
        """
        return {
            "pip": "pip install --upgrade vector-inspector",
            "github": "https://github.com/anthonypdawson/vector-inspector/releases/latest",
        }
