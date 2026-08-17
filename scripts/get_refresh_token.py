#!/usr/bin/env python3
"""Mint a Google Ads API refresh token via the OAuth2 loopback flow.

Run this on a machine that has a browser — it cannot run on a headless server:

    python3 scripts/get_refresh_token.py            # "Desktop app" OAuth client
    python3 scripts/get_refresh_token.py --port 8080  # "Web application" client

It reads GOOGLE_ADS_CLIENT_ID / GOOGLE_ADS_CLIENT_SECRET from the environment
or from .env, and prompts if they are absent. Standard library only — no
install step required.

If you have no machine to run this on, use Google's OAuth Playground instead —
see docs/SETUP.md, which covers that browser-only route.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.server
import json
import os
import secrets
import socket
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

SCOPE = "https://www.googleapis.com/auth/adwords"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_dotenv() -> None:
    path = REPO_ROOT / ".env"
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, sep, value = line.partition("=")
        if not sep:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    """Captures the ?code= redirect Google sends back to localhost."""

    result: dict[str, str] = {}

    def do_GET(self) -> None:  # noqa: N802 (name fixed by BaseHTTPRequestHandler)
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        CallbackHandler.result = {k: v[0] for k, v in params.items()}

        ok = "code" in CallbackHandler.result
        body = (
            "<h2>Authorisation complete.</h2><p>You can close this tab and "
            "return to the terminal.</p>"
            if ok
            else f"<h2>Authorisation failed.</h2><pre>{CallbackHandler.result}</pre>"
        )
        payload = f"<html><body style='font-family:sans-serif'>{body}</body></html>"
        self.send_response(200 if ok else 400)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(payload.encode("utf-8"))

    def log_message(self, *args) -> None:
        """Silence the default request logging."""


def post_form(url: str, fields: dict[str, str]) -> dict:
    data = urllib.parse.urlencode(fields).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise SystemExit(f"\nToken exchange failed ({exc.code}):\n{detail}") from exc


def prompt(name: str, secret: bool = False) -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    try:
        entered = input(f"{name}: ").strip()
    except EOFError:
        raise SystemExit(f"{name} is required but no value was provided.")
    if not entered:
        raise SystemExit(f"{name} is required.")
    return entered


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mint a Google Ads API refresh token via the OAuth2 loopback flow."
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help=(
            "Fix the loopback port instead of picking a free one. Required for a "
            "'Web application' OAuth client, which only accepts redirect URIs that "
            "were registered exactly — register http://localhost:PORT and pass the "
            "same PORT here. 'Desktop app' clients accept any port, so leave unset."
        ),
    )
    args = parser.parse_args()

    load_dotenv()

    print("Google Ads API — refresh token generator\n")
    client_id = prompt("GOOGLE_ADS_CLIENT_ID")
    client_secret = prompt("GOOGLE_ADS_CLIENT_SECRET", secret=True)

    port = args.port or free_port()
    redirect_uri = f"http://localhost:{port}"

    # PKCE, recommended by Google for installed/desktop OAuth clients.
    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    state = secrets.token_urlsafe(16)

    auth_url = AUTH_URL + "?" + urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": SCOPE,
            # offline + consent together guarantee a refresh_token is returned,
            # even if this account has authorised the client before.
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )

    server = http.server.HTTPServer(("127.0.0.1", port), CallbackHandler)
    threading.Thread(target=server.handle_request, daemon=True).start()

    print(f"\nListening on {redirect_uri}")
    print("Opening your browser. Sign in with the Google account that has access")
    print("to your Google Ads MCC, then grant the requested permission.\n")
    print(f"If the browser does not open, paste this URL manually:\n\n{auth_url}\n")
    webbrowser.open(auth_url)

    print("Waiting for the redirect...")
    for _ in range(600):  # ~5 minutes
        if CallbackHandler.result:
            break
        threading.Event().wait(0.5)

    result = CallbackHandler.result
    if not result:
        raise SystemExit("Timed out waiting for authorisation.")
    if "error" in result:
        raise SystemExit(f"Authorisation denied: {result['error']}")
    if result.get("state") != state:
        raise SystemExit("State mismatch — aborting, the redirect may be forged.")

    tokens = post_form(
        TOKEN_URL,
        {
            "code": result["code"],
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "code_verifier": verifier,
        },
    )

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        raise SystemExit(
            "Google returned no refresh_token. This usually means the client is "
            "not a 'Desktop app' OAuth client, or consent was previously granted "
            "without access_type=offline. Revoke the app at "
            "https://myaccount.google.com/permissions and run this again."
        )

    print("\n" + "=" * 68)
    print("Success. Add this line to your .env file:\n")
    print(f"GOOGLE_ADS_REFRESH_TOKEN={refresh_token}")
    print("=" * 68)
    print("\nKeep this value secret — it grants ongoing access to your Ads account.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
