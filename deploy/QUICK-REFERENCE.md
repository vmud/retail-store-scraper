# Deployment Quick Reference

## File Transfer to Dev Server

### Using rsync (Recommended for Local Network)
```bash
# From workstation - use helper script
./deploy/rsync-deploy.sh user@dev-server-ip

# Or manual rsync
rsync -avz --exclude 'venv' --exclude 'data' --exclude '.git' \
    /Users/vmud/Documents/dev/projects/retail-store-scraper/ \
    user@192.168.1.100:/opt/retail-store-scraper/
```

### Using Git
```bash
# SSH into dev server
ssh user@dev-server-ip
cd /opt
sudo git clone https://github.com/yourusername/retail-store-scraper.git
cd retail-store-scraper
```

### Using scp (Simple Transfer)
```bash
# Create tarball
tar czf retail-scraper.tar.gz --exclude='venv' --exclude='data' .
scp retail-scraper.tar.gz user@dev-server-ip:/tmp/

# SSH and extract
ssh user@dev-server-ip
sudo mkdir -p /opt/retail-store-scraper
sudo tar -xzf /tmp/retail-scraper.tar.gz -C /opt/retail-store-scraper/
```

---

## Docker Deployment Commands

### Initial Setup
```bash
# On dev server
cd /opt/retail-store-scraper
cp .env.example .env
nano .env  # Add credentials
docker compose build
docker compose up -d
```

### Daily Operations
```bash
# Check status
docker compose ps
docker compose logs -f scraper
docker compose logs -f dashboard

# Run commands in container
docker compose exec scraper python run.py --status
docker compose exec scraper python run.py --all --test

# Restart services
docker compose restart scraper
docker compose restart dashboard

# Stop/start all
docker compose down
docker compose up -d

# View resource usage
docker stats
```

### Updates
```bash
# Pull latest code
cd /opt/retail-store-scraper
git pull origin main

# Rebuild and restart
docker compose down
docker compose build
docker compose up -d
```

---

## Native Python Deployment Commands

### Initial Setup
```bash
# On dev server
cd /opt/retail-store-scraper
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
```

### Daily Operations
```bash
# Activate environment
source venv/bin/activate

# Run scrapers
python run.py --all --test
python run.py --all --resume
python run.py --retailer verizon

# Check status
python run.py --status

# Start dashboard
python dashboard/app.py  # Port 5001

# Run in background with screen
screen -S scraper
python run.py --all --resume
# Press Ctrl+A, then D to detach

# Reattach to screen
screen -r scraper
```

### Updates
```bash
cd /opt/retail-store-scraper
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
```

---

## Systemd Service Commands

### Initial Setup
```bash
# Run installer
sudo ./deploy/install.sh

# Edit service environment
sudo nano /etc/systemd/system/retail-scraper.service
sudo systemctl daemon-reload
```

### Daily Operations
```bash
# Start/stop/restart
sudo systemctl start retail-scraper
sudo systemctl stop retail-scraper
sudo systemctl restart retail-scraper

# Enable/disable auto-start
sudo systemctl enable retail-scraper
sudo systemctl disable retail-scraper

# Check status
sudo systemctl status retail-scraper

# View logs
sudo journalctl -u retail-scraper -f
sudo journalctl -u retail-scraper -n 100
sudo journalctl -u retail-scraper --since "1 hour ago"

# Manual run
sudo -u scraper /opt/retail-store-scraper/venv/bin/python \
    /opt/retail-store-scraper/run.py --status
```

---

## Monitoring Commands

### Check Scraper Status
```bash
# Docker
docker compose exec scraper python run.py --status

# Native/Systemd
python run.py --status  # or with full path
```

### View Logs
```bash
# Docker
docker compose logs -f scraper
docker compose logs -f dashboard --tail=100

# Native
tail -f logs/scraper.log
tail -100 logs/scraper.log

# Systemd
sudo journalctl -u retail-scraper -f
```

### Check Data Output
```bash
# List output files
ls -lh data/*/output/

# View store counts
for retailer in verizon att target tmobile walmart; do
    count=$(jq '. | length' data/$retailer/output/stores_latest.json 2>/dev/null || echo "0")
    echo "$retailer: $count stores"
done

# Check last modified times
find data/*/output/ -name "stores_latest.json" -ls
```

### System Resources
```bash
# Docker containers
docker stats

# Process list
ps aux | grep python

# Disk usage
df -h
du -sh /opt/retail-store-scraper/data/*

# Memory usage
free -h
```

---

## Dashboard Access

### Direct Access
```bash
# Open browser to:
http://dev-server-ip:5001
# Example: http://192.168.1.100:5001
```

