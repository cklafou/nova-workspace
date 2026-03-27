#!/usr/bin/env python3
"""
check_keys.py -- API Key Checker for Nova Group Chat
=====================================================
Checks all environment variables and config files for existing API keys.
Run: python tools/nova_chat/check_keys.py

Checks:
  - ANTHROPIC_API_KEY (Claude)
  - GEMINI_API_KEY (Gemini / Google AI Studio)
  - GOOGLE_API_KEY (older Gemini key name)
  - OpenClaw gateway (Nova)
  - Validates keys are real by making a minimal test call
"""
import os
import sys
import json
import asyncio
from pathlib import Path


def mask(key: str) -> str:
    """Show first 8 and last 4 chars only."""
    if not key or len(key) < 12:
        return "****"
    return f"{key[:8]}...{key[-4:]}"


def check_env_keys() -> dict:
    """Scan environment variables for API keys."""
    found = {}

    # Anthropic
    for var in ["ANTHROPIC_API_KEY"]:
        val = os.environ.get(var)
        if val:
            found["ANTHROPIC_API_KEY"] = val

    # Gemini / Google -- check multiple possible names
    for var in ["GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENERATIVE_AI_API_KEY"]:
        val = os.environ.get(var)
        if val and "GEMINI" not in found:
            found["GEMINI_API_KEY"] = val
            found["GEMINI_KEY_SOURCE"] = var

    return found


def check_credential_files() -> dict:
    """Check common file locations for stored API keys."""
    found = {}
    home = Path.home()

    # Check .env files in workspace
    workspace = Path(__file__).parent.parent.parent
    for env_file in [workspace / ".env", workspace.parent / ".env", home / ".env"]:
        if env_file.exists():
            try:
                content = env_file.read_text(encoding="utf-8")
                for line in content.splitlines():
                    if "=" in line and not line.strip().startswith("#"):
                        key, _, val = line.partition("=")
                        key = key.strip()
                        val = val.strip().strip('"').strip("'")
                        if "ANTHROPIC" in key.upper() and val:
                            found[f"FILE:{key}"] = val
                        if "GEMINI" in key.upper() or "GOOGLE_API" in key.upper():
                            if val:
                                found[f"FILE:{key}"] = val
            except Exception:
                pass

    # Check PowerShell profile for $env: assignments
    ps_profile = home / "Documents" / "WindowsPowerShell" / "Microsoft.PowerShell_profile.ps1"
    if ps_profile.exists():
        try:
            content = ps_profile.read_text(encoding="utf-8")
            for line in content.splitlines():
                if "$env:ANTHROPIC_API_KEY" in line or "$env:GEMINI_API_KEY" in line:
                    found["PS_PROFILE"] = f"Found in {ps_profile}"
        except Exception:
            pass

    return found


