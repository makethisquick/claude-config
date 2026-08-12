"""Google Ads client construction.

Deliberately mirrors the auth approach in Google's official read-only MCP server
(`ads_mcp/utils.py`) so both servers authenticate identically: Application Default
Credentials for identity, developer token from the environment.
"""

import contextlib
import os
import subprocess
from unittest.mock import patch

import google.auth
from google.ads.googleads.client import GoogleAdsClient

ADS_SCOPE = "https://www.googleapis.com/auth/adwords"

# Pinned explicitly and passed to GoogleAdsClient below. Left unset, the library
# would silently follow its own default (`_VALID_API_VERSIONS[0]`), so a
# `google-ads` upgrade would move every service, type and enum in this server to
# a new API version with no code change. Bump this deliberately.
API_VERSION = "v25"

_client: GoogleAdsClient | None = None


@contextlib.contextmanager
def _prevent_stdio_inheritance():
    """Stop child processes inheriting our stdio handles.

    `google.auth.default()` may shell out to gcloud; without this the subprocess
    can grab the stdio transport's handles and deadlock the server.
    """
    original_popen = subprocess.Popen

    def safe_popen(*args, **kwargs):
        if kwargs.get("stdin") is None:
            kwargs["stdin"] = subprocess.DEVNULL
        return original_popen(*args, **kwargs)

    with patch("subprocess.Popen", new=safe_popen):
        yield


def get_client() -> GoogleAdsClient:
    """Returns a cached GoogleAdsClient built from ADC + developer token."""
    global _client
    if _client is not None:
        return _client

    dev_token = os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN")
    if not dev_token:
        raise ValueError(
            "GOOGLE_ADS_DEVELOPER_TOKEN is not set. The launcher script reads it "
            "from the macOS Keychain — run the server via google-ads-write.sh."
        )

    with _prevent_stdio_inheritance():
        credentials, _ = google.auth.default(scopes=[ADS_SCOPE])

    args = {
        "credentials": credentials,
        "developer_token": dev_token,
        "use_proto_plus": True,
        "version": API_VERSION,
    }
    login_customer_id = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID")
    if login_customer_id:
        args["login_customer_id"] = login_customer_id

    _client = GoogleAdsClient(**args)
    return _client


def normalize_customer_id(customer_id: str) -> str:
    """Google Ads shows IDs as 123-456-7890; the API wants them bare."""
    return str(customer_id).replace("-", "").strip()
