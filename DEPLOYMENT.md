# Deployment Guide

Complete guide for deploying the Multi-Retailer Store Scraper to a remote development server on your local network.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Deployment Methods](#deployment-methods)
- [Method 1: Docker Deployment (Recommended)](#method-1-docker-deployment-recommended)
- [Method 2: Native Python Deployment](#method-2-native-python-deployment)
- [Method 3: Systemd Service Deployment](#method-3-systemd-service-deployment)
- [Post-Deployment Configuration](#post-deployment-configuration)
- [Running Your First Scrape](#running-your-first-scrape)
- [Monitoring and Maintenance](#monitoring-and-maintenance)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### On Your Workstation (Local Machine)

- Git installed
- SSH client (built-in on macOS/Linux)
- SSH key configured for passwordless access to dev server (optional but recommended)
- Network connectivity to dev server

### On Your Dev Server (Remote Machine)

**For Docker Deployment:**
- Ubuntu 20.04+ / Debian 11+ / RHEL 8+ or compatible Linux distribution
- Docker Engine 20.10+
- Docker Compose 2.0+
- Minimum 2GB RAM, 20GB disk space
- SSH server running
- `sudo` or root access

**For Native Deployment:**
- Python 3.8-3.11 installed
- pip and venv packages
- Git installed
- Minimum 2GB RAM, 20GB disk space
- SSH server running
- `sudo` or root access

---

## Deployment Methods

Choose the method that best fits your infrastructure:

| Method | Complexity | Isolation | Updates | Best For |
|--------|-----------|-----------|---------|----------|
| Docker | Low | High | Easy | Production, consistency |
| Native Python | Medium | Medium | Manual | Development, debugging |
| Systemd Service | Medium | Low | Manual | Long-running background tasks |

---

## Method 1: Docker Deployment (Recommended)

Docker provides the easiest deployment with built-in isolation, health checks, and automatic restarts.

### Step 1: Prepare Your Workstation

```bash
# Navigate to the project directory
cd /Users/vmud/Documents/dev/projects/retail-store-scraper

# Ensure you're on the correct branch
git status
git pull origin main  # Or your deployment branch

# Optional: Create environment file for proxy credentials
cp .env.example .env
# Edit .env with your Oxylabs credentials (if using proxies)
```

### Step 2: Transfer Files to Dev Server

**Option A: Using Git (Recommended)**

```bash
# SSH into your dev server
ssh user@dev-server-ip

# Clone the repository
cd /opt  # Or your preferred installation directory
sudo git clone https://github.com/yourusername/retail-store-scraper.git
cd retail-store-scraper

# If using a private repository, set up SSH key or use HTTPS with credentials
```

**Option B: Using rsync (For Local Network)**

```bash
# From your workstation, sync files to dev server
# Replace 'user' and 'dev-server-ip' with your actual values

rsync -avz --exclude 'venv' \
           --exclude 'data' \
           --exclude 'logs' \
           --exclude '.git' \
           --exclude 'node_modules' \
           --exclude '__pycache__' \
           /Users/vmud/Documents/dev/projects/retail-store-scraper/ \
           user@dev-server-ip:/opt/retail-store-scraper/

# Example for local network:
# rsync -avz --exclude 'venv' ... user@192.168.1.100:/opt/retail-store-scraper/
```

**Option C: Using scp (Simple File Copy)**

```bash
# Create a tarball and copy it
cd /Users/vmud/Documents/dev/projects/retail-store-scraper
tar --exclude='venv' \
    --exclude='data' \
    --exclude='logs' \
    --exclude='.git' \
    --exclude='node_modules' \
    --exclude='__pycache__' \
    -czf retail-scraper.tar.gz .

scp retail-scraper.tar.gz user@dev-server-ip:/tmp/

# SSH into server and extract
ssh user@dev-server-ip
sudo mkdir -p /opt/retail-store-scraper
sudo tar -xzf /tmp/retail-scraper.tar.gz -C /opt/retail-store-scraper/
sudo chown -R $USER:$USER /opt/retail-store-scraper
```

### Step 3: Install Docker on Dev Server (If Not Installed)

```bash
# SSH into your dev server
ssh user@dev-server-ip

# Install Docker (Ubuntu/Debian)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group (optional, to run without sudo)
sudo usermod -aG docker $USER
newgrp docker

# Install Docker Compose
sudo apt-get update
sudo apt-get install docker-compose-plugin

# Verify installation
docker --version
docker compose version
```

### Step 4: Configure Environment Variables

```bash
# SSH into dev server
ssh user@dev-server-ip
cd /opt/retail-store-scraper

# Create .env file (copy from example)
cp .env.example .env

# Edit with your credentials
nano .env  # or vim, vi, etc.
```

**Example `.env` configuration:**

```bash
# Oxylabs Proxy Configuration (Optional - leave blank for direct mode)
OXYLABS_RESIDENTIAL_USERNAME=your_username_here
OXYLABS_RESIDENTIAL_PASSWORD=your_password_here

# Dashboard API Key (Optional - for authentication)
DASHBOARD_API_KEY=your_secret_key_here

# Logging
LOG_LEVEL=INFO
```

### Step 5: Build and Start Docker Containers

```bash
# Build Docker images
docker compose build

# Start services (dashboard + scraper)
docker compose up -d

# Verify containers are running
docker compose ps

# Check logs
docker compose logs -f dashboard
docker compose logs -f scraper
```

### Step 6: Access the Dashboard

```bash
# From your workstation, open browser to:
http://dev-server-ip:5001

# Example: http://192.168.1.100:5001

# Or use SSH tunnel for secure access:
ssh -L 5001:localhost:5001 user@dev-server-ip
# Then access: http://localhost:5001
```

### Step 7: Verify Deployment

```bash
# SSH into dev server
ssh user@dev-server-ip

# Check container health
docker compose ps
docker inspect retail-scraper-dashboard --format='{{.State.Health.Status}}'

# Check scraper status
docker compose exec scraper python run.py --status

# View live logs
docker compose logs -f scraper
```

---

## Method 2: Native Python Deployment

For development environments or when Docker is not available.

### Step 1: Transfer Files to Dev Server

Use the same methods as Docker deployment (Git, rsync, or scp).

### Step 2: Set Up Python Environment

```bash
# SSH into dev server
ssh user@dev-server-ip
cd /opt/retail-store-scraper

# Check Python version
python3 --version  # Should be 3.8-3.11

# Create virtual environment
python3.11 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Configure Environment

```bash
# Create .env file
cp .env.example .env
nano .env  # Edit with your settings
```

### Step 4: Test Installation

```bash
# Activate venv if not already active
source venv/bin/activate

# Run a quick test
python run.py --retailer verizon --test

# Check status
python run.py --status
```

### Step 5: Set Up as Background Service (Optional)

Create a simple screen session for long-running tasks:

```bash
# Install screen if not available
sudo apt-get install screen

# Start a named screen session
screen -S scraper

# Inside screen, run the scraper
cd /opt/retail-store-scraper
source venv/bin/activate
python run.py --all --resume

# Detach from screen: Ctrl+A, then D

# Reattach later:
screen -r scraper

# List screens:
screen -ls
```

Or use `nohup` for simple background execution:

```bash
# Run in background with nohup
nohup python run.py --all --resume > scraper.log 2>&1 &

# Check if running
ps aux | grep run.py

# View logs
tail -f scraper.log
```

---

## Method 3: Systemd Service Deployment

For production-grade deployment with automatic restart and system integration.

### Step 1: Transfer Files and Set Up Python

Follow steps 1-3 from Native Python Deployment.

### Step 2: Run Installation Script

```bash
# SSH into dev server
ssh user@dev-server-ip
cd /opt/retail-store-scraper

# Run installation script as root
sudo ./deploy/install.sh
```

The script will:
- Create a `scraper` system user
- Install application to `/opt/retail-store-scraper`
- Set up Python virtual environment
- Install dependencies
- Configure systemd service
- Set proper permissions

### Step 3: Configure Environment

```bash
# Edit environment variables for systemd service
sudo nano /etc/systemd/system/retail-scraper.service

# Add environment variables in [Service] section:
# Environment=OXYLABS_USERNAME=your_username
# Environment=OXYLABS_PASSWORD=your_password
# Environment=LOG_LEVEL=INFO

# Reload systemd after changes
sudo systemctl daemon-reload
```

### Step 4: Manage Service

```bash
# Start the service
sudo systemctl start retail-scraper

# Enable auto-start on boot
sudo systemctl enable retail-scraper

# Check status
sudo systemctl status retail-scraper

# View logs (live)
sudo journalctl -u retail-scraper -f

# View logs (last 100 lines)
sudo journalctl -u retail-scraper -n 100

# Stop the service
sudo systemctl stop retail-scraper

# Restart the service
sudo systemctl restart retail-scraper
```

### Step 5: Start Dashboard Separately

```bash
# The systemd service only runs the scraper
# Start dashboard manually or create a separate service

# Option A: Run dashboard in screen
screen -S dashboard
cd /opt/retail-store-scraper
sudo -u scraper ./venv/bin/python dashboard/app.py

# Option B: Create dashboard systemd service
sudo nano /etc/systemd/system/retail-scraper-dashboard.service
```

**Dashboard Service File (`retail-scraper-dashboard.service`):**

```ini
[Unit]
Description=Multi-Retailer Store Scraper Dashboard
After=network.target

[Service]
Type=simple
User=scraper
Group=scraper
WorkingDirectory=/opt/retail-store-scraper
ExecStart=/opt/retail-store-scraper/venv/bin/python dashboard/app.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1
Environment=FLASK_ENV=production

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start dashboard service
sudo systemctl daemon-reload
sudo systemctl enable retail-scraper-dashboard
sudo systemctl start retail-scraper-dashboard
sudo systemctl status retail-scraper-dashboard
```

---

## Post-Deployment Configuration

### Configure Retailer Settings

```bash
# Edit retailer configuration
nano config/retailers.yaml

# Key settings to review:
# - enabled: true/false for each retailer
# - min_delay / max_delay: Request throttling
# - proxy.mode: direct, residential, web_scraper_api
```

### Set Up Proxy Credentials (Optional)

If using Oxylabs proxies:

```bash
# Edit .env file
nano .env

# Add credentials:
OXYLABS_RESIDENTIAL_USERNAME=your_username
OXYLABS_RESIDENTIAL_PASSWORD=your_password

# Validate credentials before first run
python run.py --all --proxy residential --validate-proxy
```

### Configure Firewall (If Needed)

```bash
# Allow dashboard port (5001) through firewall
sudo ufw allow 5001/tcp

# Or restrict to local network only (recommended)
sudo ufw allow from 192.168.1.0/24 to any port 5001
```

### Set Up Log Rotation (Recommended)

```bash
# Create logrotate configuration
sudo nano /etc/logrotate.d/retail-scraper
```

**Logrotate Config:**

```
/opt/retail-store-scraper/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    missingok
    copytruncate
}
```

---

## Running Your First Scrape

### Quick Test Run (10 Stores Per Retailer)

```bash
# Docker deployment
docker compose exec scraper python run.py --all --test

# Native deployment
cd /opt/retail-store-scraper
source venv/bin/activate
python run.py --all --test
```

### Full Production Run

```bash
# Docker deployment
docker compose exec scraper python run.py --all --resume

# Native deployment
python run.py --all --resume

# With proxies (faster, recommended for production)
python run.py --all --resume --proxy residential
```

### Monitor Progress

**Via Dashboard:**
- Open browser: `http://dev-server-ip:5001`
- Real-time updates every 5 seconds
- View progress bars, logs, and change reports

**Via CLI:**

```bash
# Check current status
docker compose exec scraper python run.py --status

# Or native:
python run.py --status

# View logs
docker compose logs -f scraper
# Or:
tail -f logs/scraper.log
```

### Expected Runtime

| Mode | Retailers | Stores | Runtime |
|------|-----------|--------|---------|
| Test | All (6) | 60 total | ~5-10 minutes |
| Full (Direct) | All (6) | ~15,000+ | 8-12 hours |
| Full (Proxy) | All (6) | ~15,000+ | 1-2 hours |
| Incremental | All (6) | Changed only | 15-60 minutes |

---

## Monitoring and Maintenance

### Daily Operations

```bash
# Check scraper status
docker compose exec scraper python run.py --status

# View recent logs
docker compose logs --tail=100 scraper

# Check disk usage
du -sh /opt/retail-store-scraper/data/*
```

### Weekly Maintenance

```bash
# Update code from repository
cd /opt/retail-store-scraper
git pull origin main
docker compose build
docker compose up -d

# Clean up old run history (keeps last 20 runs per retailer)
# This is automatic, but you can verify:
ls -lh data/*/runs/
```

### Backup Data

```bash
# Create backup of data directory
tar -czf retail-scraper-backup-$(date +%Y%m%d).tar.gz \
    /opt/retail-store-scraper/data/

# Transfer to workstation
scp user@dev-server-ip:/opt/retail-scraper-backup-*.tar.gz \
    /Users/vmud/backups/

# Or use rsync for incremental backups
rsync -avz user@dev-server-ip:/opt/retail-store-scraper/data/ \
    /Users/vmud/backups/retail-scraper-data/
```

### Health Checks

```bash
# Docker health check
docker inspect retail-scraper-dashboard \
    --format='{{.State.Health.Status}}'

# Manual API health check
curl http://localhost:5001/api/status

# Check for stale processes (should be none)
docker compose exec scraper ps aux | grep python
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check container logs
docker compose logs scraper
docker compose logs dashboard

# Rebuild containers
docker compose down
docker compose build --no-cache
docker compose up -d

# Check for port conflicts
sudo netstat -tlnp | grep 5001
```

### Permission Errors

```bash
# Fix ownership (Docker deployment)
sudo chown -R $(id -u):$(id -g) data/ logs/

# Fix ownership (Systemd deployment)
sudo chown -R scraper:scraper /opt/retail-store-scraper/data
sudo chown -R scraper:scraper /opt/retail-store-scraper/logs
```

### Network/Connection Issues

```bash
# Test connectivity from container
docker compose exec scraper curl -I https://www.verizon.com

# Test DNS resolution
docker compose exec scraper nslookup www.target.com

# Check proxy credentials
docker compose exec scraper python run.py --all --proxy residential --validate-proxy
```

### Scraper Hanging/Slow

```bash
# Check current status
docker compose exec scraper python run.py --status

# View request counts and rate limiting
docker compose logs scraper | grep "Pause after"

# If hanging, check for stale processes
docker compose exec scraper ps aux

# Restart if needed
docker compose restart scraper
```

### Dashboard Not Accessible

```bash
# Check if dashboard is running
docker compose ps dashboard
docker compose logs dashboard

# Test locally on server
curl http://localhost:5001/api/status

# Check firewall
sudo ufw status
sudo ufw allow 5001/tcp

# Use SSH tunnel as workaround
ssh -L 5001:localhost:5001 user@dev-server-ip
# Then access: http://localhost:5001
```

### Out of Memory

```bash
# Check memory usage
docker stats

# Increase Docker memory limit (if using Docker Desktop)
# Or add memory limits to docker-compose.yml:
# services:
#   scraper:
#     mem_limit: 2g

# Run retailers individually instead of --all
docker compose exec scraper python run.py --retailer verizon
```

### Disk Space Issues

```bash
# Check disk usage
df -h
du -sh /opt/retail-store-scraper/data/*

# Clean up old checkpoints and history
find data/*/checkpoints/ -mtime +30 -delete
find data/*/history/ -mtime +90 -delete

# Remove old Docker images
docker system prune -a
```

---

## Updating the Deployment

### Update Code

```bash
# SSH into dev server
ssh user@dev-server-ip
cd /opt/retail-store-scraper

# Stop services
docker compose down
# Or systemd:
sudo systemctl stop retail-scraper retail-scraper-dashboard

# Pull latest code
git pull origin main

# Rebuild (Docker)
docker compose build
docker compose up -d

# Or reinstall dependencies (Native)
source venv/bin/activate
pip install -r requirements.txt

# Restart services (Native/Systemd)
sudo systemctl start retail-scraper retail-scraper-dashboard
```

### Rollback to Previous Version

```bash
# Using Git
cd /opt/retail-store-scraper
git log --oneline  # Find commit hash
git checkout <commit-hash>
docker compose build
docker compose up -d

# Using backup
tar -xzf retail-scraper-backup-YYYYMMDD.tar.gz
```

---

## Security Best Practices

1. **Use SSH keys instead of passwords:**
   ```bash
   ssh-copy-id user@dev-server-ip
   ```

2. **Restrict dashboard access to local network:**
   ```bash
   sudo ufw allow from 192.168.1.0/24 to any port 5001
   ```

3. **Set dashboard API key:**
   ```bash
   # In .env file:
   DASHBOARD_API_KEY=$(openssl rand -hex 32)
   ```

4. **Keep secrets out of git:**
   ```bash
   # Never commit .env file
   echo ".env" >> .gitignore
   ```

5. **Run with non-root user:**
   - Docker deployment runs as non-root by default (user ID 1000)
   - Systemd deployment uses dedicated `scraper` user

6. **Regular updates:**
   ```bash
   # Keep system packages updated
   sudo apt-get update && sudo apt-get upgrade
   
   # Keep Python packages updated
   pip install --upgrade -r requirements.txt
   ```

---

## Next Steps

1. ✅ Deploy to dev server (Docker recommended)
2. ✅ Run first test scrape (`--all --test`)
3. ✅ Verify data output in `data/*/output/`
4. ✅ Access dashboard and explore UI
5. ✅ Run full production scrape (`--all --resume`)
6. ✅ Set up scheduled runs (cron or systemd timer)
7. ✅ Configure monitoring/alerting (optional)
8. ✅ Set up automated backups (optional)

**Questions or issues?** Check the main [README.md](README.md) or [CLAUDE.md](CLAUDE.md) for additional documentation.
