# Deployment Files

This directory contains all files needed to deploy the retail store scraper to a remote dev server.

## Quick Start

### 1. Validate Repository (Optional but Recommended)
```bash
./deploy/validate.sh
```

### 2. Transfer Files to Dev Server
```bash
# Use the helper script (easiest method)
./deploy/rsync-deploy.sh user@dev-server-ip

# Or specify custom path
./deploy/rsync-deploy.sh user@192.168.1.100 /opt/retail-store-scraper
```

### 3. Follow Server-Side Instructions
The rsync script will show you next steps. Generally:
```bash
# SSH into server
ssh user@dev-server-ip

# Docker deployment
cd /opt/retail-store-scraper
cp .env.example .env
nano .env  # Add credentials
docker compose build
docker compose up -d

# Access dashboard
http://dev-server-ip:5001
```

## Files in This Directory

### Scripts
- **`validate.sh`** - Pre-deployment validation script
  - Checks Python syntax, YAML config, Docker files
  - Verifies required files exist
  - Detects sensitive files in git
  - Run before deployment to catch issues early

- **`rsync-deploy.sh`** - File transfer helper script
  - Syncs files from workstation to dev server
  - Excludes venv, data, logs, and build artifacts
  - Tests SSH connection before transfer
  - Sets proper permissions on remote

- **`install.sh`** - Systemd service installation script
  - Creates system user and directories
  - Installs Python dependencies in venv
  - Configures systemd service
  - Run on server as root: `sudo ./deploy/install.sh`

### Documentation
- **`QUICK-REFERENCE.md`** - Command reference card
  - Common Docker commands
  - Systemd service management
  - Monitoring and troubleshooting
  - File transfer methods
  - Backup procedures

- **`deploy-checklist.md`** - Step-by-step deployment checklist
  - Pre-deployment checks
  - Method-specific instructions (Docker/Native/Systemd)
  - First run validation
  - Post-deployment tasks

### Service Files
- **`scraper.service`** - Systemd unit file
  - Service definition for Linux systems
  - Auto-restart on failure
  - Security hardening (NoNewPrivileges, PrivateTmp, etc.)
  - Installed by `install.sh`

## Deployment Methods

### Method 1: Docker (Recommended)
**Best for:** Production, ease of deployment, isolation

```bash
# On dev server
docker compose build
docker compose up -d
docker compose logs -f
```

**Pros:**
- Easy setup and updates
- Isolated environment
- Built-in health checks
- Automatic restarts

**Cons:**
- Requires Docker installation
- Slight resource overhead

### Method 2: Native Python
**Best for:** Development, debugging, resource-constrained systems

```bash
# On dev server
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run.py --all --test
```

**Pros:**
- Direct access to code
- Lower resource usage
- Easier debugging

**Cons:**
- Manual dependency management
- No automatic restarts
- Manual process management

### Method 3: Systemd Service
**Best for:** Long-running background tasks, automatic startup

```bash
# On dev server
sudo ./deploy/install.sh
sudo systemctl start retail-scraper
sudo journalctl -u retail-scraper -f
```

**Pros:**
- Auto-start on boot
- System-level logging
- Managed by systemd
- Automatic restarts

**Cons:**
- Requires root access
- More complex setup
- System-level changes

## Common Tasks

### Transfer Files
```bash
# From workstation
./deploy/rsync-deploy.sh user@dev-server-ip
```

### Validate Before Deploy
```bash
# From workstation
./deploy/validate.sh
```

### Update Deployment
```bash
# From workstation - transfer new files
./deploy/rsync-deploy.sh user@dev-server-ip

# On dev server - restart services
docker compose down && docker compose build && docker compose up -d
# Or systemd:
sudo systemctl restart retail-scraper
```

### Check Status
```bash
# Docker
docker compose exec scraper python run.py --status

# Systemd
sudo systemctl status retail-scraper

# Native
python run.py --status
```

### View Logs
```bash
# Docker
docker compose logs -f scraper

# Systemd
sudo journalctl -u retail-scraper -f

# Native
tail -f logs/scraper.log
```

## Documentation Links

- **[Complete Deployment Guide](../DEPLOYMENT.md)** - Full deployment documentation
- **[Quick Reference](QUICK-REFERENCE.md)** - Command cheat sheet
- **[Deployment Checklist](deploy-checklist.md)** - Step-by-step guide
- **[Main README](../README.md)** - Project overview
- **[Agent Guide](../AGENTS.md)** - Developer documentation

## Support

For issues or questions:
1. Check the [Deployment Guide](../DEPLOYMENT.md) troubleshooting section
2. Review [Quick Reference](QUICK-REFERENCE.md) for common commands
3. Verify configuration in `config/retailers.yaml`
4. Check logs for error messages

## Security Notes

1. **Never commit `.env` files** - Contains sensitive credentials
2. **Use SSH keys** instead of passwords for server access
3. **Restrict dashboard port** to local network only:
   ```bash
   sudo ufw allow from 192.168.1.0/24 to any port 5001
   ```
4. **Run as non-root user** - Docker and systemd both use non-root users
5. **Keep secrets secure** - Store credentials in `.env`, not in code

## Next Steps After Deployment

1. ✅ Verify dashboard access: `http://dev-server-ip:5001`
2. ✅ Run test scrape: `--all --test`
3. ✅ Check data output: `ls -lh data/*/output/`
4. ✅ Run full scrape: `--all --resume`
5. ✅ Set up scheduled runs (cron/systemd timer)
6. ✅ Configure backups
7. ✅ Monitor resource usage

---

**Ready to deploy?** Start with `./deploy/validate.sh` to check your repository!
