# Credential Management Guide

## Table of Contents
- [Overview](#overview)
- [Problems with .env Files](#problems-with-env-files)
- [Secure Alternatives](#secure-alternatives)
  - [Option 1: Systemd Environment Variables](#option-1-systemd-environment-variables-simple--secure)
  - [Option 2: Encrypted Secrets with SOPS/Age](#option-2-encrypted-secrets-with-sopsage-good-balance)
  - [Option 3: Cloud Secret Manager](#option-3-cloud-secret-manager-enterprise-grade)
  - [Option 4: Password Manager CLI](#option-4-password-manager-cli-practical)
- [Recommendation](#recommendation)
- [Implementation Guide](#implementation-guide)

## Overview

This guide explains secure credential management approaches for deploying the Multi-Site Website Monitor, especially for production environments like Raspberry Pi deployments. While `.env` files are convenient for development, they present significant security risks in production.

## Problems with .env Files

### Security Concerns

1. **Plaintext Storage**
   - Credentials stored in plain text on filesystem
   - Anyone with filesystem access can read all secrets
   - No protection if device is compromised or stolen

2. **No Audit Trail**
   - Cannot track who accessed credentials
   - No logging of credential usage
   - Difficult to detect unauthorized access

3. **No Rotation Support**
   - Updating credentials requires manual file edits
   - No automated rotation workflows
   - Risk of outdated credentials

4. **Accidental Exposure**
   - Easy to accidentally commit to git repositories
   - Can be included in backups uploaded to cloud
   - May be visible in process listings or logs

5. **Physical Access Risk**
   - If someone steals the Raspberry Pi, they have all credentials
   - No additional security layer beyond filesystem permissions
   - Difficult to revoke access after device loss

## Secure Alternatives

### Option 1: Systemd Environment Variables (Simple & Secure)

**Best for**: Single deployment, moderate security needs, quick improvement over .env

#### Overview
Use systemd service configuration to manage credentials with strict file permissions outside the application directory.

#### Implementation

**Step 1: Create systemd service file**

```bash
sudo nano /etc/systemd/system/site-monitor.service
```

```ini
[Unit]
Description=Multi-Site Website Monitor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=monitor
Group=monitor
WorkingDirectory=/home/monitor/siteChecker
EnvironmentFile=/etc/site-monitor/credentials.conf
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=10

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/home/monitor/siteChecker/logs

[Install]
WantedBy=multi-user.target
```

**Step 2: Create secure credentials file**

```bash
# Create directory
sudo mkdir -p /etc/site-monitor

# Create credentials file
sudo nano /etc/site-monitor/credentials.conf
```

```bash
# /etc/site-monitor/credentials.conf
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
HEALTHCHECK_PING_URL=https://hc-ping.com/your-uuid

# Site credentials
INFORUTA_USERNAME=username
INFORUTA_PASSWORD=password
FOMENTO_USERNAME=username
FOMENTO_PASSWORD=password
SKADE_USERNAME=username
SKADE_PASSWORD=password
```

**Step 3: Secure the credentials file**

```bash
# Set strict permissions (only root can read)
sudo chmod 600 /etc/site-monitor/credentials.conf
sudo chown root:root /etc/site-monitor/credentials.conf
```

**Step 4: Create service user**

```bash
# Create dedicated user for running the service
sudo useradd -r -s /bin/false monitor
sudo chown -R monitor:monitor /home/monitor/siteChecker
```

**Step 5: Enable and start service**

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable site-monitor.service

# Start service
sudo systemctl start site-monitor.service

# Check status
sudo systemctl status site-monitor.service

# View logs
sudo journalctl -u site-monitor.service -f
```

#### Advantages
- Credentials separated from application code
- Strict file permissions (600, root-only access)
- Service management with automatic restart
- Survives system reboots
- System-level security hardening options
- No code changes required

#### Disadvantages
- Still plaintext storage (but with better permissions)
- Requires root access to update credentials
- Manual rotation process
- No audit trail
- Single point of failure if system is compromised

#### Rotation Workflow

```bash
# 1. Edit credentials (as root)
sudo nano /etc/site-monitor/credentials.conf

# 2. Restart service to pick up changes
sudo systemctl restart site-monitor.service
```

---

### Option 2: Encrypted Secrets with SOPS/Age (Good Balance)

**Best for**: Multiple deployments, good security, version control, audit trail

#### Overview
Use Mozilla SOPS (Secrets OPerationS) with Age encryption to encrypt credentials at rest. Encrypted files can be safely committed to git and decrypted at runtime.

#### Implementation

**Step 1: Install dependencies**

```bash
# Install Age encryption tool
sudo apt-get update
sudo apt-get install age

# Install SOPS (check latest version at https://github.com/mozilla/sops/releases)
wget https://github.com/mozilla/sops/releases/latest/download/sops-v3.8.1.linux.arm64
sudo mv sops-* /usr/local/bin/sops
sudo chmod +x /usr/local/bin/sops
```

**Step 2: Generate encryption key**

```bash
# Create directory for keys
sudo mkdir -p /etc/site-monitor

# Generate age key pair
age-keygen -o /etc/site-monitor/key.txt

# Output will show public key - save this for reference
# Public key: age1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Secure the private key
sudo chmod 400 /etc/site-monitor/key.txt
sudo chown root:root /etc/site-monitor/key.txt
```

**IMPORTANT**: Backup the key file to a secure location (USB drive, password manager, etc.). Without this key, you cannot decrypt your secrets.

**Step 3: Create secrets file**

```bash
cd /home/monitor/siteChecker

# Create unencrypted secrets file
cat > config/secrets.yaml <<EOF
# Notification credentials
telegram_bot_token: "your_token_here"
telegram_chat_id: "your_chat_id_here"
healthcheck_ping_url: "https://hc-ping.com/your-uuid"

# Site credentials
credentials:
  inforuta:
    username: "username"
    password: "password"
  fomento:
    username: "username"
    password: "password"
  skade:
    username: "username"
    password: "password"
EOF
```

**Step 4: Configure SOPS**

```bash
# Create SOPS configuration
cat > config/.sops.yaml <<EOF
creation_rules:
  - path_regex: secrets\.yaml$
    age: age1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx  # Your public key
EOF
```

**Step 5: Encrypt the secrets file**

```bash
# Set key file location
export SOPS_AGE_KEY_FILE=/etc/site-monitor/key.txt

# Encrypt the file in place
sops -e -i config/secrets.yaml

# The file is now encrypted! You can safely commit it to git
git add config/secrets.yaml
```

**Step 6: Update credential manager code**

Create a new file `src/storage/encrypted_credential_manager.py`:

```python
"""
Encrypted credential manager using SOPS for decryption.
"""
import subprocess
import yaml
import logging
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class EncryptedCredentialManager:
    """Manages credentials encrypted with SOPS."""

    def __init__(self, secrets_file: str = "config/secrets.yaml"):
        """
        Initialize the encrypted credential manager.

        Args:
            secrets_file: Path to SOPS-encrypted secrets file
        """
        self.secrets_file = Path(secrets_file)
        self._secrets_cache: Optional[Dict] = None

        if not self.secrets_file.exists():
            raise FileNotFoundError(f"Secrets file not found: {secrets_file}")

    def _decrypt_secrets(self) -> Dict:
        """
        Decrypt secrets using SOPS.

        Returns:
            Decrypted secrets as dictionary
        """
        try:
            result = subprocess.run(
                ["sops", "-d", str(self.secrets_file)],
                capture_output=True,
                text=True,
                check=True
            )
            return yaml.safe_load(result.stdout)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to decrypt secrets: {e.stderr}")
            raise
        except FileNotFoundError:
            logger.error("SOPS not found. Install with: sudo apt-get install sops")
            raise

    def _load_secrets(self) -> Dict:
        """Load and cache decrypted secrets."""
        if self._secrets_cache is None:
            self._secrets_cache = self._decrypt_secrets()
        return self._secrets_cache

    def get_credential(self, credential_key: str, field: str) -> str:
        """
        Get a credential for a specific site.

        Args:
            credential_key: The credential key (e.g., "inforuta", "skade")
            field: The field to retrieve ("username" or "password")

        Returns:
            The credential value
        """
        secrets = self._load_secrets()

        try:
            return secrets["credentials"][credential_key][field]
        except KeyError:
            logger.error(f"Credential not found: {credential_key}.{field}")
            raise

    def get_telegram_token(self) -> str:
        """Get Telegram bot token."""
        return self._load_secrets()["telegram_bot_token"]

    def get_telegram_chat_id(self) -> str:
        """Get Telegram chat ID."""
        return self._load_secrets()["telegram_chat_id"]

    def get_healthcheck_url(self) -> str:
        """Get Healthchecks.io ping URL."""
        return self._load_secrets()["healthcheck_ping_url"]
```

**Step 7: Update existing credential manager**

Modify `src/storage/credential_manager.py` to support both methods:

```python
import os
from typing import Optional

class CredentialManager:
    """Manages credentials with fallback to .env files."""

    def __init__(self, use_encrypted: bool = False, secrets_file: Optional[str] = None):
        """
        Initialize credential manager.

        Args:
            use_encrypted: If True, use SOPS-encrypted secrets
            secrets_file: Path to encrypted secrets file (if use_encrypted=True)
        """
        self.encrypted_manager = None

        if use_encrypted:
            from .encrypted_credential_manager import EncryptedCredentialManager
            self.encrypted_manager = EncryptedCredentialManager(secrets_file)

    def get_credential(self, credential_key: str, field: str) -> Optional[str]:
        """Get credential from encrypted file or environment variable."""
        if self.encrypted_manager:
            return self.encrypted_manager.get_credential(credential_key, field)

        # Fallback to environment variables
        env_var = f"{credential_key.upper()}_{field.upper()}"
        return os.getenv(env_var)
```

**Step 8: Set up systemd service for SOPS**

```bash
sudo nano /etc/systemd/system/site-monitor.service
```

```ini
[Unit]
Description=Multi-Site Website Monitor
After=network-online.target

[Service]
Type=simple
User=monitor
WorkingDirectory=/home/monitor/siteChecker
Environment="SOPS_AGE_KEY_FILE=/etc/site-monitor/key.txt"
ExecStart=/usr/bin/python3 main.py --use-encrypted-secrets
Restart=always

[Install]
WantedBy=multi-user.target
```

#### Advantages
- Encrypted at rest (secrets safe even if filesystem is compromised)
- Can commit encrypted files to git
- Version control for secrets (track changes, rollback)
- Supports multiple environments (dev, prod)
- Audit trail (git history shows who changed what)
- Easy rotation workflow
- Can share with team (each member has own decryption key)

#### Disadvantages
- Requires key management (must backup encryption key)
- Slightly more complex setup
- Decryption adds minimal runtime overhead
- Requires SOPS binary available

#### Rotation Workflow

```bash
# 1. Decrypt and edit secrets
export SOPS_AGE_KEY_FILE=/etc/site-monitor/key.txt
sops config/secrets.yaml  # Opens in editor, auto-encrypts on save

# 2. Commit changes (optional)
git add config/secrets.yaml
git commit -m "Update credentials"

# 3. Restart service
sudo systemctl restart site-monitor.service
```

---

### Option 3: Cloud Secret Manager (Enterprise Grade)

**Best for**: Professional deployments, multiple services, compliance requirements

#### Overview
Use a managed secret management service that provides encryption, centralized management, audit logs, and access control.

#### Options

**Free/Self-Hosted**:
- **Infisical** (self-hosted or cloud, free tier)
- **HashiCorp Vault** (self-hosted, open source)
- **AWS Secrets Manager** (free tier: 30-day trial)

**Commercial with Free Tiers**:
- **Doppler** (free for personal projects)
- **Google Secret Manager** (free tier: 6 secrets)
- **Azure Key Vault** (pay-per-use, very cheap)

#### Implementation Example: Infisical

**Step 1: Set up Infisical**

```bash
# Option A: Use Infisical Cloud (easiest)
# Sign up at https://infisical.com
# Create project and environment

# Option B: Self-host with Docker
docker run -d \
  --name infisical \
  -p 8080:8080 \
  infisical/infisical:latest
```

**Step 2: Install Python SDK**

```bash
pip install infisical-python
```

**Step 3: Create secrets in Infisical UI**

```
Project: Site Monitor
Environment: production

Secrets:
- TELEGRAM_BOT_TOKEN = your_token
- TELEGRAM_CHAT_ID = your_id
- INFORUTA_USERNAME = username
- INFORUTA_PASSWORD = password
- SKADE_USERNAME = username
- SKADE_PASSWORD = password
```

**Step 4: Create secret manager credential provider**

Create `src/storage/secret_manager_provider.py`:

```python
"""
Secret manager credential provider using Infisical.
"""
import logging
from typing import Optional
from infisical import InfisicalClient

logger = logging.getLogger(__name__)


class SecretManagerProvider:
    """Manages credentials using Infisical secret manager."""

    def __init__(self, api_token: str, environment: str = "production"):
        """
        Initialize the secret manager provider.

        Args:
            api_token: Infisical API token (from environment or secure storage)
            environment: Environment name (dev, staging, production)
        """
        self.client = InfisicalClient(token=api_token)
        self.environment = environment
        self._cache = {}

    def get_secret(self, secret_name: str) -> str:
        """
        Fetch secret from Infisical.

        Args:
            secret_name: Name of the secret (e.g., "TELEGRAM_BOT_TOKEN")

        Returns:
            The secret value
        """
        # Check cache first
        if secret_name in self._cache:
            return self._cache[secret_name]

        try:
            secret = self.client.get_secret(
                secret_name=secret_name,
                environment=self.environment
            )
            self._cache[secret_name] = secret.secret_value
            return secret.secret_value
        except Exception as e:
            logger.error(f"Failed to fetch secret {secret_name}: {e}")
            raise

    def get_credential(self, credential_key: str, field: str) -> str:
        """
        Get a credential for a specific site.

        Args:
            credential_key: The credential key (e.g., "inforuta", "skade")
            field: The field to retrieve ("username" or "password")

        Returns:
            The credential value
        """
        secret_name = f"{credential_key.upper()}_{field.upper()}"
        return self.get_secret(secret_name)
```

**Step 5: Update main credential manager**

```python
import os
from typing import Optional

class CredentialManager:
    """Unified credential manager with multiple backend support."""

    def __init__(self, provider: str = "env"):
        """
        Initialize credential manager.

        Args:
            provider: "env", "sops", or "secret_manager"
        """
        self.provider = provider
        self.backend = self._initialize_backend()

    def _initialize_backend(self):
        """Initialize the appropriate credential backend."""
        if self.provider == "secret_manager":
            from .secret_manager_provider import SecretManagerProvider
            api_token = os.getenv("INFISICAL_API_TOKEN")
            if not api_token:
                raise ValueError("INFISICAL_API_TOKEN not set")
            return SecretManagerProvider(api_token)

        elif self.provider == "sops":
            from .encrypted_credential_manager import EncryptedCredentialManager
            return EncryptedCredentialManager()

        else:  # Default to env
            return None

    def get_credential(self, credential_key: str, field: str) -> Optional[str]:
        """Get credential from configured backend."""
        if self.backend:
            return self.backend.get_credential(credential_key, field)

        # Fallback to environment variables
        env_var = f"{credential_key.upper()}_{field.upper()}"
        return os.getenv(env_var)
```

**Step 6: Update systemd service**

```bash
sudo nano /etc/systemd/system/site-monitor.service
```

```ini
[Unit]
Description=Multi-Site Website Monitor
After=network-online.target

[Service]
Type=simple
User=monitor
WorkingDirectory=/home/monitor/siteChecker
Environment="INFISICAL_API_TOKEN=your_api_token_here"
ExecStart=/usr/bin/python3 main.py --credential-provider=secret_manager
Restart=always

[Install]
WantedBy=multi-user.target
```

#### Advantages
- Encrypted at rest and in transit
- Centralized management (update once, affects all deployments)
- Full audit logs (who accessed what secret, when)
- Access control and permissions
- Automatic secret rotation
- Secret versioning
- Team collaboration
- Compliance ready (SOC 2, HIPAA, etc.)

#### Disadvantages
- Requires internet connection (or self-hosted instance)
- External dependency
- More complex setup
- May have usage limits on free tier
- Additional infrastructure to maintain (if self-hosted)

#### Rotation Workflow

```bash
# 1. Update secret in Infisical UI or CLI
infisical secrets set SKADE_PASSWORD new_password --env production

# 2. Service picks up new value on next credential fetch (automatic)
# No restart needed if using dynamic fetching!
```

---

### Option 4: Password Manager CLI (Practical)

**Best for**: Personal projects, existing password manager users, quick wins

#### Overview
Leverage existing password manager infrastructure (Bitwarden, 1Password) using their CLI tools.

#### Implementation with Bitwarden CLI

**Step 1: Install Bitwarden CLI**

```bash
# Install via snap
sudo snap install bw

# Or download directly
wget https://vault.bitwarden.com/download/?app=cli&platform=linux
unzip bw-linux-*.zip
sudo mv bw /usr/local/bin/
sudo chmod +x /usr/local/bin/bw
```

**Step 2: Set up Bitwarden**

```bash
# Login to Bitwarden
bw login your@email.com

# Unlock vault (required after each reboot)
bw unlock

# This returns a session key - export it
export BW_SESSION="your_session_key_here"

# Test retrieval
bw get password "telegram-bot-token"
```

**Step 3: Store credentials in Bitwarden**

Use the Bitwarden app or CLI to create secure notes:

```bash
# Create entries for each credential
bw create item '{
  "type": 1,
  "name": "Site Monitor - Telegram",
  "notes": "",
  "login": {
    "username": "telegram-bot",
    "password": "your_bot_token_here"
  }
}'

bw create item '{
  "type": 1,
  "name": "Site Monitor - SKADE",
  "notes": "SKADE IoT Platform",
  "login": {
    "username": "your_username",
    "password": "your_password"
  }
}'
```

**Step 4: Create startup wrapper script**

Create `scripts/start-with-bitwarden.sh`:

```bash
#!/bin/bash

# Startup script that fetches credentials from Bitwarden

set -e

# Check if BW_SESSION is set
if [ -z "$BW_SESSION" ]; then
    echo "Error: BW_SESSION not set"
    echo "Run: export BW_SESSION=\$(bw unlock --raw)"
    exit 1
fi

# Fetch credentials from Bitwarden
export TELEGRAM_BOT_TOKEN=$(bw get password "Site Monitor - Telegram")
export TELEGRAM_CHAT_ID=$(bw get username "Site Monitor - Telegram Chat")
export HEALTHCHECK_PING_URL=$(bw get password "Site Monitor - Healthcheck")

export INFORUTA_USERNAME=$(bw get username "Site Monitor - InfoRuta")
export INFORUTA_PASSWORD=$(bw get password "Site Monitor - InfoRuta")

export FOMENTO_USERNAME=$(bw get username "Site Monitor - Fomento")
export FOMENTO_PASSWORD=$(bw get password "Site Monitor - Fomento")

export SKADE_USERNAME=$(bw get username "Site Monitor - SKADE")
export SKADE_PASSWORD=$(bw get password "Site Monitor - SKADE")

# Start the monitor
cd /home/monitor/siteChecker
python3 main.py

```

Make it executable:

```bash
chmod +x scripts/start-with-bitwarden.sh
```

**Step 5: Create systemd service with unlock**

This requires a workaround since systemd services run non-interactively. Options:

**Option A: Store session in file (less secure)**

```bash
# Create unlock script
cat > scripts/bw-unlock.sh <<'EOF'
#!/bin/bash
# Run this after each reboot
export BW_SESSION=$(bw unlock --raw)
echo "$BW_SESSION" > /tmp/bw-session
chmod 600 /tmp/bw-session
EOF

chmod +x scripts/bw-unlock.sh
```

```ini
# /etc/systemd/system/site-monitor.service
[Unit]
Description=Multi-Site Website Monitor
After=network-online.target

[Service]
Type=simple
User=monitor
WorkingDirectory=/home/monitor/siteChecker
ExecStartPre=/bin/bash -c 'export BW_SESSION=$(cat /tmp/bw-session)'
ExecStart=/home/monitor/siteChecker/scripts/start-with-bitwarden.sh
Restart=always

[Install]
WantedBy=multi-user.target
```

**Option B: Use Bitwarden self-hosted with API key**

Better for automation - generates a long-lived API key.

#### Advantages
- Leverages existing password manager
- Familiar UI for managing credentials
- Strong encryption
- Easy credential updates
- Cross-platform (same credentials on all devices)
- 2FA support

#### Disadvantages
- Requires CLI session management
- Manual unlock after reboot (unless using API key)
- Not ideal for fully automated deployments
- Requires internet connection (for cloud-hosted)

#### Rotation Workflow

```bash
# 1. Update password in Bitwarden (app or CLI)
bw edit item "Site Monitor - SKADE"

# 2. Restart service (fetches new value)
sudo systemctl restart site-monitor.service
```

---

## Recommendation

### For Your Use Case (Raspberry Pi Monitoring)

**Immediate improvement** (1-2 hours):
→ **Option 1: Systemd Environment Variables**
- Quick to implement
- Significant security improvement over .env
- No code changes needed

**Long-term solution** (3-4 hours):
→ **Option 2: SOPS + Age Encryption**
- Best balance of security and complexity
- Can version control encrypted secrets
- Easy rotation workflow
- No external dependencies

**If scaling to multiple devices**:
→ **Option 3: Secret Manager (Infisical)**
- Centralized credential management
- Update once, applies everywhere
- Audit logs and access control

### Implementation Priority

1. **Week 1**: Move to systemd with `/etc/site-monitor/credentials.conf`
   - Immediate security improvement
   - Learn systemd service management
   - Set up proper service user

2. **Week 2-3**: Implement SOPS encryption
   - Encrypt existing credentials
   - Update credential manager code
   - Test rotation workflow

3. **Future**: Consider secret manager if:
   - Deploying to multiple Raspberry Pis
   - Need team access
   - Want centralized updates
   - Require audit logs

---

## Implementation Guide

### Quick Start: Migrate from .env to Systemd

**Step-by-step migration guide**:

```bash
# 1. Create secure directory
sudo mkdir -p /etc/site-monitor
sudo chmod 700 /etc/site-monitor

# 2. Copy existing .env contents to credentials file
sudo cp config/.env /etc/site-monitor/credentials.conf
sudo chmod 600 /etc/site-monitor/credentials.conf
sudo chown root:root /etc/site-monitor/credentials.conf

# 3. Create service user
sudo useradd -r -s /bin/false monitor
sudo chown -R monitor:monitor /home/monitor/siteChecker

# 4. Create systemd service
sudo nano /etc/systemd/system/site-monitor.service
# (paste service configuration from Option 1)

# 5. Enable and start
sudo systemctl daemon-reload
sudo systemctl enable site-monitor.service
sudo systemctl start site-monitor.service

# 6. Verify it's running
sudo systemctl status site-monitor.service
sudo journalctl -u site-monitor.service -f

# 7. Remove old .env file (after confirming service works)
rm config/.env
```

### Testing Checklist

After implementing any credential management solution:

- [ ] All credentials load correctly
- [ ] Service starts automatically on boot
- [ ] Service restarts on failure
- [ ] Logs show successful authentication
- [ ] Notifications work (Telegram, Healthchecks.io)
- [ ] Credential files have correct permissions
- [ ] Old .env file removed or secured
- [ ] Backup of credentials/keys stored securely
- [ ] Documented rotation procedure
- [ ] Team members can access secrets (if applicable)

### Security Best Practices

1. **Principle of Least Privilege**
   - Run service as dedicated user (not root)
   - Restrict file permissions (600 for secrets)
   - Limit systemd service capabilities

2. **Defense in Depth**
   - Encrypt filesystem (LUKS)
   - Use firewall (ufw/iptables)
   - Keep system updated
   - Disable unnecessary services

3. **Key Management**
   - Backup encryption keys securely
   - Store keys separate from encrypted data
   - Use different keys for different environments
   - Rotate keys periodically

4. **Monitoring**
   - Log credential access attempts
   - Alert on failed authentications
   - Monitor service restarts
   - Track configuration changes

5. **Physical Security**
   - Secure Raspberry Pi location
   - Disable unused USB/network ports
   - Set BIOS/boot password
   - Consider encrypted boot partition

### Troubleshooting

**Service won't start**:
```bash
# Check service status
sudo systemctl status site-monitor.service

# View detailed logs
sudo journalctl -u site-monitor.service -n 50

# Check file permissions
ls -la /etc/site-monitor/
ls -la /home/monitor/siteChecker/

# Test manually
sudo -u monitor /usr/bin/python3 /home/monitor/siteChecker/main.py
```

**Credentials not loading**:
```bash
# Verify environment file syntax
sudo cat /etc/site-monitor/credentials.conf

# Check for special characters that need escaping
# Make sure there are no quotes around values

# Test environment injection
sudo systemd-run --property="EnvironmentFile=/etc/site-monitor/credentials.conf" \
  --unit=test-env \
  /usr/bin/env
```

**SOPS decryption fails**:
```bash
# Check SOPS_AGE_KEY_FILE is set
echo $SOPS_AGE_KEY_FILE

# Test manual decryption
sops -d config/secrets.yaml

# Verify key file permissions
ls -la /etc/site-monitor/key.txt

# Check key format
head -1 /etc/site-monitor/key.txt
# Should show: # created: YYYY-MM-DD...
```

---

## Additional Resources

### Documentation
- [Mozilla SOPS](https://github.com/mozilla/sops)
- [Age Encryption](https://age-encryption.org/)
- [Systemd Service Documentation](https://www.freedesktop.org/software/systemd/man/systemd.service.html)
- [Infisical Docs](https://infisical.com/docs)
- [HashiCorp Vault](https://www.vaultproject.io/)
- [Bitwarden CLI](https://bitwarden.com/help/cli/)

### Tools
- [git-crypt](https://github.com/AGWA/git-crypt) - Alternative to SOPS
- [Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets) - For Kubernetes
- [Doppler CLI](https://docs.doppler.com/docs/cli) - Cloud secret management
- [pass](https://www.passwordstore.org/) - Unix password manager

### Security Auditing
- [Gitleaks](https://github.com/gitleaks/gitleaks) - Scan git for secrets
- [TruffleHog](https://github.com/trufflesecurity/trufflehog) - Find leaked credentials
- [detect-secrets](https://github.com/Yelp/detect-secrets) - Pre-commit hook

---

## Summary

| Approach | Security | Complexity | Cost | Best For |
|----------|----------|------------|------|----------|
| .env files | ⚠️ Low | Low | Free | Development only |
| Systemd env | ✅ Medium | Low | Free | Single deployment |
| SOPS + Age | ✅✅ High | Medium | Free | Multiple deployments |
| Secret Manager | ✅✅✅ Very High | High | Free/Paid | Production, teams |
| Password Manager | ✅✅ High | Medium | Free/Paid | Personal projects |

**Final Recommendation**: Start with **systemd** (quick win), then migrate to **SOPS** (long-term solution).
