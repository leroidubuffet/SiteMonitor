"""
Comprehensive SSRF Protection Tests

Tests for Server-Side Request Forgery (SSRF) protection across all checkers.
"""

import pytest
from unittest.mock import Mock, patch
from src.checkers import UptimeChecker, AuthChecker, HealthChecker, SSRFProtectionError
from src.storage import CredentialManager
from src.utils import ConfigValidator, ConfigValidationError


class TestSSRFProtectionBaseChecker:
    """Test SSRF protection in BaseChecker (applies to all checkers)."""

    def test_blocks_localhost_127001(self):
        """Test that 127.0.0.1 is blocked."""
        config = {
            "monitoring": {"url": "http://127.0.0.1"},
            "checks": {"uptime": {"endpoints": ["/"]}},
        }
        checker = UptimeChecker(config)

        with pytest.raises(SSRFProtectionError, match="Localhost addresses are not allowed"):
            checker._validate_url("http://127.0.0.1")

    def test_blocks_localhost_name(self):
        """Test that localhost hostname is blocked."""
        checker = UptimeChecker({})

        with pytest.raises(SSRFProtectionError, match="Localhost addresses are not allowed"):
            checker._validate_url("http://localhost:8080")

    def test_blocks_ipv6_loopback(self):
        """Test that IPv6 loopback (::1) is blocked."""
        checker = UptimeChecker({})

        with pytest.raises(SSRFProtectionError, match="Localhost addresses are not allowed"):
            checker._validate_url("http://[::1]")

    def test_blocks_127_range(self):
        """Test that entire 127.x.x.x range is blocked."""
        checker = UptimeChecker({})

        for addr in ["127.0.0.1", "127.1.1.1", "127.255.255.255"]:
            with pytest.raises(SSRFProtectionError, match="Localhost"):
                checker._validate_url(f"http://{addr}")

    def test_blocks_private_ip_10(self):
        """Test that 10.x.x.x private range is blocked."""
        checker = UptimeChecker({})

        with pytest.raises(SSRFProtectionError, match="Private IP"):
            checker._validate_url("http://10.0.0.1")

    def test_blocks_private_ip_192168(self):
        """Test that 192.168.x.x private range is blocked."""
        checker = UptimeChecker({})

        with pytest.raises(SSRFProtectionError, match="Private IP"):
            checker._validate_url("http://192.168.1.1")

    def test_blocks_private_ip_172(self):
        """Test that 172.16-31.x.x private range is blocked."""
        checker = UptimeChecker({})

        for i in range(16, 32):
            with pytest.raises(SSRFProtectionError, match="Private IP"):
                checker._validate_url(f"http://172.{i}.0.1")

    def test_blocks_aws_metadata(self):
        """Test that AWS metadata endpoint (169.254.169.254) is blocked."""
        checker = UptimeChecker({})

        with pytest.raises(SSRFProtectionError, match="Cloud metadata"):
            checker._validate_url("http://169.254.169.254/latest/meta-data/")

    def test_blocks_gcp_metadata(self):
        """Test that GCP metadata endpoint is blocked."""
        checker = UptimeChecker({})

        with pytest.raises(SSRFProtectionError, match="Cloud metadata"):
            checker._validate_url("http://metadata.google.internal")

    def test_blocks_generic_metadata_hostnames(self):
        """Test that generic metadata hostnames are blocked."""
        checker = UptimeChecker({})

        for hostname in ["metadata", "instance-data"]:
            with pytest.raises(SSRFProtectionError, match="Cloud metadata"):
                checker._validate_url(f"http://{hostname}/")

    def test_blocks_link_local_169254(self):
        """Test that link-local addresses (169.254.x.x) are blocked."""
        checker = UptimeChecker({})

        with pytest.raises(SSRFProtectionError, match="Cloud metadata"):
            checker._validate_url("http://169.254.1.1")

    def test_blocks_ipv6_unique_local(self):
        """Test that IPv6 Unique Local Addresses (fc00::/7) are blocked."""
        checker = UptimeChecker({})

        with pytest.raises(SSRFProtectionError, match="(Unique Local|Private IP)"):
            checker._validate_url("http://[fc00::1]")

    def test_blocks_ipv6_mapped_ipv4_private(self):
        """Test that IPv6-mapped private IPv4 addresses are blocked."""
        checker = UptimeChecker({})

        with pytest.raises(SSRFProtectionError, match="(IPv6-mapped private|Private IP)"):
            checker._validate_url("http://[::ffff:192.168.1.1]")

    def test_blocks_invalid_schemes(self):
        """Test that non-HTTP/HTTPS schemes are blocked."""
        checker = UptimeChecker({})

        for scheme in ["file", "ftp", "gopher", "dict", "data"]:
            with pytest.raises(SSRFProtectionError, match="Invalid URL scheme"):
                checker._validate_url(f"{scheme}:///etc/passwd")

    def test_blocks_missing_hostname(self):
        """Test that URLs without hostname are blocked."""
        checker = UptimeChecker({})

        with pytest.raises(SSRFProtectionError, match="must have a valid hostname"):
            checker._validate_url("http://")

    def test_allows_public_ip(self):
        """Test that public IP addresses are allowed."""
        checker = UptimeChecker({})

        # Google DNS - public IP
        assert checker._validate_url("http://8.8.8.8", validate_dns=False) is True

    def test_allows_public_hostname(self):
        """Test that public hostnames are allowed (without DNS validation)."""
        checker = UptimeChecker({})

        assert checker._validate_url("https://www.google.com", validate_dns=False) is True

    @patch('socket.gethostbyname')
    def test_dns_rebinding_protection(self, mock_dns):
        """Test that DNS rebinding attacks are detected."""
        checker = UptimeChecker({})

        # Simulate DNS resolving to private IP
        mock_dns.return_value = "192.168.1.1"

        with pytest.raises(SSRFProtectionError, match="resolves to private IP"):
            checker._validate_url("http://attacker.com", validate_dns=True)

    @patch('socket.gethostbyname')
    def test_dns_validation_allows_public_ip(self, mock_dns):
        """Test that DNS validation allows hostnames resolving to public IPs."""
        checker = UptimeChecker({})

        # Simulate DNS resolving to public IP
        mock_dns.return_value = "8.8.8.8"

        assert checker._validate_url("http://example.com", validate_dns=True) is True

    def test_multicast_blocked(self):
        """Test that multicast addresses are blocked."""
        checker = UptimeChecker({})

        with pytest.raises(SSRFProtectionError, match="Multicast"):
            checker._validate_url("http://224.0.0.1")


