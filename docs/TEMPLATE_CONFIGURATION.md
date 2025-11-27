# Template-Based Configuration

**Last Updated**: 2025-11-27

---

Synod supports **two ways** to configure your setup:

1. **Interactive prompts** (Recommended for beginners)
2. **Template file** (Fast track for power users)

This guide explains the template approach.

---

## Why Use Templates?

**Benefits:**
- ✅ Fast setup (no prompts, just edit a file)
- ✅ Version control friendly (commit template to repo)
- ✅ Easy to reproduce across environments
- ✅ Great for teams (everyone uses same config)
- ✅ Edit anytime with your favorite text editor

**When to use:**
- You know exactly which models and providers you want
- You're setting up multiple environments
- You want to commit configuration to git
- You prefer config files over interactive prompts

---

## Quick Start

### Step 1: Generate Template

```bash
synod init
```

This creates `.synod.template.yaml` in your current directory.

### Step 2: Edit Template

Open `.synod.template.yaml` in your editor and fill it out:

```yaml
mode: simple

bishops:
  - anthropic/claude-opus-4.5
  - openai/gpt-5.1-chat
  - x-ai/grok-4.1-fast

pope: anthropic/claude-opus-4.5

simple:
  openrouter:
    enabled: true
    api_key: "sk-or-v1-your-key-here"
```

### Step 3: Run Synod

```bash
synod query "optimize this function" -f myfile.py
```

Synod automatically detects and validates your template!

---

## Template Modes

### Simple Mode (One Provider for All)

**Best for:** Most users, especially if using OpenRouter

```yaml
mode: simple

bishops:
  - anthropic/claude-opus-4.5
  - openai/gpt-5.1-chat
  - x-ai/grok-4.1-fast
  - google/gemini-3-pro-preview

pope: anthropic/claude-opus-4.5

simple:
  openrouter:
    enabled: true
    api_key: "sk-or-v1-..."
```

**All models will use OpenRouter.**

---

### Mixed Mode (Different Provider per Model)

**Best for:** Optimizing costs, using cloud credits, mixing free tiers

```yaml
mode: mixed

bishops:
  - anthropic/claude-opus-4.5
  - openai/gpt-5.1-chat
  - x-ai/grok-4.1-fast
  - google/gemini-3-pro-preview

pope: anthropic/claude-opus-4.5

mixed:
  providers:
    azure_foundry:
      enabled: true
      endpoint: "https://synod-resource.services.ai.azure.com/api/projects/synod"
      api_key: "your-azure-key"

    google_vertex:
      enabled: true
      project_id: "your-gcp-project"
      region: "us-central1"

    openrouter:
      enabled: true
      api_key: "sk-or-v1-..."

  routing:
    anthropic/claude-sonnet-4.5: azure_foundry
    openai/gpt-5.1: azure_foundry
    x-ai/grok-4.1-fast: openrouter        # FREE!
    google/gemini-3-pro-preview: google_vertex
```

**Each model uses a different provider!**

---

## Supported Providers

### OpenRouter (Recommended) ✅

Access 50+ models through one API. **Best for getting started.**

```yaml
simple:
  openrouter:
    enabled: true
    api_key: "sk-or-v1-..."  # Get at https://openrouter.ai/keys
```

**Models available:** All of them! Including free models like `x-ai/grok-4.1-fast:free`

---

### Azure AI Foundry ✅

Use your Azure credits for GPT, Claude, DeepSeek, Llama models.

```yaml
simple:
  azure_foundry:
    enabled: true
    endpoint: "https://your-resource.services.ai.azure.com/api/projects/your-project"
    api_key: "your-azure-key"
```

**Models available:**
- Claude Sonnet 4.5, Opus 4.5
- GPT 5.1, GPT 4o
- DeepSeek V3.1
- Meta Llama 3.3, 3.1

---

### Other Providers (Available)

The following providers are defined but may require additional setup:

- **Google Vertex AI** - Gemini models via GCP
- **Anthropic Direct** - Claude models via Anthropic API
- **OpenAI Direct** - GPT models via OpenAI API
- **Azure OpenAI** - GPT models via Azure OpenAI Service
- **AWS Bedrock** - Various models via AWS

For these providers, use OpenRouter as a simpler alternative, or configure in mixed mode with proper credentials.

---

## Validation

Synod validates your template automatically:

### ✅ Checks Performed

1. **Mode** is "simple" or "mixed"
2. **At least 3 bishops** selected
3. **Pope** is one of the bishops
4. **Model format** is correct (`provider/model-name`)
5. **In simple mode**: Exactly one provider enabled
6. **In mixed mode**: All bishops have routing entries
7. **Credentials** are provided (no empty strings)
8. **Routed providers** are enabled

### ❌ If Validation Fails

Synod shows clear error messages:

```
╭──────────── ⚠️  Configuration Error ────────────╮
│ Template Validation Failed                      │
│                                                  │
│ Found the following issues in                   │
│ .synod.template.yaml:                           │
│                                                  │
│ ❌ Simple mode: no provider enabled             │
│ ❌ OpenRouter: 'api_key' is required            │
│                                                  │
│ 💡 Fix these issues and try again, or run      │
│    synod config for interactive setup.          │
╰──────────────────────────────────────────────────╯
```

**Then you can:**
- Fix the errors and try again
- Run `synod config` for interactive setup

---

## Priority System

Synod checks configuration in this order:

1. **Template file** (`.synod.template.yaml` in current directory)
2. **Template in home** (`~/.synod.template.yaml`)
3. **Interactive prompts** (if no template found)

**This means:**
- Template always takes priority
- Different projects can have different configs
- Fallback to home template for global config
- Fallback to interactive if no template at all

