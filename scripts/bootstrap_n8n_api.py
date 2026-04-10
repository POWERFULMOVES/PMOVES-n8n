#!/usr/bin/env python3
"""Bootstrap an n8n owner account and a fresh Public API key."""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def request_json(
    opener: urllib.request.OpenerDirector,
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with opener.open(request, timeout=30) as response:
        content = response.read().decode("utf-8")
        return json.loads(content) if content else None


def extract_payload(data: Any) -> Any:
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return data


def load_env_value(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def random_password() -> str:
    return secrets.token_urlsafe(24)


def upsert_env(path: Path, pairs: dict[str, str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = set(pairs)
    updated: list[str] = []
    for line in lines:
        replaced = False
        for key in list(remaining):
            if line.startswith(f"{key}="):
                updated.append(f"{key}={pairs[key]}")
                remaining.remove(key)
                replaced = True
                break
        if not replaced:
            updated.append(line)
    if updated and updated[-1] != "":
        updated.append("")
    for key in pairs:
        if key in remaining:
            updated.append(f"{key}={pairs[key]}")
    path.write_text("\n".join(updated).rstrip() + "\n", encoding="utf-8")


def collect_scopes(scopes_payload: Any) -> list[str]:
    payload = extract_payload(scopes_payload)
    if isinstance(payload, list):
        return [str(item) for item in payload]
    if isinstance(payload, dict):
        scopes = payload.get("scopes")
        if isinstance(scopes, list):
            return [str(item) for item in scopes]
    raise RuntimeError("Unable to parse n8n API key scopes response")


def collect_api_keys(keys_payload: Any) -> list[dict[str, Any]]:
    payload = extract_payload(keys_payload)
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
    return []


def _read_env_file_value(path: Path, key: str) -> str:
    """Read a single value from an env file (KEY=value format)."""
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


def _wait_for_n8n(base_url: str, timeout: int = 120) -> None:
    """Wait for n8n to be ready, polling /healthz every 2 seconds."""
    import time

    health_url = f"{base_url}/healthz"
    print(f"waiting for n8n at {health_url} (timeout={timeout}s)...")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            req = urllib.request.Request(health_url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    print("n8n is ready")
                    return
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(2)
    raise RuntimeError(f"n8n did not become ready within {timeout}s at {health_url}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap an n8n owner account and Public API key.")
    parser.add_argument("--base-url", default=load_env_value("N8N_BASE_URL") or "http://localhost:5678")
    parser.add_argument("--api-url", default=load_env_value("N8N_API_URL") or "http://localhost:5678/api/v1")
    parser.add_argument("--email", default=load_env_value("N8N_OWNER_EMAIL", "SUPABASE_BOOT_USER_EMAIL") or "operator@pmoves.local")
    parser.add_argument("--first-name", default=load_env_value("N8N_OWNER_FIRST_NAME") or "PMOVES")
    parser.add_argument("--last-name", default=load_env_value("N8N_OWNER_LAST_NAME") or "Operator")
    parser.add_argument("--password", default=load_env_value("N8N_OWNER_PASSWORD"))
    parser.add_argument("--label", default=load_env_value("N8N_API_KEY_LABEL") or "PMOVES.AI automation bootstrap")
    parser.add_argument("--write-env", action="append", default=[])
    parser.add_argument("--wait-timeout", type=int, default=120,
                        help="Seconds to wait for n8n /healthz before giving up (default: 120)")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    api_url = args.api_url.rstrip("/")

    # --- P0 FIX: Wait for n8n to be healthy before any API calls ---
    _wait_for_n8n(base_url, timeout=args.wait_timeout)

    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

    settings = extract_payload(request_json(opener, "GET", f"{base_url}/rest/settings"))
    if not isinstance(settings, dict):
        raise RuntimeError("Unexpected n8n settings response")
    user_management = settings.get("userManagement") or {}
    needs_owner_setup = bool(user_management.get("showSetupOnFirstLoad"))

    password = args.password

    # --- P0 FIX: If no password supplied and owner already exists, try reading
    # from the env files written by a previous bootstrap run. This prevents the
    # 401 mismatch where a NEW random password is generated but the owner was
    # created with the OLD one.
    if not password and not needs_owner_setup:
        for env_path in env_paths:
            saved_pw = _read_env_file_value(env_path, "N8N_OWNER_PASSWORD")
            if saved_pw:
                password = saved_pw
                print(f"recovered owner password from {env_path}")
                break

    if needs_owner_setup and not password:
        password = random_password()
    if not password:
        raise RuntimeError(
            "N8N_OWNER_PASSWORD is required once the n8n owner account already exists. "
            "Set it in your env or pass --password. Check .env.local or env.shared "
            "for the password written during first bootstrap."
        )

    env_paths = [Path(env_path) for env_path in args.write_env]
    base_env_pairs = {
        "N8N_BASE_URL": base_url,
        "N8N_API_URL": api_url,
        "N8N_OWNER_EMAIL": args.email,
        "N8N_OWNER_PASSWORD": password,
    }

    if needs_owner_setup:
        payload = {
            "email": args.email,
            "firstName": args.first_name,
            "lastName": args.last_name,
            "password": password,
        }
        request_json(opener, "POST", f"{base_url}/rest/owner/setup", payload)
        print(f"created owner: {args.email}")
    else:
        payload = {
            "emailOrLdapLoginId": args.email,
            "password": password,
        }
        try:
            request_json(opener, "POST", f"{base_url}/rest/login", payload)
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                sys.stderr.write(
                    f"\n401 LOGIN FAILED for {args.email}\n"
                    f"  The owner account exists but the password doesn't match.\n"
                    f"  This usually means the password was generated on first bootstrap\n"
                    f"  and saved to .env.local, but the env file was lost or regenerated.\n\n"
                    f"  Recovery options:\n"
                    f"  1. Set N8N_OWNER_PASSWORD=<original_password> in your env\n"
                    f"  2. Check .env.local or pmoves/env.shared for the saved password\n"
                    f"  3. Reset n8n data: make -C pmoves volume-reset SERVICE=n8n\n"
                    f"     (WARNING: this deletes all n8n workflows and settings)\n\n"
                )
            raise
        print(f"logged in owner: {args.email}")

    for path in env_paths:
        upsert_env(path, base_env_pairs)
        print(f"wrote owner credentials: {path}")

    scopes = collect_scopes(request_json(opener, "GET", f"{base_url}/rest/api-keys/scopes"))
    existing_keys = collect_api_keys(request_json(opener, "GET", f"{base_url}/rest/api-keys"))
    for api_key in existing_keys:
        if api_key.get("label") == args.label and api_key.get("id"):
            request_json(opener, "DELETE", f"{base_url}/rest/api-keys/{api_key['id']}")
            print(f"deleted old API key: {api_key['id']}")

    key_payload = {
        "label": args.label,
        "scopes": scopes,
        "expiresAt": None,
    }
    created = extract_payload(request_json(opener, "POST", f"{base_url}/rest/api-keys/", key_payload))
    if not isinstance(created, dict) or not created.get("rawApiKey"):
        raise RuntimeError("n8n did not return a rawApiKey during bootstrap")
    raw_api_key = str(created["rawApiKey"])

    api_request = urllib.request.Request(
        urllib.parse.urljoin(api_url + "/", "workflows?limit=1"),
        headers={"X-N8N-API-KEY": raw_api_key},
        method="GET",
    )
    with urllib.request.urlopen(api_request, timeout=30) as response:
        if response.status >= 400:
            raise RuntimeError("Generated n8n API key failed validation")

    for path in env_paths:
        upsert_env(path, {**base_env_pairs, "N8N_API_KEY": raw_api_key})
        print(f"wrote bootstrap credentials: {path}")

    print("validated n8n Public API key")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        sys.stderr.write(detail or str(exc))
        raise
