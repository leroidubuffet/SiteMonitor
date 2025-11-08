#!/usr/bin/env python3
"""
InfoRuta Website Monitor

Monitor the availability and health of https://inforuta-rce.es/
with authentication support and comprehensive alerting.
"""

import argparse
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.monitor import Monitor
from src.storage import CredentialManager


def setup_credentials():
    """Interactive credential setup."""
    print("\n" + "=" * 60)
    print("InfoRuta Monitor - Credential Setup")
    print("=" * 60 + "\n")

    credential_manager = CredentialManager()

    # InfoRuta credentials
    print("InfoRuta Login Credentials")
    print("-" * 30)
    username = input("Enter InfoRuta username: ").strip()
    password = input("Enter InfoRuta password: ").strip()

    if username and password:
        # Store in environment for this session
        os.environ["INFORUTA_USERNAME"] = username
        os.environ["INFORUTA_PASSWORD"] = password
        print("✓ InfoRuta credentials configured")
    else:
        print("⚠ InfoRuta credentials skipped")

    print()

    # Email credentials (optional)
    setup_email = input("Set up email notifications? (y/n): ").strip().lower() == "y"

    if setup_email:
        print("\nEmail Configuration")
        print("-" * 30)
        from_email = input("Enter sender email address: ").strip()
        to_email = input("Enter recipient email address: ").strip()
        email_password = input("Enter email password/app password: ").strip()

        if all([from_email, to_email, email_password]):
            os.environ["EMAIL_FROM"] = from_email
            os.environ["EMAIL_TO"] = to_email
            os.environ["EMAIL_PASSWORD"] = email_password
            print("✓ Email notifications configured")

            # Update config to enable email
            config_path = Path(__file__).parent / "config" / "config.yaml"
            if config_path.exists():
                import yaml

                with open(config_path, "r") as f:
                    config = yaml.safe_load(f)
                config["notifications"]["email"]["enabled"] = True
                with open(config_path, "w") as f:
                    yaml.dump(config, f, default_flow_style=False)
        else:
            print("⚠ Email configuration skipped")

    print("\n" + "=" * 60)
    print("Credential setup complete!")
    print("=" * 60 + "\n")


def check_once(config_path: str, env_file: str = None, telegram_debug: bool = False):
    """Run a single check and exit."""
    print("\n" + "=" * 60)
    print("InfoRuta Monitor - Single Check")
    print("=" * 60 + "\n")

    monitor = Monitor(config_path, env_file, telegram_debug)
    monitor.perform_checks()

    # Display status
    status = monitor.get_status()
    metrics = status["metrics"]["availability"]

    print("\n" + "=" * 60)
    print("Check Complete")
    print("-" * 60)
    print(f"Availability: {metrics['availability_percentage']:.2f}%")
    print(f"Success Rate: {metrics['success_rate']:.2f}%")
    print("=" * 60 + "\n")


def test_connection(config_path: str, env_file: str = None):
    """Test connection and credentials."""
    print("\n" + "=" * 60)
    print("InfoRuta Monitor - Connection Test")
    print("=" * 60 + "\n")

    import yaml

    from src.checkers import AuthChecker, UptimeChecker
    from src.storage import CredentialManager

    # Load config
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Test uptime
    print("Testing basic connectivity...")
    uptime_checker = UptimeChecker(config)
    uptime_result = uptime_checker.check()

    if uptime_result.success:
        print(
            f"✓ Site is reachable (Response time: {uptime_result.response_time_ms:.0f}ms)"
        )
    else:
        print(f"✗ Site is not reachable: {uptime_result.error_message}")
        return

    # Test authentication if credentials are available
    credential_manager = CredentialManager(env_file)
    creds = credential_manager.get_inforuta_credentials()

    if creds.get("username") and creds.get("password"):
        print("\nTesting authentication...")
        auth_checker = AuthChecker(config, credential_manager=credential_manager)
        auth_result = auth_checker.check()

        if auth_result.success:
            print(
                f"✓ Authentication successful (Response time: {auth_result.response_time_ms:.0f}ms)"
            )
        else:
            print(f"✗ Authentication failed: {auth_result.error_message}")
    else:
        print("\n⚠ No credentials configured, skipping authentication test")

    print("\n" + "=" * 60 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="InfoRuta Website Monitor - Monitor https://inforuta-rce.es/ availability",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start monitoring with default config
  python main.py

  # Use custom config file
  python main.py --config my_config.yaml

  # Use custom .env file
  python main.py --env-file production.env

  # Set up credentials interactively
  python main.py --setup

  # Run a single check
  python main.py --check-once

  # Test connection and credentials
  python main.py --test
        """,
    )

    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="Path to configuration file (default: config/config.yaml)",
    )

    parser.add_argument("--env-file", help="Path to .env file with credentials")

    parser.add_argument(
        "--setup", action="store_true", help="Interactive credential setup"
    )

    parser.add_argument(
        "--check-once", action="store_true", help="Run a single check and exit"
    )

    parser.add_argument(
        "--test", action="store_true", help="Test connection and credentials"
    )

    parser.add_argument(
        "--version", action="version", version="InfoRuta Monitor v1.0.0"
    )

    parser.add_argument(
        "--telegram-debug",
        action="store_true",
        help="Enable Telegram debug mode (notify on ALL checks, not just state changes)",
    )

    args = parser.parse_args()

    # Handle special modes
    if args.setup:
        setup_credentials()
        return

    if args.test:
        test_connection(args.config, args.env_file)
        return

    if args.check_once:
        check_once(args.config, args.env_file, args.telegram_debug)
        return

    # Start monitoring
    print("""
    ╔═══════════════════════════════════════════════════════╗
    ║           Vialidad Website Monitor v1.0.0             ║
    ║                                                       ║
    ║  Monitoring:                                          ║
    ║   https://inforuta-rce.es/                            ║
    ║   https://www.aemet.es/                               ║
    ║   https://www.dgt.es/                                 ║
    ║   https://vialidad.acpofiteco.com/                    ║
    ║   https://www.fomento-vi.es/                          ║
    ║  Interval: Every 15 minutes                           ║
    ║  Press Ctrl+C to stop                                 ║
    ╚═══════════════════════════════════════════════════════╝
    """)

    try:
        monitor = Monitor(args.config, args.env_file, args.telegram_debug)
        monitor.start()
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
