# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-Site Website Monitor - A Python-based monitoring system that performs uptime checks, authentication verification, and health monitoring across multiple websites with Telegram/email notifications. Currently monitors 5 Spanish infrastructure websites (AEMET, DGT, InfoRuta RCE, Vialidad ACP, Fomento VI).

## Development Commands

### Setup and Installation
```bash
# Install dependencies
pip install -r requirements.txt

# Configure credentials (copy from example)
cp config/.env.example config/.env
# Then edit config/.env with actual credentials
```

### Running the Monitor
```bash
# Start continuous monitoring (15-minute intervals)
python3 main.py

# Run single check and exit
python3 main.py --check-once

# Enable Telegram debug mode (notify on ALL checks instead of just state changes)
python3 main.py --telegram-debug

# Test connection and credentials
python3 main.py --test
```

### Testing and Debugging
```bash
# Test all configured sites
python3 debug_all_sites.py

# Test single site login (InfoRuta example)
python3 debug_login.py

# Run Telegram integration tests
python3 tests/test_telegram.py

# Run all tests
pytest tests/
```

## Architecture Overview

### Multi-Site Architecture Pattern
The monitor uses a **per-site configuration model** where each site is independently configured with its own:
- Check types (uptime, authentication, health)
- Circuit breaker state
- Credentials (via credential_key mapping)
- Success indicators and endpoints
- Notification preferences

Sites are defined in `config/config.yaml` under the `sites` array.

### Core Components

**Monitor (`src/monitor.py`)**: Central orchestrator that:
- Loads multi-site configuration from YAML
- Initializes checkers per site based on `checks_enabled`
- Coordinates check execution across all sites
- Manages shared notifiers (console, email, Telegram)
- Handles graceful shutdown via signal handlers

**Checkers (`src/checkers/`)**: Modular check types that inherit from `BaseChecker`:
- `UptimeChecker`: HTTP availability checks (status codes, SSL verification)
- `AuthChecker`: Form-based authentication testing with auto-detection of login fields
- `HealthChecker`: Protected endpoint validation
- All return standardized `CheckResult` objects with `CheckStatus` enum

**Notifiers (`src/notifiers/`)**: Notification channels that inherit from `BaseNotifier`:
- `ConsoleNotifier`: Colored terminal output with site labels
- `EmailNotifier`: HTML email alerts per site
- `TelegramNotifier`: Bot integration with two modes:
  - **Regular mode** (default): Only notifies on state changes (downtime, recovery, auth failures)
  - **Debug mode**: Notifies on EVERY check for all sites (useful for testing)
- Supports batch notifications to reduce alert fatigue

**Storage (`src/storage/`)**:
- `CredentialManager`: Multi-site credential handling via environment variables. Maps `credential_key` from site config to `{KEY}_USERNAME` and `{KEY}_PASSWORD` env vars
- `StateManager`: Persists per-site check history, statistics, and circuit breaker state in `logs/monitor_state.json`

**Scheduler (`src/scheduler.py`)**: APScheduler-based job scheduling with configurable intervals

**Utils (`src/utils/`)**:
- `CircuitBreaker`: Per-site failure threshold management to prevent excessive checks
- `MetricsCollector`: Tracks response times and availability percentages per site
- `logger.py`: Centralized logging with file rotation

### Authentication Auto-Detection

The `AuthChecker` automatically detects HTML form fields by searching for common patterns:
- Username: `user`, `usuario`, `login`, `email`
- Password: `pass`, `pwd`, `password`, `clave`, `contraseña`
- Submit buttons: `btn`, `submit`, `entrar`, `login`
- ASP.NET ViewState fields (if present)

**Limitation**: Only works with traditional HTML forms. JavaScript/SPA-based authentication (React, Angular, Vue) requires API integration and is not yet supported.

### Notification Modes

**Telegram Notifications** have two distinct modes:

1. **Regular Mode** (`debug_mode: false`):
   - Notifies ONLY on state changes (new failures, recoveries, auth failures)
   - Reduces alert fatigue for production monitoring
   - Default behavior

2. **Debug Mode** (`debug_mode: true`):
   - Notifies on EVERY check for ALL sites (every 15 minutes)
   - Useful for initial setup, troubleshooting, or critical monitoring periods
   - Can be enabled via config or `--telegram-debug` CLI flag

### Configuration Structure

**Global Settings** (`config/config.yaml`):
- `monitoring`: Check interval, timeout, user agent
- `notifications`: Per-channel config (console, email, Telegram)
- `circuit_breaker`: Failure thresholds and recovery timeouts
- `logging`: Log levels and file paths

**Per-Site Settings**:
- `name`: Display name for notifications and logs
- `url`: Base URL to monitor
- `credential_key`: Maps to env vars (e.g., "inforuta" → `INFORUTA_USERNAME`)
- `checks_enabled`: Array of check types (`uptime`, `authentication`, `health`)
- `uptime`: Endpoints, expected status codes, SSL verification
- `authentication`: Login endpoint, success indicators, retry logic

### State Persistence

The monitor maintains state in `logs/monitor_state.json` with structure:
```json
{
  "global": {
    "last_check_time": "ISO timestamp",
    "total_checks": 250
  },
  "sites": {
    "AEMET": {
      "last_check_time": "ISO timestamp",
      "last_results": {"uptime": {...}, "authentication": {...}},
      "statistics": {"response_times": [...], "availability": 99.5},
      "circuit_breaker": {"is_open": false, "failure_count": 0}
    }
  }
}
```

This allows the monitor to:
- Resume monitoring after restarts without losing history
- Track consecutive failures per site for circuit breaker logic
- Calculate availability percentages and response time trends

### Adding New Sites

To add a new monitored site:

1. Add site configuration to `config/config.yaml` under `sites` array
2. If authentication is needed, add credentials to `config/.env` using the pattern `{CREDENTIAL_KEY}_USERNAME` and `{CREDENTIAL_KEY}_PASSWORD`
3. Test with `python3 debug_all_sites.py`
4. If auto-detection fails (SPA/JavaScript auth), either:
   - Use uptime-only monitoring (`checks_enabled: [uptime]`)
   - Implement API-based authentication (future enhancement)

### Security Notes

- Credentials are NEVER logged (masked in all log output)
- All sensitive data stored in environment variables (`.env` file is gitignored)
- Per-site credential isolation via credential_key mapping
- Dependencies updated to latest secure versions (see comments in requirements.txt)

### Python Package Management

- Python 3.8+ required
- Virtual environment recommended (`.env` directory exists but is gitignored)
- All dependencies pinned to specific versions in `requirements.txt`
- Key packages: httpx (HTTP client with HTTP/2), APScheduler (scheduling), PyYAML (config), BeautifulSoup4 (HTML parsing), colorama (terminal colors)

### Logging

- Console output: Colored status indicators with site labels (`[AEMET] ✓ UPTIME: SUCCESS`)
- File logs: `logs/monitor.log` (INFO+), `logs/monitor.error.log` (ERROR only)
- Log level configurable in `config/config.yaml` under `logging.level`
- Supports DEBUG mode for troubleshooting

### Error Handling Patterns

- Circuit breakers prevent excessive checks to failing sites (opens after 5 consecutive failures, waits 30 minutes)
- Retry logic with exponential backoff for transient failures
- Graceful degradation: One site's failure doesn't stop monitoring of other sites
- Signal handlers (SIGINT, SIGTERM) for graceful shutdown
