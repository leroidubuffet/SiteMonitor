# MacBook Pro Linux Installation Guide

## Table of Contents
- [Overview](#overview)
- [Installation Approaches Comparison](#installation-approaches-comparison)
- [Full Linux Installation](#full-linux-installation)
- [Partition-Based Dual Boot](#partition-based-dual-boot)
- [Minimal macOS + Linux Hybrid](#minimal-macos--linux-hybrid)
- [Storage Analysis](#storage-analysis)
- [Firmware Management](#firmware-management)
- [Recommended Migration Strategy](#recommended-migration-strategy)
- [Installation Instructions](#installation-instructions)
- [Post-Installation Configuration](#post-installation-configuration)
- [Troubleshooting](#troubleshooting)

---

## Overview

This guide helps you decide between different Linux installation approaches on a 2014 MacBook Pro for use as a home server. The key decision is whether to completely replace macOS with Linux or maintain a dual-boot setup.

**Target Hardware**: MacBook Pro (2014)
- 13-inch: Intel Core i5/i7, 8-16 GB RAM, 128-512 GB SSD
- 15-inch: Intel Core i7, 8-16 GB RAM, 256-512 GB SSD

**Use Case**: 24/7 home server running monitoring tools, Docker containers, and other services

---

## Installation Approaches Comparison

### Quick Comparison Table

| Factor | Full Linux | Dual Boot | Minimal macOS |
|--------|-----------|-----------|---------------|
| **Storage Available** | ⭐⭐⭐ Maximum | ⭐⭐ Limited | ⭐⭐⭐ Good |
| **Simplicity** | ⭐⭐⭐ Simple | ⭐ Complex | ⭐⭐ Moderate |
| **Firmware Updates** | ⭐ Difficult | ⭐⭐⭐ Easy | ⭐⭐⭐ Easy |
| **Recovery Options** | ⭐ Limited | ⭐⭐⭐ Good | ⭐⭐ Moderate |
| **Server Performance** | ⭐⭐⭐ Best | ⭐⭐ Good | ⭐⭐⭐ Best |
| **Beginner Friendly** | ⭐⭐ Risky | ⭐⭐⭐ Safe | ⭐⭐ Moderate |
| **Boot Speed** | ⭐⭐⭐ Fast | ⭐⭐ Slower | ⭐⭐ Moderate |
| **Maintenance** | ⭐⭐⭐ Simple | ⭐ Complex | ⭐⭐ Moderate |

---

## Full Linux Installation

### Overview
Completely replace macOS with Linux, using the entire SSD for the Linux system.

### Advantages ✅

**1. Maximum Storage Efficiency**
- Use 100% of SSD for Linux
- No space wasted on unused macOS partition
- Critical for 128 GB models
- More room for Docker images, logs, databases

**2. Simpler Boot Process**
- Direct boot to Linux (no bootloader selection)
- No rEFInd or GRUB complexity
- Faster boot times (5-10 seconds saved)
- Single partition table (less corruption risk)

**3. Better Performance**
- No macOS background processes
- Full RAM available to Linux
- No dual-boot overhead
- Cleaner system resource allocation

**4. Server-Focused**
- Single-purpose machine
- Professional server setup
- No temptation to use as laptop
- Easier to manage remotely

**5. Simplified Maintenance**
- One OS to update
- Single backup strategy
- No partition management
- Cleaner system architecture

**6. Firmware Support**
- Modern Linux supports Mac firmware updates (limited)
- Can use fwupd for some components
- UEFI firmware updates possible via Linux

### Disadvantages ⚠️

**1. No Safety Net**
- Can't boot to macOS if Linux has critical issues
- Recovery requires USB drive
- Harder to fix boot failures
- Need external backup/recovery tools

**2. Lost macOS-Specific Tools**
- No Apple Hardware Test (hold D at boot)
- No native firmware update mechanism
- Can't use official SMC/NVRAM tools
- No macOS battery calibration utilities

**3. Firmware Update Challenges**
- Apple firmware updates require macOS
- Need to reinstall macOS temporarily for updates
- Or rely on Linux tools (limited support)
- More manual intervention required

**4. Resale Considerations**
- Some buyers prefer macOS included
- Minor impact on 10-year-old machine
- Can reinstall macOS from USB if selling

**5. No Easy Rollback**
- Can't easily switch back to laptop use
- Need full macOS reinstall to restore
- More commitment required upfront

### When to Choose Full Linux

✅ **Recommended if you**:
- Commit to dedicated server use (24/7 operation)
- Need maximum storage space (especially 128 GB models)
- Want simplest, cleanest setup
- Are comfortable with Linux
- Won't need macOS for next 1+ years
- Have external backup/recovery plan

❌ **Not recommended if you**:
- Are new to Linux on Mac hardware
- Might need macOS occasionally
- Want easy firmware updates
- Uncertain about server commitment
- Plan to sell/repurpose soon

---

## Partition-Based Dual Boot

### Overview
Keep macOS and install Linux on a separate partition, using a bootloader (rEFInd) to choose between them at startup.

### Advantages ✅

**1. Safety and Flexibility**
- macOS available if Linux breaks
- Easy troubleshooting from familiar environment
- Can switch back to laptop use anytime
- Lower risk for learning/experimentation

**2. Firmware Management**
- Official Apple firmware updates via macOS
- SMC (System Management Controller) reset tools
- NVRAM management utilities
- Battery calibration tools available

**3. Hardware Diagnostics**
- Apple Hardware Test (hold D at boot)
- Official battery health monitoring
- Thermal management tools
- Sensor monitoring utilities

**4. Convenience**
- Keep familiar macOS environment
- Access macOS apps when needed
- Easy file transfer between OSes
- Better for occasional dual use

**5. Better Resale Value**
- Machine retains original OS
- Easier to sell to wider audience
- More buyer appeal
- Quick to restore to macOS-only

**6. Learning Curve**
- Test Linux without full commitment
- Safe environment to learn
- Easy to revert if needed
- Lower psychological barrier

### Disadvantages ⚠️

**1. Storage Waste**
- macOS requires 15-30 GB minimum
- 40-50 GB for comfortable use
- Significant on 128 GB models
- Space unavailable to either OS

**2. Complexity**
- Requires bootloader management (rEFInd)
- Partition table corruption risk
- More complex backup strategy
- Two systems to maintain/update

**3. Boot Process**
- Must select OS at each boot
- Can accidentally boot wrong OS
- Slower startup (10-15 seconds delay)
- Bootloader configuration needed

**4. Resource Overhead**
- Two sets of system caches
- Duplicated system files
- More complexity = more failure points
- Partition management ongoing

**5. Performance Impact**
- Slightly slower boot times
- Partition boundaries (minor impact)
- Bootloader overhead
- Wasted RAM on inactive OS files

### When to Choose Dual Boot

✅ **Recommended if you**:
- Are new to Linux on Mac
- Want to learn Linux gradually
- Might need macOS occasionally
- Have 256 GB+ storage
- Uncertain about server commitment
- Want firmware update convenience

❌ **Not recommended if you**:
- Have 128 GB SSD (too cramped)
- Want dedicated server (unnecessary complexity)
- Are experienced with Linux
- Won't use macOS for months

---

## Minimal macOS + Linux Hybrid

### Overview
A compromise approach: Keep a minimal macOS installation (30-40 GB) solely for firmware updates and diagnostics, dedicating the rest to Linux.

### Configuration

**Partition Layout** (256 GB model example):
- macOS: 35 GB (minimal, no apps/files)
- Linux: 215 GB (85% of drive)
- Boot: rEFInd (auto-boot to Linux)

**macOS Usage**: Only boot once every 3-6 months for:
- Firmware updates
- Battery calibration
- Hardware diagnostics
- SMC/NVRAM management

### Advantages ✅

**1. Best of Both Worlds**
- 85-90% storage for Linux
- Firmware update capability retained
- Safety net for emergencies
- Professional server setup

**2. Firmware Management**
- Official Apple updates available
- Boot to macOS when needed
- Full diagnostic tools
- No compromises on hardware management

**3. Storage Efficiency**
- Nearly as much as full Linux
- Only 30-40 GB "sacrifice"
- Acceptable tradeoff for peace of mind
- Still room for all server needs

**4. Recovery Options**
- Can boot macOS for troubleshooting
- Reinstall Linux without USB
- Better than USB-only recovery
- Familiar environment available

### Disadvantages ⚠️

**1. Still Dual Boot Complexity**
- Need bootloader (rEFInd)
- Partition management
- Two OSes to update (occasionally)
- More complex than full Linux

**2. "Wasted" Space**
- 30-40 GB unused most of time
- Could be Docker storage
- Psychological "waste"
- Not truly wasted, but feels inefficient

**3. Maintenance Burden**
- macOS security updates (occasional)
- Keep macOS bootable
- Test macOS boot periodically
- Two backup strategies

### When to Choose Minimal macOS

✅ **Recommended if you**:
- Want server dedication but with safety
- Have 256 GB+ storage (comfortable space)
- Value firmware update convenience
- Like having "just in case" option
- Are somewhat experienced with Linux

❌ **Not recommended if you**:
- Have 128 GB SSD (too tight)
- Want absolute simplicity
- Never want to touch macOS again
- Need every GB for services

---

## Storage Analysis

### 128 GB Model

#### Full Linux
```
Total: 128 GB
System (Linux): 12 GB
Swap: 4 GB
Available: 112 GB

Usable for server: ~110 GB
```

#### Dual Boot
```
Total: 128 GB
macOS: 40 GB
Linux System: 10 GB
Swap: 4 GB
Partition overhead: 2 GB
Available: 72 GB

Usable for server: ~70 GB
```

#### Minimal macOS
```
Total: 128 GB
macOS (minimal): 30 GB
Linux System: 10 GB
Swap: 4 GB
Partition overhead: 2 GB
Available: 82 GB

Usable for server: ~80 GB
```

**Verdict for 128 GB**: Full Linux gives **40 GB more** than dual boot. This is significant.

---

### 256 GB Model

#### Full Linux
```
Total: 256 GB
System (Linux): 15 GB
Swap: 8 GB
Available: 233 GB

Usable for server: ~230 GB
```

#### Dual Boot
```
Total: 256 GB
macOS: 50 GB
Linux System: 12 GB
Swap: 8 GB
Partition overhead: 3 GB
Available: 183 GB

Usable for server: ~180 GB
```

#### Minimal macOS
```
Total: 256 GB
macOS (minimal): 35 GB
Linux System: 12 GB
Swap: 8 GB
Partition overhead: 3 GB
Available: 198 GB

Usable for server: ~195 GB
```

**Verdict for 256 GB**: Full Linux gives **50 GB more** than dual boot, **35 GB more** than minimal. Still significant but less critical.

---

### 512 GB Model

#### Full Linux
```
Total: 512 GB
System (Linux): 20 GB
Swap: 16 GB
Available: 476 GB

Usable for server: ~470 GB
```

#### Dual Boot
```
Total: 512 GB
macOS: 80 GB
Linux System: 15 GB
Swap: 16 GB
Partition overhead: 4 GB
Available: 397 GB

Usable for server: ~390 GB
```

#### Minimal macOS
```
Total: 512 GB
macOS (minimal): 40 GB
Linux System: 15 GB
Swap: 16 GB
Partition overhead: 4 GB
Available: 437 GB

Usable for server: ~430 GB
```

**Verdict for 512 GB**: Space is abundant. Choose based on preference, not storage constraints.

---

## Firmware Management

### Importance of Firmware Updates

**What firmware includes**:
- Boot ROM (UEFI/EFI)
- SMC (System Management Controller) - power management
- Battery management firmware
- Thunderbolt controller
- SSD controller
- Keyboard/trackpad firmware

**Why updates matter**:
- Security patches (critical!)
- Battery life improvements
- Hardware bug fixes
- Performance optimizations
- Compatibility updates

### Updating with Full Linux

**Option 1: Temporary macOS Install**
```bash
# Steps:
1. Boot from macOS USB installer
2. Install macOS to external USB drive
3. Boot from USB drive
4. Run all software updates
5. Firmware updates install automatically
6. Reboot back to Linux
7. Erase USB drive

Time: ~2 hours
Frequency: Once every 6-12 months
```

**Option 2: Linux Firmware Tools (Limited)**
```bash
# Install fwupd (firmware update daemon)
sudo apt install fwupd

# Check for updates
fwupdmgr get-devices
fwupdmgr get-updates

# Apply updates
fwupdmgr update

# Note: Limited Mac support, mainly for Thunderbolt, some SSDs
```

**Option 3: Live Environment**
```bash
# Boot from macOS Recovery (Cmd+R at boot)
# Install updates from recovery environment
# Limited firmware updates available
```

### Updating with Dual Boot

**Simple Process**:
```bash
1. Reboot and select macOS
2. Open System Preferences → Software Update
3. Install all updates
4. Firmware updates install automatically
5. Reboot back to Linux

Time: 20-30 minutes
Frequency: Once every 1-3 months
```

### Updating with Minimal macOS

**Occasional Process**:
```bash
1. Boot to macOS (once every 3-6 months)
2. Install all pending updates
3. Run Apple Diagnostics (optional)
4. Check battery health
5. Reboot to Linux

Time: 30-45 minutes
Frequency: Every 3-6 months
```

### Pre-Wipe Checklist

**Before removing macOS completely**:

1. **Update to latest macOS version**
   ```bash
   # In macOS Terminal:
   softwareupdate --list
   softwareupdate --install --all
   ```

2. **Document current firmware versions**
   ```bash
   system_profiler SPHardwareDataType > ~/firmware_info.txt
   system_profiler SPiBridgeDataType >> ~/firmware_info.txt
   ```

3. **Create macOS USB installer**
   ```bash
   # Download from App Store, then:
   sudo /Applications/Install\ macOS\ Monterey.app/Contents/Resources/createinstallmedia --volume /Volumes/MyVolume
   ```

4. **Run Apple Diagnostics**
   ```bash
   # Shutdown, then hold D at boot
   # Verify hardware is healthy before wiping
   ```

5. **Backup SMC/NVRAM settings**
   ```bash
   nvram -p > ~/nvram_backup.txt
   ```

---

## Recommended Migration Strategy

### Phased Approach (Lowest Risk)

This strategy minimizes risk while learning Linux on your MacBook Pro.

#### Phase 1: Dual Boot Setup (Month 1)

**Goals**:
- Learn Linux on Mac hardware
- Test server applications
- Verify all hardware works
- Build confidence

**Steps**:
1. Backup macOS data
2. Resize macOS partition (keep 50-80 GB)
3. Install Ubuntu Server on free space
4. Install rEFInd bootloader
5. Configure server services
6. Test monitoring application

**Success Criteria**:
- Linux boots reliably
- All hardware works (WiFi, Bluetooth, sensors)
- Server runs 24/7 without issues
- Comfortable with Linux administration

#### Phase 2: Evaluation (Month 2-3)

**Track your usage**:
- How often do you boot macOS? (Track it!)
- Is Linux stable and reliable?
- Do you need more disk space?
- Are you comfortable with Linux tools?

**Questions to answer**:
- [ ] Haven't booted macOS in 30+ days?
- [ ] Linux runs server tasks perfectly?
- [ ] Need more storage for Docker images?
- [ ] Confident in Linux recovery procedures?
- [ ] Comfortable with Linux command line?

#### Phase 3: Decision Point (Month 3)

**If all checkboxes above are YES**:
→ **Proceed to Full Linux**

**If any are NO**:
→ **Stay with dual boot** or **move to minimal macOS**

#### Phase 4: Migration to Full Linux (Optional)

**Steps**:
1. Boot to macOS one last time
2. Update to latest macOS (firmware updates)
3. Backup any remaining macOS data
4. Create macOS USB installer (keep for emergencies)
5. Boot from Ubuntu Server USB
6. Choose "Erase disk and install Ubuntu"
7. Restore server configuration from backup
8. Test all services

**Rollback Plan**:
- Keep macOS USB installer
- Can reinstall macOS in 1 hour if needed
- Restore server config from backup

---

## Installation Instructions

### Preparation (All Approaches)

**Required Materials**:
- 16+ GB USB flash drive (Ubuntu installer)
- 16+ GB USB flash drive (macOS installer, optional)
- External backup drive
- Ethernet cable (recommended during install)

**Backup Checklist**:
- [ ] Time Machine backup (if keeping macOS)
- [ ] Copy important files to external drive
- [ ] Export browser bookmarks/passwords
- [ ] Note WiFi passwords
- [ ] Document current system info

**Download Required Files**:
1. Ubuntu Server 22.04 LTS ISO: https://ubuntu.com/download/server
2. Etcher (USB creator): https://www.balena.io/etcher/
3. rEFInd bootloader (for dual boot): https://www.rodsbooks.com/refind/

---

### Full Linux Installation

**Step 1: Create Ubuntu USB Installer**

On macOS or another computer:
```bash
# Download Ubuntu Server 22.04 LTS
# Download and install Etcher
# Use Etcher to flash ISO to USB drive
```

**Step 2: Boot from USB**

```bash
1. Insert Ubuntu USB drive
2. Restart Mac
3. Hold Option (⌥) key during boot
4. Select "EFI Boot" or "USB Drive"
5. Wait for Ubuntu installer
```

**Step 3: Install Ubuntu Server**

```bash
# Language and keyboard
- Select: English
- Keyboard layout: English (US) or your preference

# Network
- Use Ethernet if available (more reliable)
- Or configure WiFi (will need password)

# Storage configuration
- Choose: "Use an entire disk"
- Select: Your Mac's internal SSD
- Confirm: "Erase disk and install Ubuntu"

# Profile setup
- Your name: monitor (or your preference)
- Server name: macbook-server (or your preference)
- Username: monitor
- Password: [choose strong password]

# SSH Setup
- Enable: Install OpenSSH server ✓
- Import SSH keys: No (unless you have GitHub keys)

# Featured Server Snaps
- Select: docker (helpful for containers)
- Skip others for now

# Installation
- Wait 10-20 minutes
- Remove USB when prompted
- Reboot
```

**Step 4: First Boot**

```bash
# Login with username/password
monitor login: monitor
Password: ********

# Update system
sudo apt update && sudo apt upgrade -y

# Install useful tools
sudo apt install -y htop curl wget git vim net-tools

# Verify hardware
lscpu          # Check CPU
free -h        # Check RAM
df -h          # Check disk space
ip addr        # Check network
```

**Step 5: Configure for Server Use**

```bash
# Disable sleep/suspend
sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target

# Configure lid close behavior (for closed-lid operation)
sudo nano /etc/systemd/logind.conf
# Change:
# HandleLidSwitch=ignore
# HandleLidSwitchDocked=ignore

# Reload config
sudo systemctl restart systemd-logind

# Set static IP (recommended for server)
sudo nano /etc/netplan/00-installer-config.yaml
# Configure static IP (see Post-Installation section)
```

---

### Dual Boot Installation

**Step 1: Resize macOS Partition**

In macOS:
```bash
1. Open Disk Utility
2. Select main SSD (not partition)
3. Click "Partition"
4. Click "+"
5. Name: "Linux"
6. Format: "MS-DOS (FAT)" (temporary, will be reformatted)
7. Size:
   - 128 GB model: 70-80 GB for Linux
   - 256 GB model: 150-180 GB for Linux
   - 512 GB model: 350-400 GB for Linux
8. Click "Apply"
9. Wait for resize (5-15 minutes)
```

**Step 2: Install Ubuntu Server**

```bash
# Follow same steps as Full Linux, BUT:
# At storage configuration:
- Choose: "Manual"
- Select: The free space / partition you created
- Create partitions:
  * /boot/efi: 512 MB, EFI System Partition
  * swap: 8-16 GB (equal to RAM)
  * /: Remaining space, ext4
- Do NOT erase disk!
- Leave macOS partition untouched
```

**Step 3: Install rEFInd Bootloader**

After Ubuntu installation, boot to macOS:
```bash
# Download rEFInd
curl -O https://sourceforge.net/projects/refind/files/0.14.0.2/refind-bin-0.14.0.2.zip
unzip refind-bin-0.14.0.2.zip
cd refind-bin-0.14.0.2

# Disable System Integrity Protection temporarily
# Restart, hold Cmd+R, open Terminal:
csrutil disable
reboot

# Back in macOS, install rEFInd
sudo ./refind-install
# Or:
sudo bash refind-install

# Re-enable System Integrity Protection
# Restart, hold Cmd+R, open Terminal:
csrutil enable
reboot
```

**Step 4: Configure rEFInd**

```bash
# rEFInd config location (from macOS):
sudo nano /EFI/refind/refind.conf

# Set default OS:
# Find: default_selection
# Change to: "Ubuntu" or "macOS"

# Set timeout (seconds before auto-boot):
timeout 5

# Hide unwanted boot entries:
dont_scan_dirs ESP:/EFI/BOOT,EFI/Dell
```

**Step 5: Test Dual Boot**

```bash
1. Reboot
2. You should see rEFInd menu
3. Test booting to Ubuntu
4. Test booting to macOS
5. Verify both work correctly
```

---

### Minimal macOS Installation

**Step 1: Install as Dual Boot**

Follow dual boot instructions above, but:
- macOS partition: 30-40 GB only
- Linux partition: Everything else

**Step 2: Minimize macOS**

Boot to macOS and clean it:
```bash
# Remove unnecessary apps
sudo rm -rf /Applications/GarageBand.app
sudo rm -rf /Applications/iMovie.app
sudo rm -rf /Applications/Keynote.app
sudo rm -rf /Applications/Numbers.app
sudo rm -rf /Applications/Pages.app

# Clear caches
sudo rm -rf ~/Library/Caches/*
sudo rm -rf /Library/Caches/*

# Clear downloads, documents
rm -rf ~/Downloads/*
rm -rf ~/Documents/*

# Optional: Remove user files completely
# Keep only essential system
```

**Step 3: Configure Auto-Boot to Linux**

```bash
# In rEFInd config:
default_selection "Ubuntu"
timeout 3   # Short timeout, auto-boots to Linux
```

**Step 4: Document macOS Boot**

Create a note:
```bash
# To boot macOS:
# 1. Restart
# 2. Press any key during rEFInd countdown
# 3. Select "macOS"
# 4. Use for firmware updates only
# 5. Reboot to Linux when done
```

---

## Post-Installation Configuration

### Set Static IP Address

```bash
# Edit netplan config
sudo nano /etc/netplan/00-installer-config.yaml

# Example configuration:
network:
  version: 2
  ethernets:
    enp3s0:  # Your interface name (check with: ip addr)
      dhcp4: no
      addresses:
        - 192.168.1.100/24  # Your static IP
      gateway4: 192.168.1.1  # Your router IP
      nameservers:
        addresses:
          - 8.8.8.8
          - 8.8.4.4

# Apply configuration
sudo netplan apply

# Test connectivity
ping -c 4 google.com
```

### Enable SSH Access

```bash
# SSH should be installed, verify:
sudo systemctl status ssh

# If not running:
sudo systemctl enable ssh
sudo systemctl start ssh

# Find your IP:
ip addr show

# From another computer, test:
ssh monitor@192.168.1.100
```

### Configure Closed-Lid Operation

```bash
# Edit logind config
sudo nano /etc/systemd/logind.conf

# Uncomment and set:
HandleLidSwitch=ignore
HandleLidSwitchDocked=ignore

# Restart service
sudo systemctl restart systemd-logind

# Now laptop can run closed without sleeping
```

### Power Management

```bash
# Install TLP for better battery management
sudo apt install tlp tlp-rdw

# Enable TLP
sudo systemctl enable tlp
sudo systemctl start tlp

# Check TLP status
sudo tlp-stat -s

# For AC-only operation (server mode):
sudo nano /etc/tlp.conf
# Set:
# START_CHARGE_THRESH_BAT0=75
# STOP_CHARGE_THRESH_BAT0=80
# This preserves battery life when always plugged in
```

### Install Monitoring Tools

```bash
# System monitoring
sudo apt install htop iotop nethogs

# Temperature sensors
sudo apt install lm-sensors
sudo sensors-detect  # Press YES to all
sensors  # View temps

# Disk health
sudo apt install smartmontools
sudo smartctl -a /dev/sda  # Check SSD health
```

### Deploy Site Monitor Application

```bash
# Clone repository
cd /home/monitor
git clone https://github.com/yourusername/siteChecker.git
cd siteChecker

# Install Python dependencies
sudo apt install python3-pip python3-venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure credentials (see credential-management.md)
sudo mkdir -p /etc/site-monitor
sudo nano /etc/site-monitor/credentials.conf
# Add your credentials

# Set up systemd service (see credential-management.md)
sudo nano /etc/systemd/system/site-monitor.service
sudo systemctl enable site-monitor.service
sudo systemctl start site-monitor.service

# Check status
sudo systemctl status site-monitor.service
```

---

## Troubleshooting

### Boot Issues

**Problem: Black screen after Linux install**

```bash
# Solution: Add boot parameters
# At GRUB menu, press 'e'
# Add to linux line:
nomodeset

# Or for permanent fix:
sudo nano /etc/default/grub
# Add: GRUB_CMDLINE_LINUX_DEFAULT="quiet splash nomodeset"
sudo update-grub
```

**Problem: Can't boot macOS after Linux install**

```bash
# Hold Option (⌥) at boot
# Select "Macintosh HD"

# Or install rEFInd bootloader (see dual boot section)
```

**Problem: rEFInd not showing up**

```bash
# Boot to macOS
# Reinstall rEFInd
cd refind-bin-0.14.0.2
sudo ./refind-install

# Or hold Option at boot and manually select rEFInd
```

### Hardware Issues

**Problem: WiFi not working**

```bash
# Install Broadcom drivers
sudo apt install bcmwl-kernel-source

# Or use USB WiFi adapter (easier)
```

**Problem: No audio**

```bash
# Install PulseAudio
sudo apt install pulseaudio pavucontrol

# Test speakers
speaker-test -t wav -c 2
```

**Problem: Touchpad not working**

```bash
# Install libinput
sudo apt install xserver-xorg-input-libinput

# Configure touchpad
sudo nano /etc/X11/xorg.conf.d/40-libinput.conf
```

**Problem: Fans running constantly**

```bash
# Install mbpfan (MacBook Pro fan control)
sudo apt install mbpfan
sudo systemctl enable mbpfan
sudo systemctl start mbpfan

# Configure thresholds
sudo nano /etc/mbpfan.conf
```

**Problem: Battery draining fast**

```bash
# Check battery health
sudo apt install acpi
acpi -V

# Install TLP for power management
sudo apt install tlp
sudo tlp start

# Check power consumption
sudo powertop
```

### Partition Issues

**Problem: Can't resize macOS partition**

```bash
# Boot to macOS Recovery (Cmd+R)
# Open Disk Utility
# First Aid on Macintosh HD
# Then try resize again

# Or use command line:
diskutil list
diskutil resizeVolume disk0s2 100G
```

**Problem: Wrong partition selected during install**

```bash
# STOP installation immediately
# Restart and try again
# Be very careful with partition selection
# Wrong choice = data loss!
```

### Network Issues

**Problem: Can't connect to internet**

```bash
# Check network interface
ip addr show

# Check if interface is up
sudo ip link set enp3s0 up

# Try DHCP
sudo dhclient enp3s0

# Check DNS
cat /etc/resolv.conf
```

**Problem: SSH connection refused**

```bash
# Check SSH is running
sudo systemctl status ssh

# Check firewall
sudo ufw status
sudo ufw allow ssh

# Check SSH config
sudo nano /etc/ssh/sshd_config
# Ensure: PermitRootLogin no, PasswordAuthentication yes
sudo systemctl restart ssh
```

---

## Summary and Final Recommendations

### For 128 GB Models

**Recommended**: **Full Linux Installation**

**Reasoning**:
- Storage too limited for dual boot
- Server use doesn't need macOS
- Maximum space for Docker/services
- Simplest setup for 24/7 operation

**Alternative**: Skip to 256 GB+ used MacBook ($150-200)

---

### For 256 GB Models

**Recommended**: **Minimal macOS + Linux**

**Reasoning**:
- Best of both worlds
- 200+ GB for Linux (plenty)
- Firmware updates easy
- Safety net available
- Small sacrifice for peace of mind

**Alternative**: Full Linux if absolutely sure

---

### For 512 GB Models

**Recommended**: **Your choice** - plenty of space for any approach

**Options**:
- Dual boot: Keep full macOS experience
- Minimal macOS: Best balance
- Full Linux: Maximum simplicity

All work well with abundant storage.

---

### Migration Path Recommendation

**Best Approach for Most Users**:

```
1. Start: Dual boot (learn & test)
   ↓
2. Evaluate: After 1-2 months
   ↓
3. Decide:
   - Never use macOS? → Full Linux
   - Occasional use? → Keep dual boot
   - Just firmware? → Minimal macOS
```

This minimizes risk while maximizing learning and confidence.

---

## Additional Resources

### Official Documentation
- Ubuntu Server Guide: https://ubuntu.com/server/docs
- rEFInd Documentation: https://www.rodsbooks.com/refind/
- Arch Linux MacBook Wiki: https://wiki.archlinux.org/title/MacBook

### Community Resources
- /r/linux4noobs (Reddit)
- /r/linuxquestions (Reddit)
- Ubuntu Forums: https://ubuntuforums.org/
- Ask Ubuntu: https://askubuntu.com/

### Useful Tools
- Etcher (USB creator): https://www.balena.io/etcher/
- GParted (partition manager): https://gparted.org/
- Clonezilla (backup/restore): https://clonezilla.org/

### Monitoring Your Server
- Netdata: Real-time monitoring dashboard
- Grafana + Prometheus: Advanced metrics
- Uptime Kuma: Beautiful uptime monitoring UI

---

## Conclusion

Converting your 2014 MacBook Pro to a Linux server is an excellent way to repurpose old hardware. The key decisions are:

1. **Storage constraints** (128 GB → full Linux, 256+ GB → more options)
2. **Experience level** (beginner → dual boot, experienced → full Linux)
3. **Firmware updates** (convenient → keep macOS, manual → full Linux)

**Most flexible approach**: Start with dual boot, evaluate after 1-2 months, then decide. This minimizes risk while building confidence.

**Most powerful setup**: Minimal macOS (35 GB) + Linux (rest) gives you 90% of the benefits of full Linux with firmware update convenience.

Choose based on your priorities, and you can always change later. The beauty of Linux is flexibility!
