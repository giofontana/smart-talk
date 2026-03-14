#!/bin/bash
# Verify Wyoming Polyglot Proxy add-on is ready for HA installation

set -e

echo "🔍 Verifying Wyoming Polyglot Proxy Add-on Configuration..."
echo ""

ADDON_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ADDON_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

errors=0
warnings=0

# Check required files
echo "📁 Checking required files..."
for file in config.yaml Dockerfile README.md run.sh requirements.txt; do
    if [ -f "$file" ]; then
        echo -e "  ${GREEN}✓${NC} $file exists"
    else
        echo -e "  ${RED}✗${NC} $file missing"
        errors=$((errors + 1))
    fi
done

if [ -f "CHANGELOG.md" ]; then
    echo -e "  ${GREEN}✓${NC} CHANGELOG.md exists (recommended)"
else
    echo -e "  ${YELLOW}⚠${NC} CHANGELOG.md missing (recommended)"
    warnings=$((warnings + 1))
fi
echo ""

# Check config.yaml syntax
echo "📝 Validating config.yaml..."
if command -v python3 &> /dev/null; then
    if python3 -c "import yaml; yaml.safe_load(open('config.yaml'))" 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} YAML syntax valid"

        # Extract key fields
        name=$(python3 -c "import yaml; print(yaml.safe_load(open('config.yaml'))['name'])")
        slug=$(python3 -c "import yaml; print(yaml.safe_load(open('config.yaml'))['slug'])")
        version=$(python3 -c "import yaml; print(yaml.safe_load(open('config.yaml'))['version'])")

        echo "  Name: $name"
        echo "  Slug: $slug"
        echo "  Version: $version"

        # Check slug format
        if [[ "$slug" =~ ^[a-z0-9-]+$ ]]; then
            echo -e "  ${GREEN}✓${NC} Slug format valid (lowercase, hyphens only)"
        else
            echo -e "  ${RED}✗${NC} Slug must be lowercase with hyphens only"
            errors=$((errors + 1))
        fi
    else
        echo -e "  ${RED}✗${NC} YAML syntax error"
        python3 -c "import yaml; yaml.safe_load(open('config.yaml'))" 2>&1
        errors=$((errors + 1))
    fi
else
    echo -e "  ${YELLOW}⚠${NC} Python3 not found, skipping YAML validation"
    warnings=$((warnings + 1))
fi
echo ""

# Check Dockerfile
echo "🐳 Checking Dockerfile..."
if grep -q "FROM python:3.12-slim" Dockerfile; then
    echo -e "  ${GREEN}✓${NC} Base image: python:3.12-slim"
elif grep -q "FROM python:" Dockerfile; then
    echo -e "  ${GREEN}✓${NC} Python base image found"
else
    echo -e "  ${YELLOW}⚠${NC} No Python base image found"
    warnings=$((warnings + 1))
fi

if grep -q "COPY requirements.txt" Dockerfile && grep -q "RUN pip install" Dockerfile; then
    echo -e "  ${GREEN}✓${NC} Requirements installation found"
else
    echo -e "  ${RED}✗${NC} No pip install step found"
    errors=$((errors + 1))
fi

if grep -q "CMD" Dockerfile || grep -q "ENTRYPOINT" Dockerfile; then
    echo -e "  ${GREEN}✓${NC} Container entry point defined"
else
    echo -e "  ${RED}✗${NC} No CMD or ENTRYPOINT found"
    errors=$((errors + 1))
fi
echo ""

# Check src directory
echo "📦 Checking source code..."
if [ -d "src" ]; then
    echo -e "  ${GREEN}✓${NC} src/ directory exists"

    for file in src/main.py src/stt_proxy.py src/tts_proxy.py src/config.py; do
        if [ -f "$file" ]; then
            echo -e "  ${GREEN}✓${NC} $file exists"
        else
            echo -e "  ${RED}✗${NC} $file missing"
            errors=$((errors + 1))
        fi
    done
else
    echo -e "  ${RED}✗${NC} src/ directory missing"
    errors=$((errors + 1))
fi
echo ""

# Check repository structure
echo "🌳 Checking repository structure..."
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
if [ -n "$REPO_ROOT" ]; then
    ADDON_NAME=$(basename "$ADDON_DIR")
    EXPECTED_PATH="$REPO_ROOT/$ADDON_NAME"

    if [ "$ADDON_DIR" = "$EXPECTED_PATH" ]; then
        echo -e "  ${GREEN}✓${NC} Add-on at repository root level"
    else
        echo -e "  ${YELLOW}⚠${NC} Add-on not at repository root"
        echo "    Current: $ADDON_DIR"
        echo "    Expected: $EXPECTED_PATH"
        warnings=$((warnings + 1))
    fi

    if [ -f "$REPO_ROOT/repository.json" ] || [ -f "$REPO_ROOT/repository.yaml" ]; then
        echo -e "  ${GREEN}✓${NC} Repository metadata exists"
    else
        echo -e "  ${YELLOW}⚠${NC} No repository.json or repository.yaml at root"
        warnings=$((warnings + 1))
    fi
else
    echo -e "  ${YELLOW}⚠${NC} Not in a git repository"
    warnings=$((warnings + 1))
fi
echo ""

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $errors -eq 0 ] && [ $warnings -eq 0 ]; then
    echo -e "${GREEN}✅ All checks passed!${NC}"
    echo ""
    echo "Your add-on is ready for Home Assistant installation."
    echo ""
    echo "Next steps:"
    echo "  1. Commit and push to GitHub:"
    echo "     git add ."
    echo "     git commit -m 'Add Wyoming Polyglot Proxy addon'"
    echo "     git push"
    echo ""
    echo "  2. Add repository to HA:"
    echo "     Settings → Add-ons → ⋮ → Repositories"
    echo "     Add: $(git remote get-url origin 2>/dev/null || echo 'YOUR_GITHUB_URL')"
    echo ""
    echo "  3. Install from Add-on Store"
    exit 0
elif [ $errors -eq 0 ]; then
    echo -e "${YELLOW}⚠ ${warnings} warning(s)${NC}"
    echo ""
    echo "The add-on should work, but consider fixing warnings."
    exit 0
else
    echo -e "${RED}❌ ${errors} error(s), ${warnings} warning(s)${NC}"
    echo ""
    echo "Please fix the errors above before installing in HA."
    exit 1
fi
