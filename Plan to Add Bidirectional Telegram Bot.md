Plan: Add Bidirectional Telegram Bot with Commands

### Overview
Add command support to the Telegram bot so you can interact with the monitoring system (check status, trigger checks, etc.) via Telegram messages.

### Implementation Approach

**Architecture**: Run bot command handler in separate thread, communicate with Monitor via shared StateManager and method calls.

### Files to Create

1. **`src/bot/__init__.py`** - Module initialization
2. **`src/bot/telegram_bot_handler.py`** - Main bot handler class with command processing
3. **`src/bot/commands.py`** - Command handler functions (optional, can inline in handler)

### Files to Modify

1. **`requirements.txt`** - Add `python-telegram-bot==21.7`
2. **`config/config.yaml`** - Add bot configuration section:
   ```yaml
   bot:
     enabled: false  # Enable when ready
     authorized_users: []  # Telegram user IDs
   ```
3. **`config/.env.example`** - Add authorized users template
4. **`src/monitor.py`** - Initialize and start bot handler in separate thread
5. **`README.md`** - Document bot commands and setup

### Commands to Implement

**Priority 1 (Essential)**:
- `/status` - Check if monitor is running, show current status
- `/check` - Trigger immediate check on all sites
- `/sites` - List monitored sites with current status
- `/help` - Show available commands

**Priority 2 (Useful)**:
- `/stats` - Detailed statistics (availability, response times)
- `/site <name>` - Get details for specific site

### Key Features

1. **Authorization**: User ID whitelist (via config and environment variable)
2. **Thread-safe**: Bot runs in separate thread, uses shared StateManager
3. **Non-blocking**: Commands don't interrupt monitoring loop
4. **Error handling**: Graceful error messages to users
5. **Long polling**: Simple approach, no webhooks/SSL needed

### Configuration

**Environment Variable** (add to `.env`):
```bash
TELEGRAM_AUTHORIZED_USERS=123456789,987654321
```

**Bot Config** (in `config.yaml`):
```yaml
bot:
  enabled: true
  commands_enabled:
    - status
    - check
    - sites
    - stats
    - help
```

### Technical Details

- **Library**: `python-telegram-bot` (well-documented, mature)
- **Threading**: Bot runs in daemon thread with own event loop
- **Communication**: Direct method calls to Monitor instance
- **State Access**: Read-only access to StateManager and MetricsCollector
- **Security**: Unauthorized users get "Access Denied" message

### Testing Strategy

1. Test authorization (authorized vs unauthorized users)
2. Test each command individually
3. Verify monitor continues running while bot processes commands
4. Test error handling (invalid commands, exceptions)

### Benefits

✅ Check monitor status remotely  
✅ Trigger checks on demand  
✅ Get real-time site status  
✅ Secure (user whitelist)  
✅ Non-invasive (optional feature)  
✅ Easy to extend with new commands  

### Risks & Mitigations

**Risk**: Thread safety issues  
**Mitigation**: Use read-only access to shared state, leverage StateManager's file-based persistence

**Risk**: Bot errors crash monitor  
**Mitigation**: Run in daemon thread, comprehensive error handling

**Risk**: Unauthorized access  
**Mitigation**: User ID whitelist, log all access attempts

### Estimated Complexity

**Medium** - Requires new module, threading coordination, but clean architecture with minimal changes to existing code.