class TestSSRFProtectionUptimeChecker:
    """Test SSRF protection specifically in UptimeChecker."""

    def test_uptime_check_blocks_localhost(self):
        """Test that uptime check blocks localhost URLs."""
        config = {
            "monitoring": {"url": "http://127.0.0.1"},
            "checks": {"uptime": {"endpoints": ["/"], "expected_status": [200]}},
        }
        checker = UptimeChecker(config)

        result = checker.check()

        assert result.success is False
        assert "SSRF protection blocked" in result.error_message

    def test_uptime_check_blocks_private_ip(self):
        """Test that uptime check blocks private IPs."""
        config = {
            "monitoring": {"url": "http://192.168.1.1"},
            "checks": {"uptime": {"endpoints": ["/"], "expected_status": [200]}},
        }
        checker = UptimeChecker(config)

        result = checker.check()

        assert result.success is False
        assert "SSRF protection blocked" in result.error_message


class TestSSRFProtectionAuthChecker:
    """Test SSRF protection in AuthChecker."""

    def test_auth_check_blocks_localhost(self):
        """Test that auth check blocks localhost URLs."""
        config = {
            "monitoring": {"url": "http://localhost"},
            "checks": {"authentication": {"enabled": True, "login_endpoint": "/"}},
        }
        site_config = {
            "url": "http://localhost",
            "credential_key": "test",
            "authentication": {"enabled": True, "login_endpoint": "/"},
        }

        credential_manager = Mock(spec=CredentialManager)
        credential_manager.get_credentials_by_key.return_value = {
            "username": "test",
            "password": "test"
        }
        credential_manager.mask_credential.return_value = "tes***"

        checker = AuthChecker(config, credential_manager=credential_manager, site_config=site_config)
        result = checker.check()

        assert result.success is False
        assert "Invalid or unsafe URL" in result.error_message or "SSRF" in result.error_message


