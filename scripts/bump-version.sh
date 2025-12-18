#!/bin/bash
# Synod CLI Version Bump Script
#
# Usage:
#   ./scripts/bump-version.sh patch    # 2.2.43 -> 2.2.44
#   ./scripts/bump-version.sh minor    # 2.2.43 -> 2.3.0
#   ./scripts/bump-version.sh major    # 2.2.43 -> 3.0.0
#   ./scripts/bump-version.sh          # defaults to patch

set -e

BUMP_TYPE="${1:-patch}"
PYPROJECT="pyproject.toml"

if [[ ! -f "$PYPROJECT" ]]; then
    echo "Error: $PYPROJECT not found. Run from project root."
    exit 1
fi

# Get current version
CURRENT=$(grep -m1 'version = ' "$PYPROJECT" | cut -d'"' -f2)

if [[ -z "$CURRENT" ]]; then
    echo "Error: Could not find version in $PYPROJECT"
    exit 1
fi

# Parse version parts
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT"

# Bump version based on type
case "$BUMP_TYPE" in
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
    *)
        echo "Error: Unknown bump type '$BUMP_TYPE'. Use: major, minor, or patch"
        exit 1
        ;;
esac

NEW_VERSION="$MAJOR.$MINOR.$PATCH"

# Update pyproject.toml
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' "s/version = \"$CURRENT\"/version = \"$NEW_VERSION\"/" "$PYPROJECT"
else
    # Linux
    sed -i "s/version = \"$CURRENT\"/version = \"$NEW_VERSION\"/" "$PYPROJECT"
fi

echo "✓ Bumped version: $CURRENT -> $NEW_VERSION ($BUMP_TYPE)"
echo ""
echo "Next steps:"
echo "  git add pyproject.toml"
echo "  git commit -m \"v$NEW_VERSION: <description>\""
echo "  git push"
echo ""
echo "CI will automatically create a GitHub release and publish to PyPI."
