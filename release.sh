#!/bin/bash
# Synod Release Script
# Usage: ./release.sh [test|prod]

set -e  # Exit on error

MODE=${1:-test}

echo "🚀 Synod Release Script"
echo "======================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo -e "${RED}Error: pyproject.toml not found. Run this from the project root.${NC}"
    exit 1
fi

# Get current version
VERSION=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')
echo -e "${GREEN}Current version: ${VERSION}${NC}"
echo ""

# Pre-release checks
echo "📋 Pre-release checklist:"
echo "  [ ] All tests pass"
echo "  [ ] Documentation updated"
echo "  [ ] CHANGELOG.md updated"
echo "  [ ] Author info correct in pyproject.toml"
echo ""
read -p "Have you completed all checks? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Aborted. Complete checks first.${NC}"
    exit 1
fi

# Clean old builds
echo -e "${GREEN}🧹 Cleaning old builds...${NC}"
rm -rf dist/ build/ *.egg-info 2>/dev/null || true

# Build package
echo -e "${GREEN}📦 Building package...${NC}"
uv build

if [ ! -d "dist" ]; then
    echo -e "${RED}Error: Build failed, no dist/ directory${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✓ Built:${NC}"
ls -lh dist/
echo ""

# Upload based on mode
if [ "$MODE" == "test" ]; then
    echo -e "${YELLOW}📤 Uploading to TestPyPI...${NC}"
    echo ""
    echo "This will upload to https://test.pypi.org/"
    echo "You'll need your TestPyPI API token."
    echo ""
    read -p "Continue? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Aborted${NC}"
        exit 0
    fi

    # Install twine if needed
    if ! command -v twine &> /dev/null; then
        echo "Installing twine..."
        pip install twine
    fi

    twine upload --repository testpypi dist/*

    echo ""
    echo -e "${GREEN}✓ Uploaded to TestPyPI!${NC}"
    echo ""
    echo "Test installation:"
    echo "  pip install --index-url https://test.pypi.org/simple/ \\"
    echo "              --extra-index-url https://pypi.org/simple/ \\"
    echo "              synod-cli"
    echo ""
    echo "View at: https://test.pypi.org/project/synod-cli/${VERSION}/"

elif [ "$MODE" == "prod" ]; then
    echo -e "${RED}⚠️  PRODUCTION RELEASE${NC}"
    echo ""
    echo "This will upload to REAL PyPI (https://pypi.org/)"
    echo "This is PERMANENT and CANNOT BE UNDONE!"
    echo ""
    echo -e "${YELLOW}Have you tested on TestPyPI first?${NC}"
    read -p "Are you SURE you want to continue? (yes/N) " -r
    echo
    if [[ ! $REPLY == "yes" ]]; then
        echo -e "${YELLOW}Aborted${NC}"
        exit 0
    fi

    # Install twine if needed
    if ! command -v twine &> /dev/null; then
        echo "Installing twine..."
        pip install twine
    fi

    twine upload dist/*

    echo ""
    echo -e "${GREEN}✓✓✓ Released to PyPI! ✓✓✓${NC}"
    echo ""
    echo "Installation:"
    echo "  pip install synod-cli"
    echo ""
    echo "View at: https://pypi.org/project/synod-cli/${VERSION}/"
    echo ""
    echo "Next steps:"
    echo "  1. Tag release: git tag v${VERSION} && git push --tags"
    echo "  2. Create GitHub release"
    echo "  3. Announce!"

else
    echo -e "${RED}Error: Mode must be 'test' or 'prod'${NC}"
    echo "Usage: $0 [test|prod]"
    exit 1
fi
