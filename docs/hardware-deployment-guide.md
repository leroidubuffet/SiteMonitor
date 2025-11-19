# Hardware Deployment Guide

## Table of Contents
- [System Requirements Analysis](#system-requirements-analysis)
- [Raspberry Pi Options](#raspberry-pi-options)
- [Alternative Hardware](#alternative-hardware)
- [Cloud/VPS Options](#cloudvps-options)
- [Cost Comparison](#cost-comparison)
- [Recommendation](#recommendation)

---

## System Requirements Analysis

### Current Workload Profile

**What this monitoring system does**:
- Checks 6 websites every 15 minutes (24 checks/hour)
- HTTP requests with SSL verification
- HTML parsing (BeautifulSoup) for authentication checks
- Telegram bot polling every ~10 seconds
- JSON state persistence (no database)
- Log file writing
- Minimal network traffic (~1-2 MB/hour)

### Resource Usage Estimates

**CPU**:
- Idle: ~5-10% (Telegram polling, Python runtime)
- During checks: ~20-30% spike for 10-30 seconds
- Average: ~10-15% CPU usage

**RAM**:
- Python runtime: ~50-80 MB
- Dependencies (httpx, BeautifulSoup, etc.): ~30-50 MB
- Telegram bot: ~20-30 MB
- OS overhead (Raspberry Pi OS Lite): ~100-150 MB
- **Total: ~200-300 MB active, ~500 MB safe**

**Storage**:
- Application code: ~5 MB
- Python dependencies: ~50-100 MB
- Logs (with rotation): ~10-50 MB
- State files: <1 MB
- **Total: ~200 MB (1 GB minimum, 8 GB comfortable)**

**Network**:
- Monitoring traffic: ~1-2 MB/hour
- Telegram: ~500 KB/hour
- System updates: occasional
- **Total: ~5 GB/month**

**Conclusion**: This is an extremely lightweight application. Almost any modern computing device can handle it.

---

## Raspberry Pi Options

### Raspberry Pi Zero 2 W
https://www.raspberrypi.com/products/raspberry-pi-zero-2-w/

**Specs**:
- CPU: Quad-core ARM Cortex-A53 @ 1 GHz
- RAM: 512 MB
- Storage: MicroSD card
- Network: 2.4GHz WiFi, Bluetooth
- Power: ~0.4W idle, ~1W active
- Size: 65mm × 30mm (tiny!)

**Price**: ~$15 USD

**Pros**:
- Cheapest option
- Extremely low power consumption
- Tiny form factor (easy to hide anywhere)
- Built-in WiFi (no Ethernet needed)
- Sufficient for this workload

**Cons**:
- Only 512 MB RAM (tight but workable)
- Single-core performance is modest
- WiFi only (2.4GHz can be unreliable)
- No Ethernet port
- MicroSD can be slower

**Verdict**: ✅ **Sufficient, but minimal headroom**
- Works fine for 6 sites
- May struggle with 20+ sites or heavy HTML parsing
- Good for budget/space-constrained deployments

---

### Raspberry Pi 3 Model B+
https://www.raspberrypi.com/products/raspberry-pi-3-model-b-plus/

**Specs**:
- CPU: Quad-core ARM Cortex-A53 @ 1.4 GHz
- RAM: 1 GB
- Storage: MicroSD card
- Network: Gigabit Ethernet (limited to ~300 Mbps), 2.4/5GHz WiFi
- Power: ~1.5W idle, ~3.5W active
- Size: 85mm × 56mm (standard Pi size)

**Price**: ~$35 USD (often available used for $15-20)

**Pros**:
- 1 GB RAM (comfortable headroom)
- Faster CPU than Zero 2 W
- Ethernet + dual-band WiFi
- Widely available, mature platform
- Better thermals than Pi 4

**Cons**:
- Older model (Pi 4/5 are faster)
- MicroSD card storage (slower, less reliable)
- Limited to USB 2.0

**Verdict**: ✅✅ **Sweet spot for this use case**
- Plenty of power for monitoring
- Reliable Ethernet connection
- Good availability on used market
- Low power consumption

---

### Raspberry Pi 4 Model B (2GB/4GB/8GB)

**Specs**:
- CPU: Quad-core ARM Cortex-A72 @ 1.5-1.8 GHz
- RAM: 2 GB / 4 GB / 8 GB options
- Storage: MicroSD card (can boot from USB SSD)
- Network: Gigabit Ethernet (full speed), 2.4/5GHz WiFi
- Power: ~2.7W idle, ~6W active
- USB 3.0 ports
- Size: 85mm × 56mm

**Price**:
- 2 GB: ~$45 USD
- 4 GB: ~$55 USD
- 8 GB: ~$75 USD

**Pros**:
- Powerful CPU (overkill for this app)
- 2 GB is more than enough RAM
- Can boot from USB SSD (more reliable than SD card)
- USB 3.0 for fast storage
- True Gigabit Ethernet
- Dual 4K display support (useful for multi-purpose use)

**Cons**:
- More expensive
- Higher power consumption (heats up more)
- May require active cooling
- Overkill for simple monitoring

**Verdict**: ✅✅✅ **Best if using Pi for multiple purposes**
- Great if you want to run other services (Pi-hole, Home Assistant, etc.)
- 2 GB model is perfect for monitoring
- Future-proof for expanded monitoring

---

### Raspberry Pi 5 (4GB/8GB)

**Specs**:
- CPU: Quad-core ARM Cortex-A76 @ 2.4 GHz
- RAM: 4 GB / 8 GB options
- Storage: MicroSD card or NVMe SSD (with HAT)
- Network: Gigabit Ethernet, 2.4/5GHz WiFi
- Power: ~3.7W idle, ~8W active
- PCIe 2.0 support (NVMe SSDs!)
- Size: 85mm × 56mm

**Price**:
- 4 GB: ~$60 USD
- 8 GB: ~$80 USD

**Pros**:
- Fastest Raspberry Pi (2-3x faster than Pi 4)
- NVMe SSD support (ultra-reliable storage)
- PCIe expansion possibilities
- Future-proof
- Better USB/IO performance

**Cons**:
- Most expensive
- Requires separate power supply (~$12)
- May require active cooling
- Massive overkill for monitoring
- Higher power consumption

**Verdict**: ⚠️ **Overkill, but excellent for multi-purpose use**
- Only consider if running multiple services
- Great for expanding to home automation hub
- NVMe storage is a game-changer for reliability

---

## Alternative Hardware

### Option 1: Orange Pi Zero 2

**Specs**:
- CPU: Quad-core ARM Cortex-A53 @ 1.5 GHz
- RAM: 512 MB / 1 GB
- Network: Gigabit Ethernet, WiFi
- Power: ~0.5W idle, ~1.5W active

**Price**: ~$20-25 USD

**Pros**:
- Cheaper than Raspberry Pi
- Good performance/price ratio
- Gigabit Ethernet on small form factor
- Low power consumption

**Cons**:
- Less community support
- Software ecosystem not as mature
- May require manual kernel/driver setup
- Quality control varies

**Verdict**: ✅ **Good budget alternative if comfortable with Linux**

---

### Option 2: Old Laptop/Desktop

**Specs**: Any laptop from last 10 years

**Price**: $0 (if you have one) or $50-100 used

**Pros**:
- FREE if you have old hardware lying around
- More powerful than any Pi
- Built-in UPS (laptop battery)
- Easier to troubleshoot
- Full x86 compatibility
- Can run full desktop Linux

**Cons**:
- Much higher power consumption (15-50W)
- Larger physical size
- Overkill resources
- Battery degradation over time
- More noise (fans)

**Verdict**: ✅ **Best "free" option, but higher operating cost**
- Power cost: ~$1.50-5/month (vs $0.20/month for Pi)
- Good for testing before buying dedicated hardware

---

### Option 3: Intel NUC / Mini PC

**Specs** (example: Intel N100 mini PC):
- CPU: Intel N100 (4 cores, 3.4 GHz)
- RAM: 8-16 GB
- Storage: 128-256 GB SSD
- Network: Gigabit Ethernet, WiFi
- Power: ~6-10W

**Price**: ~$120-200 USD

**Pros**:
- x86 architecture (better compatibility)
- Fast SSD storage included
- Quiet, fanless models available
- More RAM and storage than Pi
- Can run Windows/Linux easily
- Good for multiple services

**Cons**:
- More expensive upfront
- Higher power consumption than Pi
- Larger form factor
- Overkill for simple monitoring

**Verdict**: ✅✅ **Best for serious home server use**
- Great if expanding to multiple services
- Better performance/reliability than Pi
- Worth it if running 10+ services

---

### Option 4: Virtual Private Server (VPS)

**Specs** (example: Hetzner CX11):
- CPU: 1 vCore
- RAM: 2 GB
- Storage: 20 GB SSD
- Network: 20 TB traffic
- Datacenter uptime: 99.9%+

**Price**: ~$4-5/month (~$50-60/year)

**Providers**:
- **Hetzner Cloud**: €3.79/month (~$4) - Best value
- **DigitalOcean**: $6/month - Easy to use
- **Linode/Akamai**: $5/month - Reliable
- **Vultr**: $3.50/month - Budget option
- **Oracle Cloud**: FREE tier (1-2 VMs forever)

**Pros**:
- No hardware to maintain
- Professional datacenter (UPS, redundancy)
- Better uptime than home internet
- Static IP included
- Easy to scale up/down
- Automatic backups available
- No power/internet outages at home affect it
- No initial hardware cost

**Cons**:
- Ongoing monthly cost
- Requires internet connection
- Data leaves your premises
- Need to trust VPS provider with credentials (use SOPS!)
- Slightly more latency (but irrelevant for monitoring)

**Verdict**: ✅✅✅ **Best for reliability and simplicity**
- No hardware failures
- Better uptime than home setup
- Oracle Cloud free tier = $0 forever
- Easier than managing physical hardware

---

### Option 5: Docker on Existing Server

**Specs**: Any existing server you already run

**Price**: $0 (using existing hardware)

**Pros**:
- Free if you have existing infrastructure
- Easy deployment with Docker Compose
- Isolated from other services
- Can run on NAS (Synology, QNAP, etc.)
- Resource sharing with other containers

**Cons**:
- Requires existing server
- Adds to server load (minimal)
- Depends on server uptime

**Verdict**: ✅✅✅ **Perfect if you have existing infrastructure**

**Example Docker Compose**:
```yaml
version: '3.8'
services:
  site-monitor:
    build: .
    container_name: site-monitor
    restart: unless-stopped
    volumes:
      - ./config:/app/config
      - ./logs:/app/logs
    environment:
      - TZ=Europe/Madrid
    env_file:
      - config/.env
```

---

## Cloud/VPS Options Detailed

### Oracle Cloud Free Tier (Best Free Option)

**What you get FOREVER (no credit card required after initial verification)**:
- 2 AMD-based VMs (1 GB RAM, 1 OCPU each) OR
- 1 ARM-based VM (24 GB RAM, 4 OCPUs) - insane!
- 200 GB total storage
- 10 TB/month outbound traffic

**Cost**: $0 forever

**Setup time**: ~30 minutes

**Pros**:
- Completely free forever
- ARM VM is incredibly powerful (overkill x100)
- Professional datacenter uptime
- No home internet dependency

**Cons**:
- Oracle account required
- Slightly complex initial setup
- Oracle may reclaim inactive resources (run monitoring = active)
- UI is clunky

**Verdict**: ⭐ **Best option if you don't want to buy hardware**

**Perfect for**:
- Testing before buying hardware
- Maximum uptime requirements
- No upfront cost
- Learning cloud deployments

---

### Hetzner Cloud CX11 (Best Paid VPS)

**Specs**:
- 1 vCore (AMD/Intel)
- 2 GB RAM
- 20 GB SSD
- 20 TB traffic
- Germany/Finland datacenters

**Cost**: €3.79/month (~$4/month, ~$48/year)

**Pros**:
- Excellent price/performance
- European data centers (GDPR compliant)
- Great network (low latency)
- Hourly billing (pay for what you use)
- Easy to use dashboard
- Great documentation

**Cons**:
- Monthly cost (but very cheap)
- Requires payment method

**Verdict**: ⭐⭐ **Best paid option for Europe**

---

## Cost Comparison

### 5-Year Total Cost of Ownership

| Option | Upfront | Monthly Power | Annual Cost | 5-Year Total |
|--------|---------|---------------|-------------|--------------|
| **Raspberry Pi Zero 2 W** | $15 | $0.07 | $15.84 | $19 |
| **Raspberry Pi 3 B+** | $35 | $0.25 | $38 | $41 |
| **Raspberry Pi 4 (2GB)** | $45 | $0.50 | $51 | $51 |
| **Orange Pi Zero 2** | $20 | $0.10 | $21.20 | $21 |
| **Old Laptop (50W)** | $0 | $3.60 | $43.20 | $216 |
| **Intel N100 Mini PC** | $150 | $0.72 | $158.64 | $159 |
| **Hetzner VPS** | $0 | $0 | $48 | $240 |
| **Oracle Cloud Free** | $0 | $0 | $0 | $0 |

**Assumptions**:
- Power cost: $0.12/kWh (US average)
- Raspberry Pi runs 24/7
- VPS costs remain stable
- No hardware failures

**Notes**:
- Raspberry Pi costs include MicroSD card (~$8)
- VPS has no hardware maintenance/replacement
- Old laptop assumes you already own it

---

## Power Consumption Analysis

### Annual Power Cost (24/7 operation)

| Device | Power Draw | Daily kWh | Annual kWh | Annual Cost ($0.12/kWh) |
|--------|------------|-----------|------------|------------------------|
| **Pi Zero 2 W** | 0.5W | 0.012 | 4.38 | $0.53 |
| **Pi 3 B+** | 2W | 0.048 | 17.52 | $2.10 |
| **Pi 4 (2GB)** | 4W | 0.096 | 35.04 | $4.20 |
| **Orange Pi Zero 2** | 1W | 0.024 | 8.76 | $1.05 |
| **Intel N100** | 8W | 0.192 | 70.08 | $8.41 |
| **Old Laptop** | 50W | 1.2 | 438 | $52.56 |

**Environmental Impact**:
- Raspberry Pi Zero 2 W: ~2 kg CO₂/year
- Old Laptop: ~200 kg CO₂/year
- VPS: ~50 kg CO₂/year (datacenter efficiency)

---

## Reliability Considerations

### Mean Time Between Failures (MTBF)

**Raspberry Pi with MicroSD**:
- SD card failure: ~1-3 years (heavy writes)
- Solution: Use read-only filesystem or USB SSD boot
- Mitigation: Regular backups, log rotation

**Raspberry Pi with USB SSD**:
- SSD failure: ~5-10 years
- Much more reliable than SD card
- Recommended for 24/7 operation

**VPS**:
- Provider handles hardware failures
- Redundant storage (RAID)
- Typical uptime: 99.9%+ (8.76 hours/year downtime)

**Old Laptop**:
- Battery degrades (1-3 years)
- Fan failures possible
- Generally reliable if kept cool

---

## Recommendation

### For Your Use Case (6 Sites, Home Monitoring)

**Best Overall**: **Raspberry Pi 3 B+** or **Pi 4 (2GB)**

**Why**:
- Plenty of power for current + future expansion (up to 20-30 sites)
- Reliable Ethernet connection
- Low power consumption (~$2-4/year)
- No ongoing monthly costs
- Easy to maintain
- Can repurpose for other home projects

**Where to Buy**:
- Official: [raspberrypi.com](https://www.raspberrypi.com/products/)
- US: Adafruit, CanaKit, Micro Center
- Europe: Pimoroni, The Pi Hut
- Used market: eBay, Facebook Marketplace (~$15-25 for Pi 3 B+)

---

### Budget Option: **Raspberry Pi Zero 2 W**

**If**:
- Limited budget (<$20)
- Monitoring <10 sites
- Space constrained
- WiFi is reliable in your location

**Risks**:
- Less headroom for expansion
- WiFi reliability concerns
- May need to optimize code for 512 MB RAM

---

### Best Reliability: **Oracle Cloud Free Tier ARM VM**

**If**:
- Want maximum uptime (datacenter > home internet)
- Don't mind cloud deployment
- Want to learn cloud infrastructure
- No upfront hardware cost
- Don't want to manage physical hardware

**Perfect for**:
- Critical monitoring (business websites)
- Unstable home internet
- Frequent power outages in your area
- Remote/distributed monitoring

---

### Best Long-Term: **Intel N100 Mini PC**

**If**:
- Planning to run multiple services (Pi-hole, Home Assistant, Plex, etc.)
- Want x86 compatibility
- Need more storage/RAM
- Willing to invest upfront

---

## Recommended Shopping List

### Option A: Raspberry Pi 3 B+ Setup ($50 total)

- Raspberry Pi 3 B+: $35 (or $15-20 used)
- Power supply (2.5A): $8
- MicroSD card (32 GB): $8
- Case with fan: $10
- Total: ~$50-60 new, ~$30-40 used

### Option B: Raspberry Pi 4 (2GB) Reliable Setup ($80 total)

- Raspberry Pi 4 (2GB): $45
- Official power supply: $8
- USB 3.0 SSD (128 GB): $15-20
- Case with fan: $10
- Total: ~$80

**Why SSD**: 10x more reliable than MicroSD for 24/7 operation

### Option C: Oracle Cloud Free (Software Only)

- Cost: $0
- Just need an Oracle account
- Deploy via SSH

---

## Setup Difficulty Comparison

| Option | Setup Time | Linux Skills | Ongoing Maintenance |
|--------|------------|--------------|---------------------|
| **Raspberry Pi** | 1-2 hours | Beginner | Low (monthly updates) |
| **Orange Pi** | 2-3 hours | Intermediate | Medium (less support) |
| **VPS** | 30 min | Intermediate | Very Low (auto updates) |
| **Docker on NAS** | 30 min | Beginner | Very Low (GUI management) |
| **Old Laptop** | 1 hour | Beginner | Low |

---

## Decision Flowchart

```
START: What's your priority?

├─ Absolute lowest cost?
│  └─ Oracle Cloud Free Tier (ARM VM) → $0 forever
│
├─ Lowest hardware cost + own hardware?
│  └─ Raspberry Pi Zero 2 W → $15
│
├─ Best reliability + no hardware management?
│  └─ Hetzner VPS → $4/month
│
├─ Best value for home deployment?
│  └─ Raspberry Pi 3 B+ (used) → $20-25
│
├─ Want to run multiple services?
│  └─ Intel N100 Mini PC → $150
│
├─ Already have old laptop/desktop?
│  └─ Use it! → $0 hardware, higher power cost
│
└─ Maximum reliability + home deployment?
   └─ Raspberry Pi 4 with USB SSD → $80
```

---

## Next Steps

### If choosing Raspberry Pi:

1. **Purchase hardware** (see shopping list above)
2. **Install Raspberry Pi OS Lite** (no desktop needed)
   ```bash
   # Use Raspberry Pi Imager
   # Select: Raspberry Pi OS Lite (64-bit)
   # Enable SSH in advanced options
   ```
3. **Follow deployment guide** in this repository
4. **Set up systemd service** (see credential-management.md)
5. **Configure remote access** (SSH keys, firewall)

### If choosing VPS:

1. **Sign up for Oracle Cloud Free Tier** or Hetzner
2. **Create Ubuntu 22.04 VM** (ARM for Oracle, x86 for Hetzner)
3. **Secure the server**:
   ```bash
   # Update system
   sudo apt update && sudo apt upgrade -y

   # Install firewall
   sudo ufw allow ssh
   sudo ufw enable

   # Disable password auth (SSH keys only)
   sudo nano /etc/ssh/sshd_config
   # Set: PasswordAuthentication no
   ```
4. **Deploy application** (clone repo, install deps, set up systemd)
5. **Set up automatic updates**

---

## Conclusion

**For most users**: **Raspberry Pi 3 B+** or **Pi 4 (2GB)** is the sweet spot
- Costs ~$30-50
- Runs for years on ~$2-4/year power
- Perfect for home monitoring
- Can expand to other projects

**For maximum uptime**: **Oracle Cloud Free Tier**
- $0 cost forever
- Datacenter reliability
- No hardware management

**For enterprise/business**: **Paid VPS** (Hetzner, DigitalOcean)
- Professional SLA
- Easy scaling
- Support available

All options will easily handle this monitoring workload. Choose based on your priorities: cost, reliability, learning opportunity, or convenience.