class TestSSRFProtectionHealthChecker:
    """Test SSRF protection in HealthChecker."""

    def test_health_check_blocks_private_ip(self):
        """Test that health check blocks private IPs."""
        config = {
            "monitoring": {"url": "http://10.0.0.1"},
            "checks": {"health": {"enabled": True, "protected_endpoint": "/health"}},
        }

        # Mock auth checker with session
        auth_checker = Mock()
        auth_checker.session_cookies = {"session": "test"}

        checker = HealthChecker(config, auth_checker=auth_checker)
        result = checker.check()

        assert result.success is False
        assert "SSRF protection blocked" in result.error_message


class TestConfigValidation:
    """Test configuration validation for SSRF protection."""

    def test_config_validator_blocks_localhost(self):
        """Test that config validator blocks localhost URLs."""
        with pytest.raises(ConfigValidationError, match="Localhost"):
            ConfigValidator.validate_url("http://localhost", "test_url")

    def test_config_validator_blocks_private_ip(self):
        """Test that config validator blocks private IPs."""
        with pytest.raises(ConfigValidationError, match="Private"):
            ConfigValidator.validate_url("http://192.168.1.1", "test_url")

    def test_config_validator_blocks_metadata(self):
        """Test that config validator blocks cloud metadata endpoints."""
        with pytest.raises(ConfigValidationError, match="metadata"):
            ConfigValidator.validate_url("http://169.254.169.254", "test_url")

    def test_config_validator_allows_public_url(self):
        """Test that config validator allows public URLs."""
        # Should not raise exception
        ConfigValidator.validate_url("https://www.example.com", "test_url")

    def test_validate_site_config_invalid_url(self):
        """Test that site validation catches invalid URLs."""
        site = {
            "name": "Test Site",
            "url": "http://localhost",
            "checks_enabled": ["uptime"]
        }

        with pytest.raises(ConfigValidationError, match="Localhost"):
            ConfigValidator.validate_site_config(site, 0)

    def test_validate_full_config_invalid_site_url(self):
        """Test that full config validation catches invalid site URLs."""
        config = {
            "sites": [
                {
                    "name": "Malicious",
                    "url": "http://169.254.169.254",
                    "checks_enabled": ["uptime"]
                }
            ]
        }

        with pytest.raises(ConfigValidationError, match="metadata"):
            ConfigValidator.validate_config(config)

    def test_validate_full_config_duplicate_names(self):
        """Test that duplicate site names are caught."""
        config = {
            "sites": [
                {"name": "Site1", "url": "https://example.com"},
                {"name": "Site1", "url": "https://example.org"}
            ]
        }

        with pytest.raises(ConfigValidationError, match="Duplicate"):
            ConfigValidator.validate_config(config)

    def test_validate_full_config_valid(self):
        """Test that valid configuration passes."""
        config = {
            "sites": [
                {
                    "name": "Site1",
                    "url": "https://www.example.com",
                    "checks_enabled": ["uptime"]
                }
            ]
        }

        warnings = ConfigValidator.validate_config(config)
        assert isinstance(warnings, list)


class TestRedirectValidation:
    """Test that redirects are validated for SSRF."""

    @patch('httpx.Client.get')
    def test_redirect_to_private_ip_blocked(self, mock_get):
        """Test that redirects to private IPs are blocked."""
        # Mock response with redirect to private IP
        mock_response = Mock()
        mock_response.is_redirect = True
        mock_response.headers = {'location': 'http://192.168.1.1'}
        mock_response.history = [mock_response]

        mock_get.return_value = mock_response

        checker = UptimeChecker({})

        with pytest.raises(SSRFProtectionError, match="(SSRF protection blocked redirect|Private IP)"):
            checker._make_request('get', 'https://example.com')

    def test_validate_redirect_relative_url(self):
        """Test that relative redirect URLs are resolved correctly."""
        checker = UptimeChecker({})

        # Relative redirect should be resolved against base URL
        base_url = "https://www.example.com/path"
        relative_redirect = "/new-path"

        # Should not raise exception (example.com is public)
        result = checker._validate_redirect_url(relative_redirect, base_url)
        assert result is True

    def test_validate_redirect_relative_to_private_blocked(self):
        """Test that relative redirects on private IPs are blocked."""
        checker = UptimeChecker({})

        # Even with relative redirect, if base URL is private, should be blocked
        base_url = "http://192.168.1.1/page"
        relative_redirect = "/admin"

        with pytest.raises(SSRFProtectionError, match="Private IP"):
            checker._validate_redirect_url(relative_redirect, base_url)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