def validate_anthropic_key(key: str) -> tuple[bool, str]:
    """Make a minimal API call to validate the Anthropic key."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )
        return True, "Valid -- Haiku responded OK"
    except Exception as e:
        err = str(e)
        if "401" in err or "invalid" in err.lower():
            return False, "Invalid key (401)"
        if "403" in err:
            return False, "Permission denied (403)"
        return False, f"Error: {err[:80]}"


def validate_gemini_key(key: str) -> tuple[bool, str]:
    """Make a minimal API call to validate the Gemini key."""
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=key)
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Hi",
            config=types.GenerateContentConfig(max_output_tokens=5),
        )
        return True, "Valid -- Gemini 2.5 Flash responded OK"
    except ImportError:
        return False, "google-genai not installed. Run: pip install google-genai --break-system-packages"
    except Exception as e:
        err = str(e)
        if "API_KEY_INVALID" in err or "400" in err:
            return False, "Invalid key"
        if "403" in err:
            return False, "Permission denied (403)"
        return False, f"Error: {err[:80]}"


async def check_nova_gateway() -> tuple[bool, str]:
    """Check if OpenClaw HTTP inference API is reachable."""
    import urllib.request, urllib.error
    def _check():
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:18789/v1/models",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=2) as resp:
                return resp.status == 200, resp.read().decode()
        except urllib.error.URLError:
            return False, ""
        except Exception:
            return False, ""
    loop = asyncio.get_event_loop()
    ok, body = await loop.run_in_executor(None, _check)
    if ok:
        # Try to extract model name from response
        try:
            import json
            models = json.loads(body).get("data", [])
            names = [m.get("id","") for m in models]
            model_str = ", ".join(names) if names else "unknown"
            return True, f"OpenClaw HTTP API online — models: {model_str}"
        except Exception:
            return True, "OpenClaw HTTP API online at http://127.0.0.1:18789"
    return False, "OpenClaw not running (start it to bring Nova online)"


def print_section(title: str):
    print(f"\n{'─' * 50}")
    print(f"  {title}")
    print('─' * 50)


def main():
    print("\n╔══════════════════════════════════════════════════╗")
    print("║         Nova Group Chat -- API Key Check         ║")
    print("╚══════════════════════════════════════════════════╝")

    # ── Environment variables ────────────────────────────────────────────────
    print_section("Environment Variables")
    env_keys = check_env_keys()

    anthropic_key = env_keys.get("ANTHROPIC_API_KEY")
    gemini_key = env_keys.get("GEMINI_API_KEY")
    gemini_source = env_keys.get("GEMINI_KEY_SOURCE", "GEMINI_API_KEY")

    if anthropic_key:
        print(f"  ✓ ANTHROPIC_API_KEY    {mask(anthropic_key)}")
    else:
        print(f"  ✗ ANTHROPIC_API_KEY    NOT SET")
        print(f"    Fix: $env:ANTHROPIC_API_KEY='sk-ant-...'")

    if gemini_key:
        print(f"  ✓ {gemini_source:<22} {mask(gemini_key)}")
    else:
        print(f"  ✗ GEMINI_API_KEY       NOT SET")
        print(f"    Fix: $env:GEMINI_API_KEY='AIza...'")
        print(f"    Get key: https://aistudio.google.com/apikey")

    # ── File-based keys ──────────────────────────────────────────────────────
    print_section("Config Files")
    file_keys = check_credential_files()
    if file_keys:
        for name, val in file_keys.items():
            if name == "PS_PROFILE":
                print(f"  ✓ PowerShell profile   {val}")
            else:
                print(f"  ✓ {name:<22} {mask(val) if len(val) > 12 else val}")
    else:
        print("  No API keys found in .env files or PowerShell profile")

    # ── Key validation ───────────────────────────────────────────────────────
    print_section("Key Validation (live test calls)")

    if anthropic_key:
        print("  Testing Anthropic... ", end="", flush=True)
        ok, msg = validate_anthropic_key(anthropic_key)
        print(f"{'✓' if ok else '✗'} {msg}")
    else:
        print("  Anthropic: skipped (no key)")

    if gemini_key:
        print("  Testing Gemini...    ", end="", flush=True)
        ok, msg = validate_gemini_key(gemini_key)
        print(f"{'✓' if ok else '✗'} {msg}")
    else:
        print("  Gemini:    skipped (no key)")

    # ── Nova gateway ─────────────────────────────────────────────────────────
    print_section("Nova (OpenClaw Gateway)")
    nova_ok, nova_msg = asyncio.run(check_nova_gateway())
    print(f"  {'✓' if nova_ok else '○'} {nova_msg}")

    # ── Summary ──────────────────────────────────────────────────────────────
    print_section("Summary")
    ready = []
    missing = []

    if anthropic_key:
        ready.append("Claude (Anthropic API)")
    else:
        missing.append("Claude -- set ANTHROPIC_API_KEY")

    if gemini_key:
        ready.append("Gemini (Google AI API)")
    else:
        missing.append("Gemini -- set GEMINI_API_KEY")

    if nova_ok:
        ready.append("Nova (OpenClaw local)")
    else:
        missing.append("Nova -- start OpenClaw first")

    ready.append("Cole (always online)")

    for r in ready:
        print(f"  ✓ {r}")
    for m in missing:
        print(f"  ✗ {m}")

    if missing:
        print(f"\n  {len(missing)} participant(s) will be offline in nova_chat.")
        print("  Chat works with any combination -- offline AIs are greyed out.")
    else:
        print("\n  All participants ready. Launch: python tools/nova_chat/launch.py")

    print()


if __name__ == "__main__":
    main()
