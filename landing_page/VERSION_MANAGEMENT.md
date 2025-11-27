# Version Management for Landing Page

## Current Approach
The landing page currently hardcodes version `0.3.0` in multiple locations.

## Version References in Landing Page
- Line 61: Schema.org structured data `"softwareVersion": "0.3.0"`
- Line 95: Hero badge `v0.3.0`
- Line 221: Terminal header `synod @ v0.3.0`
- Line 590: Footer version `v0.3.0`

## Future Options

### Option 1: Manual Updates (Current)
**Pros:** Simple, no automation needed
**Cons:** Easy to forget, requires updating 4+ locations

### Option 2: Build-Time Replacement
Use a build script to replace `{{VERSION}}` placeholders with actual version from `pyproject.toml`:
```bash
#!/bin/bash
VERSION=$(grep '^version = ' ../pyproject.toml | sed 's/version = "\(.*\)"/\1/')
sed "s/{{VERSION}}/$VERSION/g" index.template.html > index.html
```

**Pros:** Single source of truth, automated
**Cons:** Requires build step before deployment

### Option 3: GitHub API Dynamic Fetch
Use JavaScript to fetch latest release from GitHub API:
```javascript
fetch('https://api.github.com/repos/KekwanuLabs/synod-cli/releases/latest')
  .then(res => res.json())
  .then(data => {
    const version = data.tag_name.replace('v', '');
    document.querySelectorAll('.version').forEach(el => el.textContent = version);
  });
```

**Pros:** Always up-to-date, no manual updates
**Cons:** Requires JavaScript, API rate limits, won't work if GitHub is down

### Option 4: Static Site Generator
Use a static site generator (Hugo, Jekyll, 11ty) that can read from `pyproject.toml`:
```
{{ .Site.Data.version }}
```

**Pros:** Professional approach, integrates well with deployment
**Cons:** Requires SSG setup, learning curve

## Recommendation
For now, continue with **Option 1** (manual updates) since:
- Simple landing page doesn't need complex build system
- Version changes are infrequent (major releases only)
- Easy to update all 4 locations with find/replace

If the project grows and requires frequent version updates, move to **Option 2** (build-time replacement).
