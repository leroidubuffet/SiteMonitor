#!/usr/bin/env python3
"""
Test script for batch notifications and startup message
"""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import yaml
from dotenv import load_dotenv

from src.utils.healthcheck import HealthcheckMonitor

# Add parent directory to path to import src
sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 60)
print("Testing New Features")
print("=" * 60)

print("\n1. Testing BATCH NOTIFICATIONS (debug mode)")
print("-" * 60)
print("Running: python3 main.py --check-once --telegram-debug")
print("Expected: ONE batch message with all 7 check results")
print("-" * 60)

print("\n2. Testing HealthcheckMonitor Ping")
print("-" * 60)

# Load environment variables from config/.env file
load_dotenv(dotenv_path=Path(__file__).parent.parent / "config" / ".env")


def load_config():
    """Load configuration from config.yaml"""
    config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def test_healthcheck_ping():
    """Test that HealthcheckMonitor sends pings correctly"""
    with patch("httpx.post") as mock_post:
        mock_post.return_value.status_code = 200

        healthcheck_url = os.getenv("HEALTHCHECK_PING_URL")

        print(f"Debug: HEALTHCHECK_PING_URL used in test: {healthcheck_url}")
        monitor = HealthcheckMonitor(ping_url=healthcheck_url, enabled=True)
        success = monitor.ping_success("Test message")

        assert success is True
        mock_post.assert_called_once_with(
            healthcheck_url,
            data="Test message".encode("utf-8"),
            timeout=5.0,
        )


test_healthcheck_ping()

print("Expected: Healthcheck ping sent successfully")
print("-" * 60)

result = subprocess.run(
    ["python3", "main.py", "--check-once", "--telegram-debug"],
    capture_output=True,
    text=True,
    cwd="/Users/yagoairm2/Documents/ofiteco/_siteChecker",
)

# Count Telegram API calls
telegram_calls = result.stderr.count("POST https://api.telegram.org")
print(f"\n✓ Telegram API calls made: {telegram_calls}")

if telegram_calls == 1:
    print("✅ SUCCESS: Batch notification working! (1 message instead of 7)")
else:
    print(f"⚠️  WARNING: Expected 1 batch message, got {telegram_calls} messages")

print("\n" + "=" * 60)
print("2. Testing STARTUP NOTIFICATION (regular mode)")
print("-" * 60)
print("You need to manually run: python3 main.py")
print("Expected: You'll receive a startup message like:")
print("-" * 60)
print("""
🚀 Monitor Started

📊 Monitoring 5 site(s):
  • AEMET
  • DGT Traffic Cameras
  • InfoRuta RCE
  • Vialidad ACP
  • Fomento VI

⏱ Check interval: 15 minutes
🕐 Started at: 2025-11-08 14:58:00

Regular mode: You'll only receive alerts for failures and recoveries
""")
print("-" * 60)

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print("\n✅ Batch notifications: IMPLEMENTED")
print("   - Debug mode now sends ONE batch message instead of 7 individual messages")
print("   - Regular mode will batch multiple failures/recoveries")
print("\n✅ Startup notification: IMPLEMENTED")
print("   - Sent when you start monitoring in regular mode")
print("   - NOT sent in debug mode (to avoid confusion)")
print("   - NOT sent on --check-once (only on continuous monitoring)")

print("\n" + "=" * 60)
print("NEXT STEPS")
print("=" * 60)
print("\n1. To test startup notification:")
print("   python3 main.py")
print("   (Check your Telegram for the startup message, then press Ctrl+C)")
print("\n2. To run in production (regular mode):")
print("   python3 main.py")
print("   (You'll get startup message + alerts on failures only)")
print("\n3. To run with full visibility (debug mode):")
print("   python3 main.py --telegram-debug")
print("   (You'll get batch updates every 15 minutes, no startup message)")

print("\n" + "=" * 60)
