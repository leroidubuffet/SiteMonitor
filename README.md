# InfoRuta Website Monitor

A comprehensive Python monitoring solution for https://inforuta-rce.es/ that performs uptime checks, authentication verification, and health monitoring with configurable alerts.

## Features

- **Uptime Monitoring**: Check website availability every 15 minutes
- **Authentication Testing**: Verify login functionality with credentials
- **Health Checks**: Monitor protected endpoints to ensure full stack operation
- **Smart Notifications**:
  - Console output with colored status indicators
  - Email alerts for downtime/recovery
  - Batch notifications to reduce alert fatigue
- **Circuit Breaker**: Prevents cascading failures and excessive alerts
- **Performance Metrics**: Track response times, availability percentage, and trends
- **Persistent State**: Maintains check history and statistics across restarts
- **Flexible Configuration**: YAML-based configuration with environment variable support

## Quick Start

### 1. Installation

```bash
# Clone or download the project
cd /Users/yagoairm2/Documents/ofiteco/_siteChecker

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Credentials

#### Option A: Interactive Setup
```bash
python main.py --setup
```

#### Option B: Manual Setup
```bash
# Copy the example environment file
cp config/.env.example config/.env

# Edit config/.env with your credentials
# INFORUTA_USERNAME=your_username
# INFORUTA_PASSWORD=your_password
```

### 3. Run the Monitor

```bash
# Start monitoring (checks every 15 minutes)
python main.py

# Run a single check
python main.py --check-once

# Test connection and credentials
python main.py --test
```

## Configuration

The monitor is configured via `config/config.yaml`. Key settings include:

### Monitoring Settings
```yaml
monitoring:
  url: "https://inforuta-rce.es/"
  interval_minutes: 15  # Check frequency
  timeout_seconds: 30    # Request timeout
```

### Check Types
```yaml
checks:
  enabled:
    - uptime          # Basic availability
    - authentication  # Login verification
    - health         # Protected endpoint checks
```

### Notifications
```yaml
notifications:
  console:
    enabled: true
    colored_output: true
    
  email:
    enabled: false  # Set to true after configuring credentials
    alert_on:
      - downtime
      - recovery
      - auth_failure
```

### Performance Thresholds
```yaml
performance:
  warning_threshold_ms: 3000   # Warn if response > 3 seconds
  critical_threshold_ms: 10000 # Critical if response > 10 seconds
```

## Usage Examples

### Basic Monitoring
```bash
# Start monitoring with default settings
python main.py

# Output:
# ✓ UPTIME: SUCCESS (245ms) HTTP 200
# ✓ AUTHENTICATION: SUCCESS (1823ms)
# ⚠ HEALTH: WARNING (3250ms) - Slow response
```

### Custom Configuration
```bash
# Use custom config file
python main.py --config custom_config.yaml

# Use production credentials
python main.py --env-file production.env
```

### Testing and Debugging
```bash
# Test connection without continuous monitoring
python main.py --test

# Run single check with verbose output
python main.py --check-once
```

## Console Output

The monitor provides real-time colored console output:

- ✓ Green: Successful checks
- ⚠ Yellow: Warnings (slow response, non-critical issues)
- ✗ Red: Failures (site down, auth failed)
- ⏰ Purple: Timeouts

State changes trigger prominent alerts:
- **SITE DOWN**: Red background alert when site becomes unavailable
- **SITE RECOVERED**: Green background alert when site recovers

## Email Notifications

When configured, the monitor sends HTML-formatted emails for:

- **Downtime Alerts**: Immediate notification when site goes down
- **Recovery Notices**: Confirmation when site comes back online
- **Authentication Failures**: Alerts for login issues
- **Daily Digests**: Summary reports (optional)

### Email Setup (Gmail Example)

1. Enable 2-factor authentication on your Gmail account
2. Generate an app-specific password
3. Configure in `.env`:
   ```
   EMAIL_FROM=your_email@gmail.com
   EMAIL_TO=alerts@example.com
   EMAIL_PASSWORD=your_app_specific_password
   ```

## Advanced Features

### Circuit Breaker

Prevents excessive checks during extended outages:
- Opens after 5 consecutive failures
- Waits 30 minutes before attempting recovery
- Reduces unnecessary load on failing services

### Metrics Collection

Tracks performance metrics over time:
- Response time statistics (mean, median, p95, p99)
- Availability percentage
- Success/failure rates
- Uptime/downtime duration

### State Persistence

Maintains monitoring history in `logs/monitor_state.json`:
- Last 100 check results per check type
- Consecutive failure counts
- Recovery timestamps
- Statistical summaries

## Security Considerations

- **Credentials are never logged**: The system masks credentials in all log output
- **Secure storage options**: Supports keyring for production credential storage
- **Updated dependencies**: All packages are updated to latest secure versions
- **No hardcoded secrets**: All sensitive data stored in environment variables

## Troubleshooting

### Common Issues

**"No credentials configured"**
- Run `python main.py --setup` to configure credentials
- Or create `config/.env` from `config/.env.example`

**"SSL certificate verification failed"**
- The site's certificate may be expired or invalid
- Check `checks.uptime.check_ssl` in config.yaml

**"Circuit breaker is OPEN"**
- Too many consecutive failures detected
- Wait 30 minutes or restart the monitor to reset

**Email notifications not working**
- Verify SMTP credentials are correct
- Check firewall/antivirus settings
- For Gmail, ensure app-specific password is used

### Debug Mode

Enable debug logging in `config/config.yaml`:
```yaml
logging:
  level: DEBUG
```

## Project Structure

```
_siteChecker/
├── config/
│   ├── config.yaml       # Main configuration
│   └── .env.example      # Environment template
├── src/
│   ├── checkers/         # Health check modules
│   ├── notifiers/        # Notification handlers
│   ├── storage/          # Credential & state management
│   ├── utils/            # Utilities (logging, metrics)
│   ├── monitor.py        # Main orchestrator
│   └── scheduler.py      # Job scheduling
├── logs/                 # Log files (auto-created)
├── main.py              # Entry point
├── requirements.txt     # Dependencies
└── README.md           # This file
```

## Requirements

- Python 3.8+
- Internet connection
- Valid InfoRuta credentials (for auth checks)

## License

This monitoring tool is provided as-is for internal use at Ofiteco.

## Support

For issues or questions, please contact the development team.

---

**Version**: 1.0.0  
**Last Updated**: January 2025