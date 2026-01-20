#!/bin/bash
#
# Pre-Deployment Validation Script
# Checks that the repository is ready for deployment
#
# Usage: ./deploy/validate.sh
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

ERRORS=0
WARNINGS=0

echo "=========================================="
echo "Pre-Deployment Validation"
echo "=========================================="
echo ""

# Change to repo directory
cd "$REPO_DIR"

# Check 1: Git status
echo -e "${BLUE}[1/10] Checking git status...${NC}"
if git rev-parse --git-dir > /dev/null 2>&1; then
    if [ -z "$(git status --porcelain)" ]; then
        echo -e "${GREEN}✓ Working directory is clean${NC}"
    else
        echo -e "${YELLOW}⚠ You have uncommitted changes${NC}"
        git status --short
        WARNINGS=$((WARNINGS + 1))
    fi
else
    echo -e "${YELLOW}⚠ Not a git repository${NC}"
    WARNINGS=$((WARNINGS + 1))
fi

# Check 2: Required files exist
echo -e "${BLUE}[2/10] Checking required files...${NC}"
REQUIRED_FILES=(
    "run.py"
    "requirements.txt"
    "config/retailers.yaml"
    "Dockerfile"
    "docker-compose.yml"
    "dashboard/app.py"
    ".env.example"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "  ✓ $file"
    else
        echo -e "${RED}  ✗ Missing: $file${NC}"
        ERRORS=$((ERRORS + 1))
    fi
done

# Check 3: Python syntax
echo -e "${BLUE}[3/10] Checking Python syntax...${NC}"
if command -v python3 &> /dev/null; then
    PYTHON_FILES=$(find src tests dashboard -name "*.py" 2>/dev/null | head -20)
    SYNTAX_ERRORS=0
    for file in $PYTHON_FILES; do
        if ! python3 -m py_compile "$file" 2>/dev/null; then
            echo -e "${RED}  ✗ Syntax error in $file${NC}"
            SYNTAX_ERRORS=$((SYNTAX_ERRORS + 1))
        fi
    done
    
    if [ $SYNTAX_ERRORS -eq 0 ]; then
        echo -e "${GREEN}✓ No Python syntax errors found${NC}"
    else
        ERRORS=$((ERRORS + SYNTAX_ERRORS))
    fi
else
    echo -e "${YELLOW}⚠ Python not found, skipping syntax check${NC}"
    WARNINGS=$((WARNINGS + 1))
fi

# Check 4: Dependencies file validity
echo -e "${BLUE}[4/10] Checking requirements.txt...${NC}"
if [ -f "requirements.txt" ]; then
    # Check for duplicate packages
    if [ "$(sort requirements.txt | uniq -d)" ]; then
        echo -e "${RED}✗ Duplicate packages found in requirements.txt${NC}"
        ERRORS=$((ERRORS + 1))
    else
        echo -e "${GREEN}✓ requirements.txt is valid${NC}"
    fi
else
    echo -e "${RED}✗ requirements.txt not found${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check 5: Docker files validity
echo -e "${BLUE}[5/10] Checking Docker configuration...${NC}"
if command -v docker &> /dev/null; then
    # Check if Dockerfile exists and has basic syntax
    if [ -f "Dockerfile" ]; then
        # Basic Dockerfile syntax check (look for FROM instruction)
        if grep -q "^FROM" Dockerfile; then
            echo -e "${GREEN}✓ Dockerfile exists and has FROM instruction${NC}"
        else
            echo -e "${RED}✗ Dockerfile missing FROM instruction${NC}"
            ERRORS=$((ERRORS + 1))
        fi
    else
        echo -e "${RED}✗ Dockerfile not found${NC}"
        ERRORS=$((ERRORS + 1))
    fi
    
    # Validate docker-compose.yml
    if docker compose config > /dev/null 2>&1; then
        echo -e "${GREEN}✓ docker-compose.yml is valid${NC}"
    else
        echo -e "${RED}✗ docker-compose.yml has errors${NC}"
        ERRORS=$((ERRORS + 1))
    fi
    
    echo -e "${YELLOW}  Note: Full Docker build not tested (run 'docker compose build' to verify)${NC}"
else
    echo -e "${YELLOW}⚠ Docker not found, skipping Docker validation${NC}"
    WARNINGS=$((WARNINGS + 1))
fi

# Check 6: YAML configuration
echo -e "${BLUE}[6/10] Checking YAML configuration...${NC}"
if command -v python3 &> /dev/null; then
    if python3 -c "import yaml; yaml.safe_load(open('config/retailers.yaml'))" 2>/dev/null; then
        echo -e "${GREEN}✓ retailers.yaml is valid YAML${NC}"
    else
        echo -e "${RED}✗ retailers.yaml has syntax errors${NC}"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "${YELLOW}⚠ Cannot validate YAML (Python/PyYAML not available)${NC}"
    WARNINGS=$((WARNINGS + 1))
fi

# Check 7: Deployment scripts
echo -e "${BLUE}[7/10] Checking deployment scripts...${NC}"
DEPLOY_SCRIPTS=(
    "deploy/install.sh"
    "deploy/rsync-deploy.sh"
)

for script in "${DEPLOY_SCRIPTS[@]}"; do
    if [ -f "$script" ]; then
        if [ -x "$script" ]; then
            echo -e "  ✓ $script (executable)"
        else
            echo -e "${YELLOW}  ⚠ $script exists but is not executable${NC}"
            echo "    Run: chmod +x $script"
            WARNINGS=$((WARNINGS + 1))
        fi
    else
        echo -e "${RED}  ✗ Missing: $script${NC}"
        ERRORS=$((ERRORS + 1))
    fi
done

# Check 8: Documentation
echo -e "${BLUE}[8/10] Checking documentation...${NC}"
DOCS=(
    "README.md"
    "DEPLOYMENT.md"
    "AGENTS.md"
    "CLAUDE.md"
)

for doc in "${DOCS[@]}"; do
    if [ -f "$doc" ]; then
        echo -e "  ✓ $doc"
    else
        echo -e "${YELLOW}  ⚠ Missing: $doc${NC}"
        WARNINGS=$((WARNINGS + 1))
    fi
done

# Check 9: .gitignore completeness
echo -e "${BLUE}[9/10] Checking .gitignore...${NC}"
if [ -f ".gitignore" ]; then
    GITIGNORE_PATTERNS=(
        "venv"
        "data"
        "logs"
        "__pycache__"
        ".env"
    )
    
    MISSING_PATTERNS=()
    for pattern in "${GITIGNORE_PATTERNS[@]}"; do
        if ! grep -q "$pattern" .gitignore; then
            MISSING_PATTERNS+=("$pattern")
        fi
    done
    
    if [ ${#MISSING_PATTERNS[@]} -eq 0 ]; then
        echo -e "${GREEN}✓ .gitignore is complete${NC}"
    else
        echo -e "${YELLOW}⚠ .gitignore is missing patterns: ${MISSING_PATTERNS[*]}${NC}"
        WARNINGS=$((WARNINGS + 1))
    fi
else
    echo -e "${RED}✗ .gitignore not found${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check 10: Sensitive files not committed
echo -e "${BLUE}[10/10] Checking for sensitive files...${NC}"
SENSITIVE_PATTERNS=(
    "*.env"
    "*.pem"
    "*.key"
    "*secret*"
    "*password*"
    "*credential*"
)

FOUND_SENSITIVE=0
for pattern in "${SENSITIVE_PATTERNS[@]}"; do
    if git ls-files "$pattern" 2>/dev/null | grep -q .; then
        echo -e "${RED}✗ Sensitive files may be committed: $pattern${NC}"
        git ls-files "$pattern"
        FOUND_SENSITIVE=1
    fi
done

if [ $FOUND_SENSITIVE -eq 0 ]; then
    echo -e "${GREEN}✓ No sensitive files detected in git${NC}"
else
    ERRORS=$((ERRORS + 1))
fi

# Summary
echo ""
echo "=========================================="
echo "Validation Summary"
echo "=========================================="

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed! Repository is ready for deployment.${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Review DEPLOYMENT.md for deployment instructions"
    echo "  2. Use ./deploy/rsync-deploy.sh to transfer files"
    echo "  3. Follow deploy/deploy-checklist.md on the server"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠ Validation passed with $WARNINGS warning(s)${NC}"
    echo ""
    echo "You can proceed with deployment, but review warnings above."
    exit 0
else
    echo -e "${RED}✗ Validation failed with $ERRORS error(s) and $WARNINGS warning(s)${NC}"
    echo ""
    echo "Please fix the errors above before deploying."
    exit 1
fi
