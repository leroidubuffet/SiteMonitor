# Healthchecks.io Setup Guide

## Quick Start (5 Minutes)

This guide shows you how to set up external monitoring for your site monitor using Healthchecks.io (free).

### What You'll Get

- **External validation** that your monitor is running
- **Alerts when the monitor stops** (crashes, hangs, power loss)
- **Free tier:** 20 checks, email/SMS/Telegram notifications
- **Detection time:** 20-25 minutes

---

## Step-by-Step Setup

### 1. Sign Up for Healthchecks.io

1. Go to **https://healthchecks.io**
2. Click **"Sign Up"** (top right)
3. Register with email (no credit card needed)
4. Verify your email

**Cost:** FREE (20 checks included)

---

### 2. Create Your Check

1. Click the big **"Add Check"** button
2. Fill in the form:

```
Name:               Site Monitor Heartbeat
Tags:               monitoring, production
Schedule:           * * * * *
                    (this will be overridden by Period setting below)
Grace Time:         5 minutes
                    (how long to wait after expected ping before alerting)
Period:             20 minutes
                    (how often to expect pings: 15 min checks + 5 min buffer)
```

3. Click **"Save Check"**

---

### 3. Get Your Ping URL

After saving, you'll see a screen with:

**Ping URL:**
```
https://hc-ping.com/01234567-89ab-cdef-0123-456789abcdef
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                Your unique UUID
```

**Copy this entire URL** (you'll need it in the next step)

---

### 4. Configure Your Monitor

#### Option A: Edit `.env` file directly

```bash
# Edit config/.env
nano config/.env

# Add this line at the end:
HEALTHCHECK_PING_URL=https://hc-ping.com/your-uuid-here
```

#### Option B: Use echo command

```bash
# Replace YOUR_UUID with the actual UUID from step 3
echo "HEALTHCHECK_PING_URL=https://hc-ping.com/YOUR_UUID" >> config/.env
```

#### Verify it's set:

```bash
grep HEALTHCHECK config/.env
# Should show: HEALTHCHECK_PING_URL=https://hc-ping.com/...
```

---

### 5. Configure Notifications

Back in Healthchecks.io dashboard:

1. Click **"Integrations"** (in the left sidebar)
2. Click **"Add Integration"**
3. Choose your preferred notification method:

**Recommended:**
- **Email** - Always enable this (free, reliable)
- **Telegram** - If you're already using Telegram for the monitor
- **SMS** - For critical alerts (free tier: limited)

**Optional:**
- Slack, Discord, PagerDuty, etc.

4. Test the integration by clicking **"Test"**

---

### 6. Test It Works

#### Test 1: Check Heartbeats Are Sent

```bash
# Run a single check
python3 main.py --check-once

# Then check Healthchecks.io dashboard
# You should see "Last Ping: a few seconds ago" ✅
```

#### Test 2: Check Failure Detection (Optional)

```bash
# Start the monitor
python3 main.py

# Wait ~2 minutes for first heartbeat
# Check Healthchecks.io shows "UP" status

# Stop the monitor
Press Ctrl+C

# Wait 25 minutes
# You should receive an alert: "Site Monitor Heartbeat is DOWN"
```

---

## Troubleshooting

### Problem: "No pings received"

**Check 1:** Is the URL set in .env?
```bash
grep HEALTHCHECK config/.env
# Should show the URL
```

**Check 2:** Is healthcheck enabled in config?
```bash
grep -A2 "^healthcheck:" config/config.yaml
# Should show: enabled: true
```

**Check 3:** Are there errors in the logs?
```bash
grep -i healthcheck logs/monitor.log
# Should show: "Healthcheck.io monitoring enabled"
```

---

### Problem: "Too many false alerts"

Adjust the grace time in Healthchecks.io:

1. Go to your check
2. Click **"Edit"**
3. Increase **Grace Time** from `5 minutes` to `10 minutes`
4. Increase **Period** from `20 minutes` to `30 minutes`
5. Click **"Save"**

---

### Problem: "Monitor is running but Healthchecks.io shows DOWN"

This means checks are **failing** (not completing), so no pings are sent.

Check the monitor logs:
```bash
tail -50 logs/monitor.error.log
# Look for errors
```

Common causes:
- All sites are down (circuit breakers open)
- Network connectivity issues
- Authentication failures on all sites

---

## Understanding the Dashboard

### Check Status Indicators

| Icon | Status | Meaning |
|------|--------|---------|
| ✅ | **Up** | Pings received on schedule |
| ⏰ | **Grace** | Ping late, within grace period |
| ❌ | **Down** | No ping received, alert sent |
| ⏸️ | **Paused** | Check manually paused |

### Timeline

The timeline shows:
- 🟢 Green bars: Pings received on time
- 🟡 Yellow bars: Pings during grace period
- 🔴 Red bars: Missed pings (downtime)

### Last Ping Body

Shows the message from your monitor:
```
Checked 5 sites, 7 checks completed
```

This helps you verify the monitor is working correctly.

---

## Advanced Configuration

### Change Ping Interval

If you change your monitoring interval, update Healthchecks.io:

```yaml
# config/config.yaml
monitoring:
  interval_minutes: 30  # Changed from 15 to 30
```

Then update Healthchecks.io check:
- **Period:** `35 minutes` (30 + 5 grace)
- **Grace Time:** `5 minutes`

---

### Disable Healthcheck

To temporarily disable:

```yaml
# config/config.yaml
healthcheck:
  enabled: false
```

Or remove/comment out in `.env`:
```bash
# HEALTHCHECK_PING_URL=https://hc-ping.com/...
```

---

### Multiple Environments

For dev/staging/production, create separate checks:

```bash
# Production
HEALTHCHECK_PING_URL=https://hc-ping.com/prod-uuid

# Staging
HEALTHCHECK_PING_URL=https://hc-ping.com/staging-uuid
```

---

## What Gets Monitored

### ✅ Detected by Healthchecks.io

- Process crashes
- Process hangs (frozen)
- Out of memory kills
- Server power loss
- Network connectivity loss
- Scheduler failures
- Python exceptions during check cycle

### ❌ NOT Detected by Healthchecks.io

- Individual site failures (use Telegram notifications)
- Slow responses (use Telegram notifications)
- Authentication failures (use Telegram notifications)

**Remember:** Healthchecks.io monitors **the monitor itself**, not the sites. For site-specific alerts, use Telegram notifications.

---

## Cost Summary

### Free Tier (What You Get)

- ✅ 20 checks (you only need 1)
- ✅ 1,000 log entries per check
- ✅ 1 month of history
- ✅ Email notifications
- ✅ SMS notifications (100/month)
- ✅ All integrations (Slack, Telegram, etc.)
- ✅ API access
- ✅ Status badges

**This is more than sufficient for monitoring one or even multiple instances!**

### Paid Tiers (Optional)

Only needed if you have:
- More than 20 monitors to track
- Need more than 1 month of history
- Want priority support

**For this use case, free tier is perfect.**

---

## Next Steps

1. ✅ Set up Healthchecks.io account
2. ✅ Create check and get ping URL
3. ✅ Add URL to `config/.env`
4. ✅ Test with `python3 main.py --check-once`
5. ✅ Configure notifications (email + Telegram)
6. ✅ Run monitor: `python3 main.py`
7. ✅ Verify pings in dashboard

**You're done! Your monitor is now externally monitored.**

---

## Support

- **Healthchecks.io Docs:** https://healthchecks.io/docs/
- **Monitor Docs:** See README.md
- **Issues:** Check logs in `logs/monitor.log`
