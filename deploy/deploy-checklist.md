# Deployment Checklist

Use this checklist to ensure a smooth deployment to your remote dev server.

## Pre-Deployment (On Workstation)

- [ ] Code is tested locally
  ```bash
  pytest tests/
  pylint $(git ls-files '*.py')
  ```

- [ ] All changes committed to git
  ```bash
  git status
  git add .
  git commit -m "Prepare for deployment"
  ```

- [ ] Branch is up to date
  ```bash
  git pull origin main
  ```

- [ ] Environment file prepared (if using proxies)
  ```bash
  cp .env.example .env
  # Edit with your Oxylabs credentials
  ```

- [ ] Know your dev server IP and credentials
  - IP Address: `___________________`
  - Username: `___________________`
  - SSH Port: `___________________` (default: 22)

## Deployment Method Selection

Choose ONE method and check all steps in that section:

### Method A: Docker Deployment (Recommended)

#### Initial Setup
- [ ] SSH into dev server
  ```bash
  ssh user@dev-server-ip
  ```

- [ ] Verify Docker is installed
  ```bash
  docker --version
  docker compose version
  ```

- [ ] Transfer files to server (choose one):
  - [ ] **Git Clone**
    ```bash
    cd /opt
    sudo git clone <repository-url>
    ```
  - [ ] **rsync from workstation**
    ```bash
    rsync -avz --exclude 'venv' --exclude 'data' --exclude '.git' \
        /Users/vmud/Documents/dev/projects/retail-store-scraper/ \
        user@dev-server-ip:/opt/retail-store-scraper/
    ```

- [ ] Navigate to project directory
  ```bash
  cd /opt/retail-store-scraper
  ```

- [ ] Create `.env` file
  ```bash
  cp .env.example .env
  nano .env  # Add your credentials
  ```

- [ ] Build Docker images
  ```bash
  docker compose build
  ```

- [ ] Start services
  ```bash
  docker compose up -d
  ```

- [ ] Verify containers are running
  ```bash
  docker compose ps
  docker compose logs -f dashboard
  ```

- [ ] Access dashboard
  - [ ] Open browser: `http://dev-server-ip:5001`
  - [ ] Or SSH tunnel: `ssh -L 5001:localhost:5001 user@dev-server-ip`

### Method B: Native Python Deployment

#### Initial Setup
- [ ] SSH into dev server
- [ ] Verify Python 3.8-3.11 installed
  ```bash
  python3 --version
  ```
- [ ] Transfer files (same as Docker method)
- [ ] Create virtual environment
  ```bash
  cd /opt/retail-store-scraper
  python3.11 -m venv venv
  source venv/bin/activate
  ```
- [ ] Install dependencies
  ```bash
  pip install --upgrade pip
  pip install -r requirements.txt
  ```
- [ ] Create `.env` file
  ```bash
  cp .env.example .env
  nano .env
  ```
- [ ] Run test scrape
  ```bash
  python run.py --all --test
  ```

### Method C: Systemd Service Deployment

#### Initial Setup
- [ ] Complete Native Python setup above
- [ ] Run installation script
  ```bash
  sudo ./deploy/install.sh
  ```
- [ ] Configure environment in systemd service
  ```bash
  sudo nano /etc/systemd/system/retail-scraper.service
  ```
- [ ] Start and enable service
  ```bash
  sudo systemctl start retail-scraper
  sudo systemctl enable retail-scraper
  ```
- [ ] Check service status
  ```bash
  sudo systemctl status retail-scraper
  sudo journalctl -u retail-scraper -f
  ```

## First Run Validation

- [ ] Run test mode (10 stores per retailer)
  - Docker: `docker compose exec scraper python run.py --all --test`
  - Native: `python run.py --all --test`
  - Systemd: Service runs automatically, check logs

- [ ] Verify output files created
  ```bash
  ls -lh data/*/output/
  # Should see stores_latest.json for each retailer
  ```

- [ ] Check log files
  ```bash
  ls -lh logs/
  tail -100 logs/scraper.log
  ```

- [ ] Access dashboard and verify:
  - [ ] Retailers show correct status
  - [ ] Progress bars update
  - [ ] Logs appear in log viewer
  - [ ] Configuration editor works

## Production Run

- [ ] Stop test run if still running
  - Docker: `docker compose restart scraper`
  - Native: `Ctrl+C` or kill process
  - Systemd: `sudo systemctl stop retail-scraper`

- [ ] Review retailer configuration
  ```bash
  nano config/retailers.yaml
  # Verify enabled retailers and settings
  ```

- [ ] Start full production run
  - Docker: `docker compose exec scraper python run.py --all --resume`
  - Native: `python run.py --all --resume`
  - Systemd: `sudo systemctl start retail-scraper`

- [ ] Monitor progress
  - [ ] Dashboard: `http://dev-server-ip:5001`
  - [ ] CLI: `python run.py --status`
  - [ ] Logs: `tail -f logs/scraper.log`

- [ ] Estimate completion time
  - Direct mode: 8-12 hours
  - With proxies: 1-2 hours
  - Note start time: `___________________`
  - Expected completion: `___________________`

## Post-Deployment

- [ ] Set up automated backups
  ```bash
  # Add to crontab
  0 2 * * * tar -czf /backups/retail-scraper-$(date +\%Y\%m\%d).tar.gz /opt/retail-store-scraper/data/
  ```

- [ ] Configure firewall (if needed)
  ```bash
  sudo ufw allow from 192.168.1.0/24 to any port 5001
  ```

- [ ] Set up log rotation
  ```bash
  sudo nano /etc/logrotate.d/retail-scraper
  ```

- [ ] Document server details
  - Server hostname: `___________________`
  - Installation path: `/opt/retail-store-scraper`
  - Dashboard URL: `http://___________________:5001`
  - Deployment method: Docker / Native / Systemd (circle one)

- [ ] Schedule regular runs (optional)
  - [ ] Daily: `0 2 * * *`
  - [ ] Weekly: `0 2 * * 0`
  - [ ] Monthly: `0 2 1 * *`

## Troubleshooting

If you encounter issues, check:

- [ ] Container/service logs
- [ ] Network connectivity (ping dev server)
- [ ] Firewall rules (port 5001 accessible?)
- [ ] Disk space (`df -h`)
- [ ] Memory usage (`free -h`)
- [ ] Proxy credentials (if using)

See [DEPLOYMENT.md](../DEPLOYMENT.md) for detailed troubleshooting steps.

## Success Criteria

Deployment is successful when:

- ✅ Dashboard accessible at `http://dev-server-ip:5001`
- ✅ Test run completes successfully (60 stores total)
- ✅ Data files created in `data/*/output/`
- ✅ Logs show no critical errors
- ✅ Services auto-restart after reboot (if using Docker/systemd)

---

**Deployment Date**: ___________________  
**Deployed By**: ___________________  
**Notes**: 
```

```
