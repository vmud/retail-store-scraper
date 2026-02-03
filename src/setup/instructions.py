"""Human instruction templates for manual setup steps."""

import platform
from typing import Dict, List, Optional

from src.setup.diagnose import CheckResult, ProbeResult


# Instruction templates keyed by human_instructions value
INSTRUCTION_TEMPLATES: Dict[str, Dict[str, str]] = {
    "install_python": {
        "title": "Install Python 3.8-3.11",
        "description": "This project requires Python 3.8 through 3.11.",
        "macos": """### macOS (using Homebrew)

```bash
# Install Homebrew if not installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python 3.11
brew install python@3.11

# Verify installation
python3.11 --version
```

### macOS (using pyenv)

```bash
# Install pyenv
brew install pyenv

# Install Python 3.11
pyenv install 3.11

# Set as local version for this project
pyenv local 3.11

# Verify
python --version
```""",
        "linux": """### Ubuntu/Debian

```bash
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev

# Verify installation
python3.11 --version
```

### Fedora/RHEL

```bash
sudo dnf install python3.11 python3.11-devel

# Verify installation
python3.11 --version
```

### Using pyenv (any Linux)

```bash
# Install dependencies
sudo apt install -y build-essential libssl-dev zlib1g-dev \\
    libbz2-dev libreadline-dev libsqlite3-dev curl \\
    libncursesw5-dev xz-utils tk-dev libxml2-dev \\
    libxmlsec1-dev libffi-dev liblzma-dev

# Install pyenv
curl https://pyenv.run | bash

# Add to shell (bash)
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init -)"' >> ~/.bashrc
source ~/.bashrc

# Install Python
pyenv install 3.11
pyenv local 3.11
```""",
        "windows": """### Windows

1. **Download Python installer:**
   - Go to https://www.python.org/downloads/
   - Download Python 3.11.x

2. **Run the installer:**
   - Check "Add Python to PATH"
   - Click "Install Now"

3. **Verify in Command Prompt:**
   ```cmd
   python --version
   ```

### Using Chocolatey

```powershell
# Install Chocolatey if not installed (run PowerShell as Admin)
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# Install Python
choco install python311
```"""
    },

    "setup_oxylabs": {
        "title": "Configure Oxylabs Proxy Credentials",
        "description": "Oxylabs provides rotating residential proxies for web scraping. This is optional but recommended for production use.",
        "all": """### Sign Up

1. Go to https://oxylabs.io/
2. Sign up for a Residential Proxy plan
3. Get your credentials from the dashboard

### Configure Credentials

Add these lines to your `.env` file:

```bash
# Oxylabs Residential Proxy
OXYLABS_RESIDENTIAL_USERNAME=customer-YOUR_USERNAME
OXYLABS_RESIDENTIAL_PASSWORD=YOUR_PASSWORD

# OR use generic credentials (works for both residential and Web Scraper API)
OXYLABS_USERNAME=customer-YOUR_USERNAME
OXYLABS_PASSWORD=YOUR_PASSWORD
```

### Verify Configuration

```bash
# Test proxy connectivity
python run.py --retailer verizon --proxy residential --validate-proxy --test --limit 1
```

### Notes

- The `customer-` prefix is required for residential proxies
- Credentials are per-proxy-type (residential vs datacenter)
- Usage is metered - check dashboard for usage and billing"""
    },

    "setup_gcs": {
        "title": "Configure Google Cloud Storage",
        "description": "GCS provides cloud backup and team access to scraped data. This is optional.",
        "all": """### Create GCS Bucket

1. Go to https://console.cloud.google.com/storage
2. Click "Create Bucket"
3. Choose a globally unique name (e.g., `mycompany-retail-scraper-data`)
4. Select region closest to your location
5. **Enable object versioning** (recommended for data recovery)

### Create Service Account

1. Go to https://console.cloud.google.com/iam-admin/serviceaccounts
2. Click "Create Service Account"
3. Name: `retail-scraper` or similar
4. Grant role: `Storage Object Admin`
5. Click "Done"

### Download Key File

1. Click on the service account you created
2. Go to "Keys" tab
3. Click "Add Key" > "Create new key"
4. Choose JSON format
5. Save the file securely (e.g., `~/.gcloud/retail-scraper-sa.json`)

### Configure Credentials

Add these lines to your `.env` file:

```bash
# Google Cloud Storage
GCS_SERVICE_ACCOUNT_KEY=/path/to/your/service-account-key.json
GCS_BUCKET_NAME=your-bucket-name
GCS_PROJECT_ID=your-gcp-project-id  # Optional, auto-detected from key file

# Enable timestamped history (optional)
GCS_ENABLE_HISTORY=true
```

### Verify Configuration

```bash
# Test with a single retailer
python run.py --retailer verizon --cloud --test --limit 3
```

### Security Notes

- Never commit the service account key file to git
- Keep the key file permissions restricted: `chmod 600 /path/to/key.json`
- Consider using Workload Identity in production GKE environments"""
    },

    "install_docker": {
        "title": "Install Docker (Optional)",
        "description": "Docker enables containerized deployment. This is optional for local development.",
        "macos": """### macOS

1. Download Docker Desktop from https://www.docker.com/products/docker-desktop
2. Open the downloaded `.dmg` file
3. Drag Docker to Applications
4. Launch Docker from Applications

```bash
# Verify installation
docker --version
docker compose version
```""",
        "linux": """### Ubuntu/Debian

```bash
# Remove old versions
sudo apt remove docker docker-engine docker.io containerd runc

# Install dependencies
sudo apt update
sudo apt install ca-certificates curl gnupg lsb-release

# Add Docker's GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Add repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Add your user to docker group (avoids needing sudo)
sudo usermod -aG docker $USER

# Log out and back in, then verify
docker --version
docker compose version
```

### Fedora/RHEL

```bash
sudo dnf install dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
sudo dnf install docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER
```""",
        "windows": """### Windows

1. **Enable WSL2:**
   - Open PowerShell as Administrator
   - Run: `wsl --install`
   - Restart your computer

2. **Download Docker Desktop:**
   - Go to https://www.docker.com/products/docker-desktop
   - Download and run the installer

3. **Configure Docker Desktop:**
   - Enable WSL2 backend (recommended)
   - Start Docker Desktop

4. **Verify:**
   ```cmd
   docker --version
   docker compose version
   ```"""
    }
}


