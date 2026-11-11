"""Minimal client for Jev through OpenRouter's Decisions API.

Images are sent as base64 data-URL `image_url` parts. Jev reads them anywhere
in `state` (at any depth) and inside a question's `instructions`/`criteria`.
"""
import base64
import json
import os
import ssl
import urllib.error
import urllib.request
from pathlib import Path

import certifi

# python.org builds ship without system CA certs, so use certifi's bundle.
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

ENDPOINT = "https://openrouter.ai/api/alpha/decisions"
MODEL = "typesafe/jev-1.14"
ENV_FILE = Path(__file__).parent / ".env"


def api_key():
    if os.environ.get("OPENROUTER_API_KEY"):
        return os.environ["OPENROUTER_API_KEY"]
    # .env may hold KEY=VALUE lines or just the bare key.
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line.startswith("sk-or-"):
            return line
        if line.split("=", 1)[0].strip().removeprefix("export ").strip() == "OPENROUTER_API_KEY":
            return line.split("=", 1)[1].strip().strip("\"'")
    raise RuntimeError("no OpenRouter key found")


def image_part(path):
    data = base64.b64encode(Path(path).read_bytes()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{data}"}}


def decide(state, questions, model=MODEL):
    """POST one Decisions request. Returns the parsed JSON response."""
    body = json.dumps({"model": model, "state": state, "questions": questions}).encode()
    req = urllib.request.Request(ENDPOINT, data=body, method="POST", headers={
        "Authorization": f"Bearer {api_key()}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=300, context=SSL_CONTEXT) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as err:
        raise RuntimeError(f"HTTP {err.code}: {err.read().decode(errors='replace')[:2000]}") from None
