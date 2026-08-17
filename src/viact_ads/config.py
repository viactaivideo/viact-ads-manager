"""Credential loading and validation.

Values come from the process environment, falling back to a `.env` file in the
repository root. Nothing is written to stdout here: this process speaks the MCP
protocol over stdout, so any stray print would corrupt the stream.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_API_VERSION = "v25"

REPO_ROOT = Path(__file__).resolve().parents[2]

REQUIRED = (
    "GOOGLE_ADS_DEVELOPER_TOKEN",
    "GOOGLE_ADS_CLIENT_ID",
    "GOOGLE_ADS_CLIENT_SECRET",
    "GOOGLE_ADS_REFRESH_TOKEN",
)


class ConfigError(RuntimeError):
    """Raised when credentials are missing or malformed."""


def load_dotenv(path: Path | None = None) -> None:
    """Populate os.environ from a .env file without overriding real env vars.

    Deliberately minimal (no python-dotenv dependency): `KEY=value` per line,
    `#` comments, optional `export ` prefix, optional surrounding quotes.
    """
    path = path or (REPO_ROOT / ".env")
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
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        # Real environment wins, so .mcp.json / shell exports can override the file.
        os.environ.setdefault(key, value)


def normalize_customer_id(customer_id: str | None) -> str | None:
    """Strip the display formatting from an account ID: 123-456-7890 -> 1234567890."""
    if customer_id is None:
        return None
    digits = re.sub(r"[^0-9]", "", str(customer_id))
    if not digits:
        return None
    if len(digits) != 10:
        raise ConfigError(
            f"Google Ads customer ID must be 10 digits, got {digits!r} "
            f"(from input {customer_id!r}). Use the ID shown in the top-right "
            f"of the Google Ads UI, e.g. 123-456-7890."
        )
    return digits


@dataclass(frozen=True)
class Config:
    developer_token: str
    client_id: str
    client_secret: str
    refresh_token: str
    login_customer_id: str | None
    default_customer_id: str | None
    api_version: str

    @property
    def endpoint(self) -> str:
        return f"https://googleads.googleapis.com/{self.api_version}"

    def resolve_customer_id(self, customer_id: str | None) -> str:
        """Pick the account to query, preferring the explicit argument."""
        resolved = normalize_customer_id(customer_id) or self.default_customer_id
        if not resolved:
            raise ConfigError(
                "No customer_id given and GOOGLE_ADS_CUSTOMER_ID is not set. "
                "Pass customer_id explicitly, or run list_accessible_customers "
                "to see which accounts these credentials can reach."
            )
        return resolved


def load_config() -> Config:
    load_dotenv()

    missing = [name for name in REQUIRED if not os.environ.get(name, "").strip()]
    if missing:
        raise ConfigError(
            "Missing Google Ads credentials: "
            + ", ".join(missing)
            + ". Copy .env.example to .env and fill it in — see docs/SETUP.md."
        )

    version = os.environ.get("GOOGLE_ADS_API_VERSION", "").strip() or DEFAULT_API_VERSION
    if not re.fullmatch(r"v\d+", version):
        raise ConfigError(
            f"GOOGLE_ADS_API_VERSION must look like 'v25', got {version!r}."
        )

    return Config(
        developer_token=os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"].strip(),
        client_id=os.environ["GOOGLE_ADS_CLIENT_ID"].strip(),
        client_secret=os.environ["GOOGLE_ADS_CLIENT_SECRET"].strip(),
        refresh_token=os.environ["GOOGLE_ADS_REFRESH_TOKEN"].strip(),
        login_customer_id=normalize_customer_id(
            os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID")
        ),
        default_customer_id=normalize_customer_id(
            os.environ.get("GOOGLE_ADS_CUSTOMER_ID")
        ),
        api_version=version,
    )
