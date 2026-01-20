# Deployment Ready Summary

## ✅ Repository Prepared for Deployment

Your retail store scraper is now ready to deploy to your remote dev server on the local network.

## 📋 What Was Prepared

### New Documentation
1. **[DEPLOYMENT.md](DEPLOYMENT.md)** - Complete deployment guide
   - 3 deployment methods (Docker, Native Python, Systemd)
   - Step-by-step instructions for each method
   - Network setup for local dev server
   - Troubleshooting section
   - Security best practices

2. **[deploy/deploy-checklist.md](deploy/deploy-checklist.md)** - Interactive checklist
   - Pre-deployment checks
   - Method-specific steps
   - Post-deployment validation
   - Print and check off as you go

3. **[deploy/QUICK-REFERENCE.md](deploy/QUICK-REFERENCE.md)** - Command reference
   - Common operations for all deployment methods
   - Monitoring commands
   - Backup procedures
   - Firewall configuration

### New Scripts
1. **[deploy/validate.sh](deploy/validate.sh)** - Pre-deployment validator
   ```bash
   ./deploy/validate.sh
   ```
   - Checks Python syntax
   - Validates configuration files
   - Verifies required files exist
   - Detects sensitive files

2. **[deploy/rsync-deploy.sh](deploy/rsync-deploy.sh)** - File transfer helper
   ```bash
   ./deploy/rsync-deploy.sh user@192.168.1.100
   ```
   - Transfers files to dev server
   - Excludes build artifacts and data
   - Tests connection first
   - Shows next steps

### Updated Documentation
1. **[README.md](README.md)** - Enhanced with:
   - Latest features (proxy integration, streaming JSON, rate limiting)
   - Advanced usage examples
   - Performance metrics
   - Contributing guidelines

2. **[deploy/install.sh](deploy/install.sh)** - Updated dashboard port to 5001

## 🚀 Deployment Quick Start

### Step 1: Validate (Optional but Recommended)
```bash
cd /Users/vmud/Documents/dev/projects/retail-store-scraper
./deploy/validate.sh
```

**Expected Output:**
```
✓ All checks passed! Repository is ready for deployment.
```

### Step 2: Transfer Files to Dev Server

**Method A: Using Helper Script (Recommended)**
```bash
./deploy/rsync-deploy.sh user@dev-server-ip
```

**Method B: Using Git**
```bash
# On dev server
ssh user@dev-server-ip
cd /opt
sudo git clone https://github.com/yourusername/retail-store-scraper.git
```

**Replace:** `user@dev-server-ip` with your actual server credentials
- Example: `ubuntu@192.168.1.100`
- Example: `admin@192.168.1.50`

### Step 3: Choose Deployment Method

#### Option 1: Docker (Recommended)
```bash
# SSH into dev server
ssh user@dev-server-ip
cd /opt/retail-store-scraper

# Configure
cp .env.example .env
nano .env  # Add your Oxylabs credentials (optional)

# Deploy
docker compose build
docker compose up -d

# Verify
docker compose ps
docker compose logs -f dashboard
```

**Access Dashboard:** `http://dev-server-ip:5001`

#### Option 2: Native Python
```bash
# SSH into dev server
ssh user@dev-server-ip
cd /opt/retail-store-scraper

# Set up
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Test
python run.py --all --test

# Run
python run.py --all --resume
```

#### Option 3: Systemd Service
```bash
# SSH into dev server
ssh user@dev-server-ip
cd /opt/retail-store-scraper

# Install
sudo ./deploy/install.sh

# Start
sudo systemctl start retail-scraper
sudo systemctl enable retail-scraper

# Monitor
sudo journalctl -u retail-scraper -f
```

### Step 4: Run First Test
```bash
# Docker
docker compose exec scraper python run.py --all --test

# Native/Systemd
python run.py --all --test
```

**Expected:** ~5-10 minutes to scrape 60 stores (10 per retailer)

### Step 5: Verify Deployment
- [ ] Dashboard accessible at `http://dev-server-ip:5001`
- [ ] Data files created: `ls -lh data/*/output/`
- [ ] Logs show no errors: `tail -100 logs/scraper.log`
- [ ] Test run completed successfully

### Step 6: Run Full Production Scrape
```bash
# Docker
docker compose exec scraper python run.py --all --resume

# Native
python run.py --all --resume --proxy residential  # If using proxies

# Systemd (already running)
sudo systemctl status retail-scraper
```

**Expected Runtime:**
- Direct mode: 8-12 hours
- With Oxylabs proxies: 1-2 hours

## 📊 What to Expect

### Test Run (60 stores)
```
✓ Verizon: 10 stores in ~1-2 min
✓ AT&T: 10 stores in ~1-2 min  
✓ Target: 10 stores in ~30 sec
✓ T-Mobile: 10 stores in ~1-2 min
✓ Walmart: 10 stores in ~1-2 min
✓ Best Buy: Disabled (WIP)

Total: 50-60 stores in 5-10 minutes
```

### Full Production Run
```
Verizon: ~1,800 stores
AT&T: ~5,000 stores
Target: ~1,900 stores
T-Mobile: ~7,500 stores
Walmart: ~4,500 stores

Total: ~20,000+ stores
Runtime: 8-12 hours (direct) or 1-2 hours (with proxies)
```

