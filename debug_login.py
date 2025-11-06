#!/usr/bin/env python3
"""Debug script to test InfoRuta login."""

import httpx
import re
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from src.storage import CredentialManager


def main():
    # Get credentials
    cm = CredentialManager()
    creds = cm.get_inforuta_credentials()

    if not creds.get("username") or not creds.get("password"):
        print("❌ No credentials found")
        return

    print(f"✓ Using username: {creds['username'][:3]}***")
    print(f"✓ Using password: ***")
    print()

    # Create client
    client = httpx.Client(timeout=30.0, follow_redirects=True)

    # Get login page
    url = "https://inforuta-rce.es/"
    print(f"Fetching: {url}")
    response = client.get(url)
    print(f"Status: {response.status_code}")
    print()

    # Extract form fields
    print("Extracting form fields...")
    html = response.text

    # Find all input fields in the form
    inputs = re.findall(r"<input[^>]*>", html, re.IGNORECASE)
    form_fields = {}

    print("Found input fields:")
    for inp in inputs:
        name_match = re.search(r'name=["\']([^"\']+)["\']', inp)
        value_match = re.search(r'value=["\']([^"\']*)["\']', inp)
        type_match = re.search(r'type=["\']([^"\']+)["\']', inp)

        if name_match:
            name = name_match.group(1)
            value = value_match.group(1) if value_match else ""
            field_type = type_match.group(1) if type_match else "text"

            form_fields[name] = value

            # Show non-hidden fields
            if field_type not in ["hidden"]:
                print(f"  - {name} (type: {field_type})")

    print()
    print("Looking for username/password field names...")

    # Look for username/password fields
    username_fields = [
        k for k in form_fields.keys() if "user" in k.lower() or "usuario" in k.lower()
    ]
    password_fields = [
        k for k in form_fields.keys() if "pass" in k.lower() or "pwd" in k.lower()
    ]
    button_fields = [
        k for k in form_fields.keys() if "btn" in k.lower() or "button" in k.lower()
    ]

    print(f"Potential username fields: {username_fields}")
    print(f"Potential password fields: {password_fields}")
    print(f"Potential button fields: {button_fields}")
    print()

    # Show ViewState fields
    viewstate_fields = [k for k in form_fields.keys() if "VIEW" in k or "EVENT" in k]
    print(f"ASP.NET ViewState fields: {viewstate_fields}")
    print()

    # Try to find the form action
    form_match = re.search(r'<form[^>]*action=["\']([^"\']*)["\']', html, re.IGNORECASE)
    if form_match:
        print(f"Form action: {form_match.group(1)}")
    else:
        print("Form action: (not found - probably posts to same URL)")

    print()
    print("=" * 60)
    print("Full form data that would be submitted:")
    for key, value in sorted(form_fields.items()):
        if len(value) > 50:
            print(f"  {key}: {value[:50]}...")
        else:
            print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
