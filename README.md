# Multi-Site Website Monitor

A comprehensive Python monitoring solution that performs uptime checks, authentication verification, and health monitoring across multiple websites with configurable alerts.

## Features

- **Multi-Site Monitoring**: Monitor multiple websites simultaneously with independent tracking
- **Uptime Monitoring**: Check website availability every 15 minutes
- **Authentication Testing**: Verify login functionality with auto-detected form fields
- **Smart Notifications**:
  - Console output with colored status indicators and site labels
  - Email alerts for downtime/recovery per site
  - Telegram bot notifications with debug/regular modes
  - Batch notifications to reduce alert fatigue
- **Per-Site Circuit Breakers**: Independent failure thresholds for each site
- **Performance Metrics**: Track response times, availability percentage, and trends per site
- **Persistent State**: Maintains check history and statistics for each site across restarts
- **Auto-Detection**: Automatically detects login form fields (username, password, submit button)
- **Flexible Configuration**: YAML-based configuration with environment variable support

## Monitored Sites

Currently configured to monitor:
- **AEMET** - Spanish Meteorological Agency
- **DGT Traffic Cameras** - Spanish Directorate-General for Traffic
- **InfoRuta RCE** - Road information system (with authentication)
- **Vialidad ACP** - Ofiteco road monitoring platform
- **Fomento VI** - Infrastructure management system (with authentication)

## Quick Start

### 1. Installation

```bash
# Clone or download the project
cd /Users/yagoairm2/Documents/ofiteco/_siteChecker

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Credentials

```bash
# Copy the example environment file
cp config/.env.example config/.env

# Edit config/.env with your credentials
nano config/.env
```

Add credentials for authenticated sites:
```bash
# InfoRuta credentials
INFORUTA_USERNAME=your_username
INFORUTA_PASSWORD=your_password

# Fomento VI credentials
FOMENTO_USERNAME=your_username
FOMENTO_PASSWORD=your_password

# Vialidad credentials (optional - currently uptime-only)
VIALIDAD_USERNAME=your_username
VIALIDAD_PASSWORD=your_password
```

### 3. Test Configuration

```bash
# Test all sites and verify credentials
python3 debug_all_sites.py
```

This will show:
- Which sites are ready for monitoring
- Auto-detected login form fields
- Any configuration issues

### 4. Run the Monitor

```bash
# Start monitoring (checks every 15 minutes)
python3 main.py
```

## Configuration

The monitor is configured via `config/config.yaml`. 

### Multi-Site Structure
```yaml
sites:
  - name: "AEMET"
    url: "https://www.aemet.es/"
    checks_enabled:
      - uptime
    uptime:
      endpoints:
        - "/"
      expected_status: [200, 301, 302]
      check_ssl: true

  - name: "InfoRuta RCE"
    url: "https://inforuta-rce.es/"
    credential_key: "inforuta"  # Maps to INFORUTA_USERNAME/PASSWORD
    checks_enabled:
      - uptime
      - authentication
    uptime:
      endpoints:
        - "/"
      expected_status: [200, 301, 302]
      check_ssl: true
    authentication:
      enabled: true
      login_endpoint: "/"
      success_indicators:
        - "Usuario"
        - "session"
      max_retries: 2
```

### Global Settings
```yaml
monitoring:
  interval_minutes: 15  # Check frequency for all sites
  timeout_seconds: 30   # Request timeout
  user_agent: "Multi-Site-Monitor/1.0"
```

### Notifications
```yaml
notifications:
  console:
    enabled: true
    colored_output: true
    show_timestamps: true

  email:
    enabled: false  # Set to true after configuring credentials
    alert_on:
      - downtime
      - recovery
      - auth_failure
```

### Circuit Breaker (Per-Site)
```yaml
circuit_breaker:
  enabled: true
  failure_threshold: 5        # Open after 5 consecutive failures
  recovery_timeout_minutes: 30
```

## Usage Examples

### Basic Monitoring
```bash
# Start monitoring all sites
python3 main.py

# Output:
# [AEMET] ✓ UPTIME: SUCCESS (245ms) HTTP 200
# [InfoRuta RCE] ✓ UPTIME: SUCCESS (312ms) HTTP 200
# [InfoRuta RCE] ✓ AUTHENTICATION: SUCCESS (1823ms)
# [DGT Traffic Cameras] ✓ UPTIME: SUCCESS (189ms) HTTP 200
# [Vialidad ACP] ✓ UPTIME: SUCCESS (276ms) HTTP 200
# [Fomento VI] ✓ UPTIME: SUCCESS (421ms) HTTP 200
```

### Testing and Debugging
```bash
# Test all sites and check configuration
python3 debug_all_sites.py

