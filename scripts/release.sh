#!/bin/bash
# Synod Release Script
# Usage: ./scripts/release.sh [patch|minor|major]
# Example: ./scripts/release.sh minor  # 0.3.0 -> 0.4.0

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the bump type (default: patch)
BUMP_TYPE=${1:-patch}

if [[ ! "$BUMP_TYPE" =~ ^(patch|minor|major)$ ]]; then
    echo -e "${RED}Error: Invalid bump type. Use: patch, minor, or major${NC}"
    exit 1
fi

# Get current version from pyproject.toml
CURRENT_VERSION=$(grep -E '^version = "' pyproject.toml | sed 's/version = "\(.*\)"/\1/')
echo -e "${YELLOW}Current version: ${CURRENT_VERSION}${NC}"

# Parse version components
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"

# Bump version
case $BUMP_TYPE in
    major)
        MAJOR=$((MAJOR + 1))
        MINOR=0
        PATCH=0
        ;;
    minor)
        MINOR=$((MINOR + 1))
        PATCH=0
        ;;
    patch)
        PATCH=$((PATCH + 1))
        ;;
esac

NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}"
echo -e "${GREEN}New version: ${NEW_VERSION}${NC}"

# Confirm
read -p "Release v${NEW_VERSION}? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${RED}Aborted${NC}"
    exit 1
fi

# Update pyproject.toml
echo -e "${YELLOW}Updating pyproject.toml...${NC}"
sed -i '' "s/version = \"${CURRENT_VERSION}\"/version = \"${NEW_VERSION}\"/" pyproject.toml

# Check for uncommitted changes
if [[ -n $(git status --porcelain) ]]; then
    echo -e "${YELLOW}Committing changes...${NC}"
    git add .
    git commit -m "chore: bump version to ${NEW_VERSION}"
fi

# Create git tag
echo -e "${YELLOW}Creating git tag v${NEW_VERSION}...${NC}"
git tag -a "v${NEW_VERSION}" -m "Release v${NEW_VERSION}"

# Push to origin
echo -e "${YELLOW}Pushing to origin...${NC}"
git push origin main
git push origin "v${NEW_VERSION}"

# Create GitHub release (triggers PyPI publish)
echo -e "${YELLOW}Creating GitHub release...${NC}"

# Extract changelog for this version (between this version header and next)
CHANGELOG_CONTENT=$(awk "/## \[${NEW_VERSION}\]/{flag=1; next} /## \[/{flag=0} flag" CHANGELOG.md)

if [[ -z "$CHANGELOG_CONTENT" ]]; then
    CHANGELOG_CONTENT="Release v${NEW_VERSION}"
fi

gh release create "v${NEW_VERSION}" \
    --title "v${NEW_VERSION}" \
    --notes "$CHANGELOG_CONTENT"

echo -e "${GREEN}✓ Released v${NEW_VERSION}!${NC}"
echo -e "${GREEN}✓ GitHub Actions will now publish to PyPI${NC}"
echo ""
echo -e "View release: https://github.com/KekwanuLabs/synod-cli/releases/tag/v${NEW_VERSION}"
echo -e "View PyPI: https://pypi.org/project/synod-cli/${NEW_VERSION}/"