---

## Editing Configuration

### Option 1: Edit Template Directly

```bash
# Open in your editor
code .synod.template.yaml

# Synod will detect changes automatically
synod query "your question"
```

### Option 2: Use Interactive Config

```bash
synod config
```

### Option 3: Edit in Interactive Mode

```
synod> /bishops
```

---

## Examples

### Example 1: Simple OpenRouter Setup

**Use case:** Just want to try Synod, no cloud credits

```yaml
mode: simple

bishops:
  - anthropic/claude-opus-4.5
  - openai/gpt-5.1-chat
  - x-ai/grok-4.1-fast
  - google/gemini-3-pro-preview

pope: anthropic/claude-opus-4.5

simple:
  openrouter:
    enabled: true
    api_key: "sk-or-v1-1234567890"
```

**Setup time:** 2 minutes

---

### Example 2: Azure AI Foundry Only

**Use case:** Using Azure credits for everything

```yaml
mode: simple

bishops:
  - anthropic/claude-opus-4.5
  - openai/gpt-5.1-chat
  - deepseek/deepseek-v3.1
  - meta/llama-3.3-70b

pope: anthropic/claude-opus-4.5

simple:
  azure_foundry:
    enabled: true
    endpoint: "https://synod-resource.services.ai.azure.com/api/projects/synod"
    api_key: "abc123def456"
```

**Cost:** Uses your Azure credits

---

### Example 3: Mixed Mode (Optimize Costs)

**Use case:** Use Azure for most, Google for Gemini, OpenRouter for free Grok

```yaml
mode: mixed

bishops:
  - anthropic/claude-opus-4.5
  - openai/gpt-5.1-chat
  - x-ai/grok-4.1-fast
  - google/gemini-3-pro-preview

pope: anthropic/claude-opus-4.5

mixed:
  providers:
    azure_foundry:
      enabled: true
      endpoint: "azure-endpoint"
      api_key: "abc123"

    google_vertex:
      enabled: true
      project_id: "my-gcp-project"
      region: "us-central1"

    openrouter:
      enabled: true
      api_key: "sk-or-v1-xyz789"

  routing:
    anthropic/claude-sonnet-4.5: azure_foundry
    openai/gpt-5.1: azure_foundry
    x-ai/grok-4.1-fast: openrouter        # FREE!
    google/gemini-3-pro-preview: google_vertex
```

**Cost:** Optimized (uses cloud credits + free tier)

---

### Example 4: Team Configuration

**Use case:** Same config for whole team

```yaml
# .synod.template.yaml - committed to git

mode: simple

bishops:
  - anthropic/claude-opus-4.5
  - openai/gpt-5.1-chat
  - x-ai/grok-4.1-fast

pope: anthropic/claude-opus-4.5

simple:
  openrouter:
    enabled: true
    api_key: ""  # Each team member fills this in locally
```

**Workflow:**
1. Commit `.synod.template.yaml` (with empty `api_key`)
2. Add `.synod.template.yaml` to `.gitignore` **after** first commit
3. Team members clone repo
4. Each fills in their own `api_key`
5. Everyone has same model config, different credentials

---

## Security Best Practices

### ⚠️ Never Commit API Keys

Add to `.gitignore`:

```gitignore
.synod.template.yaml
.env
```

### ✅ Use Environment Variables (Advanced)

Instead of hardcoding keys in template:

```yaml
simple:
  openrouter:
    enabled: true
    api_key: "${OPENROUTER_API_KEY}"  # Read from env var
```

Then:
```bash
export OPENROUTER_API_KEY="sk-or-v1-..."
synod query "your question"
```

---

## Troubleshooting

### "Template file not found"

**Problem:** Synod can't find `.synod.template.yaml`

**Solution:**
```bash
synod init  # Create template in current directory
```

### "Template validation failed"

**Problem:** Template has errors

**Solution:** Check error messages and fix issues. Common problems:
- Empty `api_key`
- Wrong `mode` value
- Pope not in bishops list
- Less than 3 bishops

### "Model not available on provider"

**Problem:** Trying to use model on provider that doesn't have it

**Solution:** Check model availability in template comments or see the Supported Providers section above.

### "YAML syntax error"

**Problem:** Invalid YAML syntax

**Solution:** Check indentation (use spaces, not tabs). Validate YAML at https://www.yamllint.com

---

## FAQ

**Q: Can I use both template and interactive setup?**
A: Template takes priority. Delete template to use interactive setup.

**Q: How do I switch from simple to mixed mode?**
A: Edit template file, change `mode: simple` to `mode: mixed`, add routing section.

**Q: Can I have different templates for different projects?**
A: Yes! Place `.synod.template.yaml` in each project directory.

**Q: What if I want global config for all projects?**
A: Place template in your home directory: `~/.synod.template.yaml`

**Q: Can I mix OpenRouter models with direct providers in mixed mode?**
A: Absolutely! That's the whole point of mixed mode.

**Q: How do I know which provider a model is using?**
A: Synod shows routing summary after loading template. Or check `routing` section in mixed mode.

**Q: Can I validate template without running Synod?**
A: Not yet, but you can run `synod query "test"` to trigger validation.

---

## Next Steps

1. ✅ Run `synod init` to create template
2. ✅ Edit template with your models and credentials
3. ✅ Run `synod query` to start using Synod
4. ✅ Edit template anytime to change configuration

**Template not for you?** Run `synod config` for interactive setup!

---

## Related Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - Full system architecture
- [CLAUDE.md](CLAUDE.md) - Developer guide
- [README.md](../README.md) - User documentation

Happy coding! 🎉
