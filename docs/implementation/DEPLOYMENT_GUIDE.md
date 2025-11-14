# Deployment Guide for Reliable 24/7 Monitoring

## Current Status: Sleep Prevention Enabled ✓

The monitor now **prevents your computer from sleeping** while running, ensuring reliable monitoring. However, for true 24/7 operation, consider deploying to always-on infrastructure.

---

## Why Deploy to Always-On Infrastructure?

**Current Setup (Your Laptop):**
- ❌ Computer must stay on 24/7
- ❌ Higher power consumption (~50-100W)
- ❌ Risk of accidental shutdown
- ❌ Laptop battery wear from constant charging
- ❌ No redundancy if computer crashes

**Always-On Infrastructure:**
- ✅ Low power (~2-15W)
- ✅ Designed for 24/7 operation
- ✅ Automatic restart on failure
- ✅ Remote access from anywhere
- ✅ Your laptop can sleep/shutdown

---

## Deployment Options (Ranked by Recommendation)

### Option 1: Raspberry Pi (Best for Home/Office) ⭐⭐⭐⭐⭐

**Cost**: $35-75 one-time
**Power**: ~3-5W ($5/year electricity)
**Difficulty**: Easy

**Why this is best:**
- Tiny (credit card size)
- Silent operation
- Extremely reliable
- Can be hidden behind monitor/desk
- Perfect for local network monitoring

**Setup Steps:**

```bash
# 1. Buy hardware
- Raspberry Pi 4 (2GB or 4GB): $35-55
- MicroSD card (32GB): $8
- USB-C power supply: $8
- Optional case: $5-10

# 2. Install Raspberry Pi OS Lite
# Download from: https://www.raspberrypi.com/software/
# Use Raspberry Pi Imager to flash SD card

# 3. SSH into Pi
ssh pi@raspberrypi.local
# Default password: raspberry (change immediately!)

# 4. Install dependencies
sudo apt update
sudo apt install -y python3 python3-pip git

# 5. Clone your monitor
cd ~
git clone [your-repo-url] monitor
cd monitor

# 6. Install Python dependencies
pip3 install -r requirements.txt

# 7. Copy credentials
scp config/.env pi@raspberrypi.local:~/monitor/config/

# 8. Create systemd service for auto-start
sudo nano /etc/systemd/system/sitemonitor.service
```

```ini
[Unit]
Description=Multi-Site Website Monitor
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/monitor
ExecStart=/usr/bin/python3 /home/pi/monitor/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# 9. Enable and start service
sudo systemctl enable sitemonitor
sudo systemctl start sitemonitor

# 10. Check status
sudo systemctl status sitemonitor
journalctl -u sitemonitor -f  # View logs
```

**Pros:**
- One-time cost
- No monthly fees
- Full control
- Local network access
- Low power

**Cons:**
- Requires physical setup
- No remote access (without VPN/port forwarding)
- Single point of failure

---

### Option 2: Cloud VM (DigitalOcean, Linode, Vultr) ⭐⭐⭐⭐

**Cost**: $5-6/month
**Power**: N/A (datacenter)
**Difficulty**: Medium

**Why use this:**
- Access from anywhere
- Automatic backups
- High uptime (99.99%)
- Easy scaling

**Setup Steps (DigitalOcean example):**

```bash
# 1. Create account at https://www.digitalocean.com
# Get $200 free credit for 60 days

# 2. Create Droplet
- Choose: Ubuntu 22.04 LTS
- Plan: Basic $6/month (1GB RAM)
- Region: Closest to your monitored sites
- SSH key: Add your public key

# 3. SSH into server
ssh root@your-droplet-ip

# 4. Create non-root user
adduser monitor
usermod -aG sudo monitor
su - monitor

# 5. Install dependencies
sudo apt update
sudo apt install -y python3 python3-pip git

# 6. Clone and setup
git clone [your-repo-url] ~/monitor
cd ~/monitor
pip3 install -r requirements.txt

# 7. Copy credentials (from local machine)
scp config/.env monitor@your-droplet-ip:~/monitor/config/

# 8. Setup systemd service (same as Raspberry Pi above)

# 9. Configure firewall
sudo ufw allow OpenSSH
sudo ufw enable

# 10. Optional: Setup automatic updates
sudo apt install unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

**Monitoring Providers Comparison:**

| Provider | Price | RAM | Storage | Bandwidth |
|----------|-------|-----|---------|-----------|
| DigitalOcean | $6/mo | 1GB | 25GB | 1TB |
| Linode | $5/mo | 1GB | 25GB | 1TB |
| Vultr | $6/mo | 1GB | 25GB | 1TB |
| AWS Lightsail | $5/mo | 1GB | 40GB | 2TB |

**Pros:**
- Professional infrastructure
- Automatic backups
- Remote access
- Easy migration

**Cons:**
- Monthly cost
- Requires cloud knowledge
- Dependent on provider

---

### Option 3: AWS/GCP Free Tier ⭐⭐⭐

**Cost**: FREE (12 months, then ~$5-10/mo)
**Power**: N/A
**Difficulty**: Hard

**AWS Free Tier:**
- t2.micro or t3.micro instance
- 750 hours/month (always-on)
- 30GB EBS storage
- Free for 12 months

**GCP Free Tier:**
- e2-micro instance
- 1 shared vCPU, 1GB RAM
- 30GB standard disk
- Always free (no time limit!)

**Setup:**
Similar to DigitalOcean, but requires AWS/GCP knowledge.

**Pros:**
- Free (AWS for 1 year, GCP forever)
- Enterprise-grade infrastructure
- Scalable

**Cons:**
- Complex setup
- Easy to accidentally incur charges
- Steep learning curve

---

### Option 4: Docker Container (On NAS/Home Server) ⭐⭐⭐⭐

**Cost**: $0 (if you have NAS)
**Power**: Negligible
**Difficulty**: Medium

**If you have a Synology/QNAP NAS or home server:**

```dockerfile
# Create Dockerfile in monitor directory
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python3", "main.py"]
```

```bash
# Build and run
docker build -t sitemonitor .
docker run -d \
  --name sitemonitor \
  --restart unless-stopped \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/logs:/app/logs \
  sitemonitor