### Output Files (per retailer)
```
data/verizon/
├── output/
│   ├── stores_latest.json    # Current run data
│   ├── stores_latest.csv     # CSV export
│   ├── stores_previous.json  # Previous run (for change detection)
│   └── stores_latest.xlsx    # Excel export (if requested)
├── checkpoints/              # Resume state
└── history/                  # Change reports
```

## 🔧 Common Operations

### Check Status
```bash
# Docker
docker compose exec scraper python run.py --status

# Native/Systemd
python run.py --status
```

### View Logs
```bash
# Docker
docker compose logs -f scraper
docker compose logs -f dashboard

# Systemd
sudo journalctl -u retail-scraper -f

# Native
tail -f logs/scraper.log
```

### Access Dashboard
**Direct:** `http://dev-server-ip:5001`

**SSH Tunnel (secure):**
```bash
# From workstation
ssh -L 5001:localhost:5001 user@dev-server-ip

# Then access: http://localhost:5001
```

### Update Code
```bash
# Transfer new files from workstation
./deploy/rsync-deploy.sh user@dev-server-ip

# On dev server, restart services
docker compose down && docker compose build && docker compose up -d
# Or:
sudo systemctl restart retail-scraper
```

### Backup Data
```bash
# On dev server
tar -czf retail-scraper-backup-$(date +%Y%m%d).tar.gz \
    data/ logs/ config/retailers.yaml .env

# Transfer to workstation
scp retail-scraper-backup-*.tar.gz \
    user@workstation:/Users/vmud/backups/
```

## 📚 Documentation Reference

### For Deployment
1. **[DEPLOYMENT.md](DEPLOYMENT.md)** - Complete guide (read first)
2. **[deploy/deploy-checklist.md](deploy/deploy-checklist.md)** - Step-by-step checklist
3. **[deploy/QUICK-REFERENCE.md](deploy/QUICK-REFERENCE.md)** - Command cheat sheet
4. **[deploy/README.md](deploy/README.md)** - Deployment files overview

### For Development
1. **[README.md](README.md)** - Project overview and usage
2. **[CLAUDE.md](CLAUDE.md)** - AI assistant context
3. **[AGENTS.md](AGENTS.md)** - Developer guidelines

### For Configuration
1. **[config/retailers.yaml](config/retailers.yaml)** - Retailer settings
2. **[.env.example](.env.example)** - Environment template

## 🔐 Security Checklist

Before deploying:
- [ ] `.env` file created with credentials (not committed to git)
- [ ] SSH key configured for passwordless access (recommended)
- [ ] Firewall configured to restrict dashboard to local network
- [ ] Dashboard API key set (optional but recommended)
- [ ] Non-root user used for all operations

## ⚠️ Important Notes

1. **Dashboard Port Changed to 5001**
   - Updated from 5000 to avoid conflicts
   - Update any firewall rules or bookmarks

2. **Proxy Credentials Optional**
   - Leave blank in `.env` for direct mode (slower but free)
   - Add Oxylabs credentials for 6-8x speedup

3. **First Run Takes Time**
   - Test run: 5-10 minutes
   - Full run: 8-12 hours (direct) or 1-2 hours (proxy)
   - Be patient, progress shown in dashboard

4. **Data Persists**
   - Docker volumes mount to `./data` and `./logs`
   - Native/Systemd writes directly to filesystem
   - Use `--resume` to continue interrupted runs

5. **Incremental Mode Available**
   - After first run, use `--incremental`
   - Only processes changed stores
   - Much faster: 15-60 minutes

## 🎯 Success Criteria

Deployment is successful when:
- ✅ Dashboard loads at `http://dev-server-ip:5001`
- ✅ Test run completes without errors
- ✅ Data files appear in `data/*/output/`
- ✅ Logs show progress without critical errors
- ✅ Services restart automatically (Docker/Systemd)

## 🆘 Troubleshooting

### Issue: Can't access dashboard
**Solution:**
```bash
# Check if running
docker compose ps  # or: sudo systemctl status retail-scraper-dashboard

# Check logs
docker compose logs dashboard

# Test locally on server
curl http://localhost:5001/api/status

# Use SSH tunnel
ssh -L 5001:localhost:5001 user@dev-server-ip
```

### Issue: Permission denied
**Solution:**
```bash
# Fix ownership
sudo chown -R $USER:$USER /opt/retail-store-scraper
# Or for Docker:
sudo chown -R $(id -u):$(id -g) data/ logs/
```

### Issue: Out of disk space
**Solution:**
```bash
# Check usage
df -h
du -sh data/*

# Clean old checkpoints
find data/*/checkpoints/ -mtime +30 -delete
```

See [DEPLOYMENT.md - Troubleshooting](DEPLOYMENT.md#troubleshooting) for more solutions.

## 📞 Next Steps

1. **Read** [DEPLOYMENT.md](DEPLOYMENT.md) for detailed instructions
2. **Run** `./deploy/validate.sh` to check repository
3. **Follow** [deploy/deploy-checklist.md](deploy/deploy-checklist.md) step-by-step
4. **Deploy** using your preferred method (Docker recommended)
5. **Monitor** via dashboard at `http://dev-server-ip:5001`
6. **Enjoy** automated retail store data collection!

---

**Ready to deploy?** Start here: `./deploy/validate.sh`

**Need help?** Check [DEPLOYMENT.md](DEPLOYMENT.md) or [deploy/QUICK-REFERENCE.md](deploy/QUICK-REFERENCE.md)
