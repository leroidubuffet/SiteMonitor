#!/usr/bin/env python3
"""
Test script for Telegram notifier

Tests both regular and debug modes with sample check results.
"""

import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path to import src
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml

from src.checkers import CheckResult, CheckStatus
from src.notifiers import TelegramNotifier
from src.storage import CredentialManager


def load_config():
    """Load configuration from config.yaml"""
    config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def create_test_results():
    """Create sample check results for testing"""

    # Success result
    success_result = CheckResult(
        check_type="uptime",
        status=CheckStatus.SUCCESS,
        success=True,
        timestamp=datetime.now(),
        response_time_ms=245,
        status_code=200,
        details={"url": "https://www.aemet.es/"},
    )

    # Failure result
    failure_result = CheckResult(
        check_type="uptime",
        status=CheckStatus.FAILURE,
        success=False,
        timestamp=datetime.now(),
        response_time_ms=5000,
        error_message="Site did not respond within 30 seconds",
        details={"url": "https://inforuta-rce.es/"},
    )

    # Authentication success
    auth_success = CheckResult(
        check_type="authentication",
        status=CheckStatus.SUCCESS,
        success=True,
        timestamp=datetime.now(),
        response_time_ms=1823,
        details={"authenticated": True},
    )

    # Warning result
    warning_result = CheckResult(
        check_type="uptime",
        status=CheckStatus.WARNING,
        success=True,
        timestamp=datetime.now(),
        response_time_ms=3250,
        status_code=200,
        warning_message="Slow response time",
        details={"url": "https://vialidad.acpofiteco.com/"},
    )

    return [
        (success_result, None, "AEMET"),
        (failure_result, None, "InfoRuta RCE"),
        (auth_success, None, "InfoRuta RCE"),
        (warning_result, None, "Vialidad ACP"),
    ]


def test_regular_mode():
    """Test Telegram notifier in regular mode (state changes only)"""
    print("\n" + "=" * 60)
    print("Testing Telegram Notifier - REGULAR MODE")
    print("=" * 60)

    config = load_config()

    # Ensure regular mode
    if "notifications" not in config:
        config["notifications"] = {}
    if "telegram" not in config["notifications"]:
        config["notifications"]["telegram"] = {}
    config["notifications"]["telegram"]["debug_mode"] = False
    config["notifications"]["telegram"]["enabled"] = True

    credential_manager = CredentialManager()
    notifier = TelegramNotifier(config, credential_manager)

    if not notifier.enabled:
        print("✗ Telegram notifier is not enabled")
        print(
            "  Check that TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are set in config/.env"
        )
        return False

    print(f"✓ Telegram notifier initialized (Debug mode: {notifier.debug_mode})")
    print(
        f"  Bot token: {notifier.bot_token[:20]}..."
        if notifier.bot_token
        else "  No token"
    )
    print(f"  Chat ID: {notifier.chat_id}")

    # Test single notification (failure)
    print("\nSending test FAILURE notification...")
    results = create_test_results()
    failure_result, _, site = results[1]  # Get the failure result

    success = notifier.notify(failure_result, previous_result=None, site_name=site)

    if success:
        print("✓ Failure notification sent successfully")
    else:
        print("✗ Failed to send notification")
        return False

    # In regular mode, success notifications won't be sent without state change
    print("\nIn regular mode, success notifications are NOT sent (no state change)")
    print("This is expected behavior - only failures and recoveries are notified")

    return True


def test_debug_mode():
    """Test Telegram notifier in debug mode (all checks)"""
    print("\n" + "=" * 60)
    print("Testing Telegram Notifier - DEBUG MODE")
    print("=" * 60)

    config = load_config()

    # Enable debug mode
    if "notifications" not in config:
        config["notifications"] = {}
    if "telegram" not in config["notifications"]:
        config["notifications"]["telegram"] = {}
    config["notifications"]["telegram"]["debug_mode"] = True
    config["notifications"]["telegram"]["enabled"] = True

    credential_manager = CredentialManager()
    notifier = TelegramNotifier(config, credential_manager)

    if not notifier.enabled:
        print("✗ Telegram notifier is not enabled")
        return False

    print(f"✓ Telegram notifier initialized (Debug mode: {notifier.debug_mode})")

    # Test multiple notifications
    results = create_test_results()

    print(f"\nSending {len(results)} test notifications...")
    for i, (result, prev, site) in enumerate(results, 1):
        print(f"\n{i}. Sending {result.status.name} notification for {site}...")
        success = notifier.notify(result, previous_result=prev, site_name=site)

        if success:
            print(f"   ✓ Sent successfully")
        else:
            print(f"   ✗ Failed to send")
            return False

    return True


def test_batch_notifications():
    """Test batch notification feature"""
    print("\n" + "=" * 60)
    print("Testing Telegram Notifier - BATCH MODE")
    print("=" * 60)

    config = load_config()

    # Enable debug mode for batch testing
    if "notifications" not in config:
        config["notifications"] = {}
    if "telegram" not in config["notifications"]:
        config["notifications"]["telegram"] = {}
    config["notifications"]["telegram"]["debug_mode"] = True
    config["notifications"]["telegram"]["enabled"] = True
    config["notifications"]["telegram"]["batch_notifications"] = True

    credential_manager = CredentialManager()
    notifier = TelegramNotifier(config, credential_manager)

    if not notifier.enabled:
        print("✗ Telegram notifier is not enabled")
        return False

    print(f"✓ Telegram notifier initialized (Batch mode: {notifier.batch_enabled})")

    # Send batch notification
    results = create_test_results()
    print(f"\nSending batch notification with {len(results)} results...")

    success = notifier.notify_batch(results)

    if success:
        print("✓ Batch notification sent successfully")
    else:
        print("✗ Failed to send batch notification")
        return False

    return True


def main():
    """Main test runner"""
    print("""
    ╔═══════════════════════════════════════════════════════╗
    ║        Telegram Notifier Test Suite                  ║
    ║                                                       ║
    ║  This script tests the Telegram integration by       ║
    ║  sending sample notifications to your configured bot ║
    ╚═══════════════════════════════════════════════════════╝
    """)

    # Check credentials
    print("Checking credentials...")
    credential_manager = CredentialManager()
    telegram_creds = credential_manager.get_telegram_credentials()

    if not telegram_creds.get("bot_token") or not telegram_creds.get("chat_id"):
        print("\n✗ ERROR: Telegram credentials not configured")
        print("\nPlease add the following to config/.env:")
        print("  TELEGRAM_BOT_TOKEN=your_bot_token")
        print("  TELEGRAM_CHAT_ID=your_chat_id")
        print("\nSee README.md for setup instructions")
        sys.exit(1)

    print("✓ Credentials found")

    # Run tests
    tests = [
        ("Regular Mode", test_regular_mode),
        ("Debug Mode", test_debug_mode),
        ("Batch Notifications", test_batch_notifications),
    ]

    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\n✗ Test failed with error: {e}")
            import traceback

            traceback.print_exc()
            results[test_name] = False

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{status}: {test_name}")

    print("=" * 60)

    all_passed = all(results.values())
    if all_passed:
        print("\n✓ All tests passed!")
        print("\nYou should have received notifications in your Telegram chat.")
        print("If not, check:")
        print("  1. Bot token is correct")
        print("  2. Chat ID is correct")
        print("  3. You've sent at least one message to the bot")
        print("  4. Logs at logs/monitor.log for errors")
    else:
        print("\n✗ Some tests failed")
        print("Check logs/monitor.log for details")
        sys.exit(1)


if __name__ == "__main__":
    main()