# Test single site (using debug_login.py for InfoRuta)
python3 debug_login.py
```

## Console Output

The monitor provides real-time colored console output with site labels:

```
[2025-11-08 14:30:15] [AEMET] ✓ UPTIME: SUCCESS (245ms)
[2025-11-08 14:30:16] [InfoRuta RCE] ✓ AUTHENTICATION: SUCCESS (1823ms)
[2025-11-08 14:30:17] [Vialidad ACP] ⚠ UPTIME: WARNING (3250ms) - Slow response
```

Colors:
- ✓ **Green**: Successful checks
- ⚠ **Yellow**: Warnings (slow response, non-critical issues)
- ✗ **Red**: Failures (site down, auth failed)
- ⏰ **Purple**: Timeouts

State changes trigger prominent alerts:
- **SITE DOWN**: Red background alert when site becomes unavailable
- **SITE RECOVERED**: Green background alert when site recovers

## Email Notifications

When configured, the monitor sends HTML-formatted emails for each site:

- **Downtime Alerts**: Immediate notification when a site goes down
- **Recovery Notices**: Confirmation when a site comes back online
- **Authentication Failures**: Alerts for login issues (per site)
- **Daily Digests**: Summary reports for all sites (optional)

### Email Setup (Gmail Example)

1. Enable 2-factor authentication on your Gmail account
2. Generate an app-specific password
3. Configure in `.env`:
   ```bash
   EMAIL_FROM=your_email@gmail.com
   EMAIL_TO=alerts@example.com
   EMAIL_PASSWORD=your_app_specific_password
   ```
4. Enable in `config/config.yaml`:
   ```yaml
   notifications:
     email:
       enabled: true
   ```

## Telegram Notifications

The monitor includes Telegram bot integration with two notification modes for flexible alerting.

### Notification Modes

#### Regular Mode (Default)
Notifies only on important state changes:
- Site downtime (when a site goes down)
- Site recovery (when a site comes back online)
- Authentication failures (login issues)

This mode reduces notification fatigue by only alerting on actionable events.

#### Debug Mode
Notifies on EVERY check for all sites (every 15 minutes):
- All uptime checks
- All authentication checks
- All health checks
- Success and failure states

Useful for:
- Initial setup and testing
- Troubleshooting connectivity issues
- Monitoring during critical periods

### Setup Instructions

#### Step 1: Create a Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` to create a new bot
3. Follow the prompts to choose a name and username
4. BotFather will give you a **Bot Token** (looks like `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
5. Save this token - you'll need it for configuration

#### Step 2: Get Your Chat ID

**Option A: Using your bot**
1. Send a message to your bot (any message like "hello")
2. Visit this URL in your browser (replace `<YOUR_BOT_TOKEN>` with your actual token):
   ```
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
3. Look for `"chat":{"id":123456789}` in the response
4. The number is your **Chat ID**

**Option B: Using @userinfobot**
1. Search for **@userinfobot** on Telegram
2. Start a chat with the bot
3. It will send you your Chat ID

**For Group Chats:**
1. Add your bot to the group
2. Send a message in the group
3. Visit the getUpdates URL (as in Option A)
4. Look for `"chat":{"id":-123456789}` (note the negative number for groups)

#### Step 3: Configure Credentials

Add your bot credentials to `config/.env`:

```bash
# Telegram Configuration
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=your_chat_id_here
```

#### Step 4: Enable Telegram in Configuration

Edit `config/config.yaml`:

```yaml
notifications:
  telegram:
    enabled: true              # Enable Telegram notifications
    debug_mode: false          # false = regular mode, true = debug mode
    batch_notifications: true  # Combine multiple alerts into one message
    alert_on:
      - downtime
      - recovery
      - auth_failure
```

### Usage Examples

#### Start with Regular Mode (State Changes Only)

```bash
# Default behavior - notifies on failures/recoveries only
python3 main.py
```

Output in Telegram:
```
❌ [InfoRuta RCE] UPTIME FAILURE 🚨 NEW FAILURE

⏱ Response: Timeout after 30s
❗️ Error: Connection timeout
🕐 Time: 2025-11-08 14:30:15
```

#### Start with Debug Mode (All Checks)

```bash
# Enable debug mode via command line
python3 main.py --telegram-debug
```

Output in Telegram (every 15 minutes):
```
✅ [AEMET] UPTIME SUCCESS

⏱ Response: 245ms
📊 HTTP: 200
🕐 Time: 2025-11-08 14:30:15

[Debug Mode]
```

```
✅ [InfoRuta RCE] AUTHENTICATION SUCCESS

⏱ Response: 1823ms
🕐 Time: 2025-11-08 14:30:16

[Debug Mode]
```

#### Permanent Debug Mode

To enable debug mode permanently, edit `config/config.yaml`:

```yaml
notifications:
  telegram:
    enabled: true
    debug_mode: true  # Always send all checks
```

### Message Formats

The Telegram notifier sends rich formatted messages with emojis:

**Success Message:**
```
✅ [AEMET] UPTIME SUCCESS

⏱ Response: 245ms
📊 HTTP: 200
🕐 Time: 2025-11-08 14:30:15
```

**Failure Message:**
```
❌ [InfoRuta RCE] UPTIME FAILURE 🚨 NEW FAILURE

⏱ Response: 5000ms
📊 HTTP: 500
💬 Internal Server Error
❗️ Error: Server returned HTTP 500
🕐 Time: 2025-11-08 14:30:15
```

**Recovery Message:**
```
✅ [Vialidad ACP] UPTIME SUCCESS 🔄 RECOVERED

⏱ Response: 276ms
📊 HTTP: 200
🕐 Time: 2025-11-08 14:35:20
```

**Batch Message (Multiple Sites):**
```
📋 Batch Status Update

✅ 3 OK | ❌ 2 FAIL

✅ AEMET            UPTI 245ms
✅ InfoRuta RCE     AUTH 1823ms
❌ Vialidad ACP     UPTI Timeout
✅ Fomento VI       UPTI 421ms
❌ DGT Traffic      UPTI 500ms

🕐 2025-11-08 14:30:15
```

### Command-Line Options

```bash
# Regular mode (state changes only)
python3 main.py

# Debug mode (all checks)
python3 main.py --telegram-debug

# Test with a single check
python3 main.py --check-once --telegram-debug

# Use custom config
python3 main.py --config my_config.yaml --telegram-debug

# Test the Telegram integration
python3 tests/test_telegram.py
```

### Troubleshooting

**Testing Your Setup:**

Run the comprehensive test suite to verify everything works:
```bash
python3 tests/test_telegram.py
```

This will test:
- Credential configuration
- Regular mode notifications (state changes only)
- Debug mode notifications (all checks)
- Batch notifications

You should receive test messages in your Telegram chat.

**"Telegram enabled but missing BOT_TOKEN or CHAT_ID"**
- Check that both variables are set in `config/.env`
- Verify there are no extra spaces or quotes around the values
- Ensure the .env file is in the `config/` directory

**"Telegram API error: Unauthorized"**
- Your bot token is invalid or expired
- Copy the token again from @BotFather
- Make sure you copied the entire token (including the colon and everything after it)

**"Telegram API error: Bad Request: chat not found"**
- Your chat ID is incorrect
- Make sure you've sent at least one message to the bot first
- For group chats, ensure the bot has been added to the group
- Check if the chat ID should be negative (for groups)

**"Bot doesn't respond to messages"**
- This is normal - the bot only sends notifications, it doesn't respond to commands
- The monitor controls when messages are sent
- You can test by running `python3 main.py --check-once`

**Messages not appearing in debug mode:**
- Verify `debug_mode: true` in config.yaml or use `--telegram-debug` flag
- Check that `enabled: true` in the telegram configuration
- Look at console output to verify Telegram notifier is initialized
- Check logs at `logs/monitor.log` for Telegram-related errors

### Security Notes

- Keep your bot token secret - it provides full access to your bot
- Don't commit `.env` files to version control
- For group chats, be aware that all group members can see notifications
- You can revoke and regenerate bot tokens via @BotFather if compromised

## Advanced Features

### Auto-Detection of Login Forms

The monitor automatically detects login form fields by looking for:
- Username fields: `user`, `usuario`, `login`
- Password fields: `pass`, `pwd`, `clave`
- Submit buttons: `btn`, `submit`, `entrar`
- ASP.NET ViewState fields (if present)

This works for traditional HTML form-based authentication. JavaScript/SPA-based sites require API integration.

### Per-Site Circuit Breakers

Each site has its own circuit breaker to prevent excessive checks:
- Opens after 5 consecutive failures (configurable)
- Waits 30 minutes before attempting recovery
- Other sites continue to be monitored normally

### Metrics Collection

Tracks performance metrics per site:
- Response time statistics (mean, median, p95, p99)
- Availability percentage
- Success/failure rates per site
- Uptime/downtime duration per site

### State Persistence

Maintains monitoring history in `logs/monitor_state.json`:
- Per-site statistics and history
- Last 100 check results per site per check type
- Consecutive failure counts per site
- Circuit breaker state per site
- Recovery timestamps

Example state structure:
```json
{
  "global": {
    "last_check_time": "2025-11-08T14:30:15",
    "total_checks": 250
  },
  "sites": {
    "AEMET": {
      "last_check_time": "2025-11-08T14:30:15",
      "last_results": {...},
      "statistics": {...},
      "circuit_breaker": {
        "is_open": false,
        "failure_count": 0
      }
    },
    "InfoRuta RCE": {...}
  }
}
```

## Adding New Sites

To add a new site to monitor:

1. **Edit `config/config.yaml`**:
   ```yaml
   sites:
     - name: "My New Site"
       url: "https://example.com/"
       credential_key: "mysite"  # Optional, only for authenticated sites
       checks_enabled:
         - uptime
         - authentication  # Optional
       uptime:
         endpoints:
           - "/"
         expected_status: [200]
         check_ssl: true
       authentication:  # Optional
         enabled: true
         login_endpoint: "/login"
         success_indicators:
           - "Welcome"
           - "Dashboard"
         max_retries: 2
   ```

2. **Add credentials (if needed)** in `config/.env`:
   ```bash
   MYSITE_USERNAME=username
   MYSITE_PASSWORD=password
   ```

3. **Test the configuration**:
   ```bash
   python3 debug_all_sites.py
   ```

4. **Start monitoring**:
   ```bash
   python3 main.py
   ```

## Security Considerations

- **Credentials are never logged**: The system masks credentials in all log output
- **Secure storage options**: Supports keyring for production credential storage
- **Updated dependencies**: All packages are updated to latest secure versions
- **No hardcoded secrets**: All sensitive data stored in environment variables
- **Per-site credential isolation**: Each site uses its own credential key

## Troubleshooting

### Common Issues

**"No credentials configured for site"**
- Check that credentials exist in `config/.env`
- Verify the `credential_key` in `config.yaml` matches the environment variable prefix

**"Could not auto-detect login fields"**
- The site may use JavaScript-based authentication (React, Angular, Vue)
- Run `python3 debug_all_sites.py` to see what fields were found
- Consider changing the site to uptime-only monitoring
- For API-based auth, future enhancement required

**"Circuit breaker is OPEN for site"**
- Too many consecutive failures detected for that site
- Other sites continue to be monitored
- Wait 30 minutes or restart the monitor to reset

**"SSL certificate verification failed"**
- The site's certificate may be expired or invalid
- Set `check_ssl: false` for that site in config.yaml

### Debug Tools

**Test all sites:**
```bash
python3 debug_all_sites.py
```

**Test specific site (InfoRuta example):**
```bash
python3 debug_login.py
```

**Enable debug logging** in `config/config.yaml`:
```yaml
logging:
  level: DEBUG
```

## Project Structure

```
_siteChecker/
├── config/
│   ├── config.yaml          # Multi-site configuration
│   ├── .env                 # Credentials (gitignored)
│   └── .env.example         # Credential template
├── src/
│   ├── checkers/
│   │   ├── base_checker.py     # Base checker class
│   │   ├── uptime_checker.py   # HTTP availability checks
│   │   ├── auth_checker.py     # Login verification (site-agnostic)
│   │   └── health_checker.py   # Protected endpoint checks
│   ├── notifiers/
│   │   ├── base_notifier.py    # Base notifier class
│   │   ├── console_notifier.py # Console output (per-site labels)
│   │   └── email_notifier.py   # Email alerts (per-site)
│   ├── storage/
│   │   ├── credential_manager.py  # Multi-site credential handling
│   │   └── state_manager.py       # Per-site state persistence
│   ├── utils/
│   │   ├── logger.py           # Logging configuration
│   │   ├── metrics.py          # Performance metrics
│   │   └── circuit_breaker.py  # Circuit breaker pattern
│   ├── monitor.py              # Multi-site orchestrator
│   └── scheduler.py            # Job scheduling
├── logs/                       # Log files (auto-created)
│   ├── monitor.log
│   ├── monitor.error.log
│   └── monitor_state.json      # Per-site state
├── main.py                     # Entry point
├── debug_all_sites.py          # Multi-site testing utility
├── debug_login.py              # Single-site login testing
├── requirements.txt            # Dependencies
└── README.md                   # This file
```

## Requirements

- Python 3.8+
- Internet connection
- Valid credentials for authenticated sites

## Dependencies

Key packages:
- `httpx` - Modern HTTP client with HTTP/2 support
- `APScheduler` - Job scheduling
- `PyYAML` - Configuration parsing
- `colorama` - Cross-platform colored terminal output
- `python-dotenv` - Environment variable management
- `keyring` - Secure credential storage (optional)

See `requirements.txt` for complete list.

## License

This monitoring tool is provided as-is for internal use at Ofiteco.

## Support

For issues or questions, please contact the development team.

---

**Version**: 2.0.0 (Multi-Site)  
**Last Updated**: November 2025  
**Author**: Ofiteco Development Team