```

**Synology NAS GUI:**
1. Open Docker app
2. Download Python image
3. Create container with volume mounts
4. Enable auto-restart

**Pros:**
- Free if you have hardware
- Container isolation
- Easy updates
- Auto-restart

**Cons:**
- Requires Docker knowledge
- Need existing server/NAS

---

### Option 5: GitHub Actions (For Simple Checks) ⭐⭐

**Cost**: FREE
**Difficulty**: Easy

**Note**: Only suitable for very basic uptime checks, **not** recommended for this full monitoring system.

**Why it doesn't work well:**
- ❌ 5-minute minimum interval (your checks are 15 min)
- ❌ No persistent state
- ❌ No Telegram bot interaction
- ❌ Limited to 6 hours per run

---

## Migration Checklist

Before deploying to new infrastructure:

- [ ] **Backup current state**
  ```bash
  cp logs/monitor_state.json logs/monitor_state.backup.json
  ```

- [ ] **Export credentials**
  ```bash
  # Credentials are in config/.env (gitignored)
  # Safely transfer to new system via scp/sftp
  ```

- [ ] **Test on new system**
  ```bash
  python3 main.py --check-once
  ```

- [ ] **Verify Telegram bot works**
  ```bash
  # Send /status command to bot
  # Should respond immediately
  ```

- [ ] **Setup monitoring for the monitor**
  ```bash
  # Use healthchecks.io or similar
  # Configure in config/config.yaml:
  healthcheck:
    enabled: true
    # Add HEALTHCHECK_URL to config/.env
  ```

- [ ] **Configure automatic restarts**
  ```bash
  # Use systemd (Linux) or supervisor
  # Ensures monitor restarts after crashes/reboots
  ```

- [ ] **Setup log rotation**
  ```bash
  sudo nano /etc/logrotate.d/sitemonitor
  ```
  ```
  /home/monitor/logs/*.log {
      daily
      rotate 30
      compress
      delaycompress
      missingok
      notifempty
  }
  ```

---

## Current Setup (Laptop with Sleep Prevention)

**What's working now:**
```
✓ Sleep prevention enabled (caffeinate on macOS)
✓ Computer stays awake while monitor runs
✓ All checks run on schedule
✓ Telegram bot responds
✓ Resource leaks fixed
```

**Limitations:**
```
⚠ Computer must stay on 24/7
⚠ Higher power consumption
⚠ Manual restart after power loss
⚠ No redundancy
```

**Power consumption comparison:**
- **Your laptop**: ~50-100W = $50-100/year
- **Raspberry Pi**: ~3-5W = $3-5/year
- **Cloud VM**: N/A, ~$60-72/year

---

## Recommendations by Use Case

**Home/Office, Local Network:**
→ **Raspberry Pi** (Best value, one-time cost)

**Need Remote Access:**
→ **Cloud VM** (DigitalOcean/Linode)

**Free for 12 months:**
→ **AWS Free Tier** (then migrate to paid)

**Already have NAS/Server:**
→ **Docker Container**

**Learning/Testing:**
→ **Keep laptop setup** (works well with sleep prevention)

---

## Support & Troubleshooting

**Raspberry Pi not working?**
```bash
# Check service status
sudo systemctl status sitemonitor

# View logs
journalctl -u sitemonitor -n 100

# Restart service
sudo systemctl restart sitemonitor
```

**Cloud VM connection issues?**
```bash
# Check firewall
sudo ufw status

# Test from local machine
ping your-server-ip
ssh monitor@your-server-ip
```

**Monitor not sending alerts?**
```bash
# Check Telegram credentials
python3 -c "import os; from dotenv import load_dotenv; load_dotenv('config/.env'); print(os.getenv('TELEGRAM_BOT_TOKEN'))"

# Test manually
python3 main.py --check-once
```

---

## Next Steps

1. **Short-term (Now)**: Keep using laptop with sleep prevention ✓
2. **Medium-term (1-2 weeks)**: Order Raspberry Pi, set up in parallel
3. **Long-term (1 month)**: Migrate to Pi, decommission laptop setup

Questions? Check logs or review the monitor output for errors.

---

**Last Updated**: 2025-11-14
**Version**: 2.0
