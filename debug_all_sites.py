#!/usr/bin/env python3
"""Debug script to test login for all configured sites."""

import re
import sys
from pathlib import Path
from typing import Any, Dict

import httpx
import yaml

sys.path.insert(0, str(Path(__file__).parent))
from src.storage import CredentialManager


def load_config() -> Dict[str, Any]:
    """Load configuration from yaml file."""
    config_path = Path(__file__).parent / "config" / "config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def extract_form_fields(html: str) -> Dict[str, Dict[str, str]]:
    """Extract all form fields from HTML."""
    inputs = re.findall(r"<input[^>]*>", html, re.IGNORECASE)
    form_fields = {}

    for inp in inputs:
        name_match = re.search(r'name=["\']([^"\']+)["\']', inp)
        value_match = re.search(r'value=["\']([^"\']*)["\']', inp)
        type_match = re.search(r'type=["\']([^"\']+)["\']', inp)

        if name_match:
            name = name_match.group(1)
            value = value_match.group(1) if value_match else ""
            field_type = type_match.group(1) if type_match else "text"
            form_fields[name] = {"value": value, "type": field_type}

    return form_fields


def auto_detect_login_fields(form_fields: Dict[str, Dict[str, str]]) -> Dict[str, str]:
    """Auto-detect username, password, and submit fields."""
    detected = {}

    # Look for username field
    username_fields = [
        k
        for k in form_fields.keys()
        if "user" in k.lower() or "usuario" in k.lower() or "login" in k.lower()
    ]
    if username_fields:
        detected["username_field"] = username_fields[0]

    # Look for password field
    password_fields = [
        k
        for k in form_fields.keys()
        if "pass" in k.lower() or "pwd" in k.lower() or "clave" in k.lower()
    ]
    if password_fields:
        detected["password_field"] = password_fields[0]

    # Look for submit button
    button_fields = [
        k
        for k in form_fields.keys()
        if form_fields[k]["type"].lower() in ["submit", "button"]
        and ("btn" in k.lower() or "submit" in k.lower() or "entrar" in k.lower())
    ]
    if button_fields:
        detected["submit_field"] = button_fields[0]
        detected["submit_value"] = form_fields[button_fields[0]]["value"]

    return detected


def test_site_login(
    site_config: Dict[str, Any], cm: CredentialManager
) -> Dict[str, Any]:
    """Test login for a specific site."""
    site_name = site_config.get("name", "Unknown")
    url = site_config.get("url", "")
    credential_key = site_config.get("credential_key")

    result = {
        "site_name": site_name,
        "url": url,
        "has_auth": "authentication" in site_config.get("checks_enabled", []),
        "status": "skipped",
        "details": {},
    }

    # Skip if no authentication needed
    if not result["has_auth"]:
        result["status"] = "success"
        result["details"]["message"] = "No authentication required (uptime-only check)"
        return result

    # Get credentials
    if not credential_key:
        result["status"] = "error"
        result["details"]["error"] = "No credential_key configured"
        return result

    creds = cm.get_credentials_by_key(credential_key)
    if not creds.get("username") or not creds.get("password"):
        result["status"] = "error"
        result["details"]["error"] = f"Credentials not found for '{credential_key}'"
        return result

    # Test the login
    try:
        client = httpx.Client(timeout=30.0, follow_redirects=True)

        # Get login page
        login_endpoint = site_config.get("authentication", {}).get(
            "login_endpoint", "/"
        )
        login_url = url.rstrip("/") + "/" + login_endpoint.lstrip("/")

        print(f"  Fetching: {login_url}")
        response = client.get(login_url)

        if response.status_code != 200:
            result["status"] = "error"
            result["details"]["error"] = (
                f"Failed to load login page: HTTP {response.status_code}"
            )
            return result

        # Extract form fields
        form_fields = extract_form_fields(response.text)
        detected_fields = auto_detect_login_fields(form_fields)

        result["details"]["form_fields_count"] = len(form_fields)
        result["details"]["detected_fields"] = detected_fields

        # Check if we detected required fields
        if not detected_fields.get("username_field") or not detected_fields.get(
            "password_field"
        ):
            result["status"] = "warning"
            result["details"]["warning"] = "Could not auto-detect login fields"
            result["details"]["all_fields"] = list(form_fields.keys())
            return result

        # Try to identify success indicators in config
        success_indicators = site_config.get("authentication", {}).get(
            "success_indicators", []
        )
        result["details"]["success_indicators"] = success_indicators

        result["status"] = "ready"
        result["details"]["message"] = "Login fields detected successfully"

        return result

    except Exception as e:
        result["status"] = "error"
        result["details"]["error"] = str(e)
        return result


def main():
    """Test login for all configured sites."""
    print("=" * 70)
    print("Multi-Site Login Debug Tool")
    print("=" * 70)
    print()

    # Load config
    try:
        config = load_config()
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        return

    # Get credential manager
    cm = CredentialManager()

    # Get sites
    sites = config.get("sites", [])
    if not sites:
        print("❌ No sites configured in config.yaml")
        return

    print(f"Found {len(sites)} site(s) to test\n")

    # Test each site
    results = []
    for site_config in sites:
        site_name = site_config.get("name", "Unknown")
        print(f"Testing: {site_name}")
        print("-" * 70)

        result = test_site_login(site_config, cm)
        results.append(result)

        # Print result
        status_icons = {
            "success": "✓",
            "ready": "✓",
            "warning": "⚠",
            "error": "✗",
            "skipped": "○",
        }
        icon = status_icons.get(result["status"], "?")

        print(f"  Status: {icon} {result['status'].upper()}")
        print(f"  URL: {result['url']}")
        print(f"  Authentication: {'Yes' if result['has_auth'] else 'No'}")

        if result["details"].get("message"):
            print(f"  Message: {result['details']['message']}")

        if result["details"].get("error"):
            print(f"  Error: {result['details']['error']}")

        if result["details"].get("warning"):
            print(f"  Warning: {result['details']['warning']}")

        if result["details"].get("detected_fields"):
            fields = result["details"]["detected_fields"]
            print(f"  Detected fields:")
            for field_name, field_value in fields.items():
                print(f"    - {field_name}: {field_value}")

        if result["details"].get("success_indicators"):
            indicators = result["details"]["success_indicators"]
            print(f"  Success indicators: {', '.join(indicators)}")

        if result["details"].get("all_fields"):
            print(
                f"  All form fields found: {', '.join(result['details']['all_fields'][:10])}"
            )
            if len(result["details"]["all_fields"]) > 10:
                print(f"    ... and {len(result['details']['all_fields']) - 10} more")

        print()

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    success_count = sum(1 for r in results if r["status"] in ["success", "ready"])
    error_count = sum(1 for r in results if r["status"] == "error")
    warning_count = sum(1 for r in results if r["status"] == "warning")

    print(f"Total sites: {len(results)}")
    print(f"✓ Ready/Success: {success_count}")
    print(f"⚠ Warnings: {warning_count}")
    print(f"✗ Errors: {error_count}")
    print()

    if error_count > 0:
        print("⚠ Fix errors before running the monitor")
    elif warning_count > 0:
        print("⚠ Review warnings - some sites may need manual configuration")
    else:
        print("✓ All sites are ready for monitoring!")
    print()


if __name__ == "__main__":
    main()