### SSH Tunnel (Secure)
```bash
# From workstation
ssh -L 5001:localhost:5001 user@dev-server-ip

# Then access:
http://localhost:5001
```

### Check Dashboard Health
```bash
# Docker
curl http://localhost:5001/api/status

# From workstation
curl http://dev-server-ip:5001/api/status
```

---

## Common Troubleshooting Commands

### Permission Issues
```bash
# Docker
sudo chown -R $(id -u):$(id -g) data/ logs/

# Systemd
sudo chown -R scraper:scraper /opt/retail-store-scraper/data
sudo chown -R scraper:scraper /opt/retail-store-scraper/logs
```

### Port Conflicts
```bash
# Check what's using port 5001
sudo netstat -tlnp | grep 5001
sudo lsof -i :5001

# Kill process using port
sudo kill -9 <PID>
```

### Container Issues
```bash
# Rebuild from scratch
docker compose down
docker compose build --no-cache
docker compose up -d

# Remove all containers and volumes
docker compose down -v
docker system prune -a
```

### Network Issues
```bash
# Test connectivity from container
docker compose exec scraper curl -I https://www.verizon.com
docker compose exec scraper nslookup www.target.com

# Test from host
curl -I https://www.verizon.com
```

### Clean Restart
```bash
# Docker
docker compose down
docker compose build
docker compose up -d

# Systemd
sudo systemctl stop retail-scraper
sudo systemctl start retail-scraper

# Native (kill all Python processes)
pkill -f "python run.py"
```

---

## Backup and Restore

### Backup Data
```bash
# Create timestamped backup
tar -czf retail-scraper-backup-$(date +%Y%m%d-%H%M%S).tar.gz \
    data/ logs/ config/retailers.yaml .env

# Transfer to workstation
scp retail-scraper-backup-*.tar.gz \
    user@workstation-ip:/Users/vmud/backups/

# Or use rsync for incremental backups
rsync -avz data/ user@workstation-ip:/Users/vmud/backups/retail-scraper-data/
```

### Restore from Backup
```bash
# Extract backup
tar -xzf retail-scraper-backup-20260120-120000.tar.gz

# Or restore specific directories
tar -xzf backup.tar.gz data/ logs/
```

---

## Environment Variables

### Set Proxy Credentials
```bash
# Edit .env file
nano .env

# Add:
OXYLABS_RESIDENTIAL_USERNAME=your_username
OXYLABS_RESIDENTIAL_PASSWORD=your_password

# For Docker, restart containers
docker compose down && docker compose up -d

# For systemd, edit service file
sudo nano /etc/systemd/system/retail-scraper.service
sudo systemctl daemon-reload
sudo systemctl restart retail-scraper
```

### Validate Proxy Setup
```bash
# Docker
docker compose exec scraper python run.py --all --proxy residential --validate-proxy

# Native
python run.py --all --proxy residential --validate-proxy
```

---

## Performance Testing

### Quick Test (60 stores total)
```bash
# Docker
time docker compose exec scraper python run.py --all --test

# Native
time python run.py --all --test

# Expected: 5-10 minutes direct, 1-2 minutes with proxy
```

### Benchmark Single Retailer
```bash
# Test Verizon (smallest dataset)
time python run.py --retailer verizon --limit 100

# Test Target (API-based, fastest)
time python run.py --retailer target --limit 100
```

---

## Scheduled Runs (Cron)

### Daily at 2 AM
```bash
# Edit crontab
crontab -e

# Add:
0 2 * * * cd /opt/retail-store-scraper && docker compose exec scraper python run.py --all --resume >> /var/log/scraper-cron.log 2>&1
```

### Weekly on Sunday
```bash
0 2 * * 0 cd /opt/retail-store-scraper && docker compose exec scraper python run.py --all --resume
```

---

## Firewall Configuration

### Allow Dashboard Port (Local Network Only)
```bash
# UFW (Ubuntu/Debian)
sudo ufw allow from 192.168.1.0/24 to any port 5001
sudo ufw status

# firewalld (RHEL/CentOS)
sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="192.168.1.0/24" port protocol="tcp" port="5001" accept'
sudo firewall-cmd --reload
```

### Allow from Specific IP
```bash
sudo ufw allow from 192.168.1.50 to any port 5001
```

---

## Quick Links

- **Full Documentation**: [DEPLOYMENT.md](../DEPLOYMENT.md)
- **Deployment Checklist**: [deploy-checklist.md](deploy-checklist.md)
- **Main README**: [README.md](../README.md)
- **Agent Guide**: [AGENTS.md](../AGENTS.md)