def get_platform_key() -> str:
    """Get the current platform key for instructions."""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    elif system == "linux":
        return "linux"
    elif system == "windows":
        return "windows"
    return "linux"  # Default to linux


def get_instruction(instruction_key: str) -> Optional[str]:
    """Get formatted instruction for a specific key.

    Args:
        instruction_key: The human_instructions value from CheckResult

    Returns:
        Formatted instruction string or None if not found
    """
    if instruction_key not in INSTRUCTION_TEMPLATES:
        return None

    template = INSTRUCTION_TEMPLATES[instruction_key]
    platform_key = get_platform_key()

    # Build the instruction text
    parts = []

    # Title
    if "title" in template:
        parts.append(f"## {template['title']}")

    # Description
    if "description" in template:
        parts.append(f"\n{template['description']}\n")

    # Platform-specific or generic instructions
    if platform_key in template:
        parts.append(template[platform_key])
    elif "all" in template:
        parts.append(template["all"])

    return "\n".join(parts)


def generate_instructions(probe_result: ProbeResult) -> str:
    """Generate human instructions for all issues requiring manual intervention.

    Args:
        probe_result: Result from environment probe

    Returns:
        Formatted string with all human instructions
    """
    human_issues = probe_result.human_required_issues
    warning_issues = [c for c in probe_result.warning_checks if c.human_instructions]

    if not human_issues and not warning_issues:
        return ""

    parts = [
        "=" * 50,
        "HUMAN ACTION REQUIRED",
        "=" * 50,
        ""
    ]

    # Critical/required issues first
    if human_issues:
        parts.append("### Required Actions\n")
        for check in human_issues:
            if check.human_instructions:
                instruction = get_instruction(check.human_instructions)
                if instruction:
                    parts.append(instruction)
                    parts.append("\n" + "-" * 40 + "\n")
                else:
                    parts.append(f"## {check.name}")
                    parts.append(f"\n{check.details}\n")
                    parts.append("\n" + "-" * 40 + "\n")

    # Optional/warning issues
    if warning_issues:
        parts.append("\n### Optional Actions (Warnings)\n")
        for check in warning_issues:
            if check.human_instructions:
                instruction = get_instruction(check.human_instructions)
                if instruction:
                    parts.append(instruction)
                    parts.append("\n" + "-" * 40 + "\n")

    # Resume instructions
    parts.append("\n" + "=" * 50)
    parts.append("After completing the required actions, run setup again:")
    parts.append("```bash")
    parts.append("python scripts/setup.py --resume")
    parts.append("```")
    parts.append("=" * 50)

    return "\n".join(parts)


def generate_single_instruction(check: CheckResult) -> str:
    """Generate instruction for a single check.

    Args:
        check: The CheckResult requiring human intervention

    Returns:
        Formatted instruction string
    """
    if not check.human_instructions:
        return f"Manual fix required for: {check.name}\nDetails: {check.details}"

    instruction = get_instruction(check.human_instructions)
    if instruction:
        return instruction
    else:
        return f"Manual fix required for: {check.name}\nDetails: {check.details}"
