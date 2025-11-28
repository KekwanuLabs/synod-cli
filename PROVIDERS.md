# Provider Setup Guide

Synod uses [OpenRouter](https://openrouter.ai) as its API gateway, which gives you access to all major AI providers through a single API key. This guide covers how to set up each provider.

## Table of Contents

- [OpenRouter (Required)](#openrouter-required)
- [Using Your Own Cloud Accounts](#using-your-own-cloud-accounts)
  - [Azure OpenAI](#azure-openai)
  - [AWS Bedrock](#aws-bedrock)
  - [Google Vertex AI](#google-vertex-ai)
  - [Anthropic Direct](#anthropic-direct)
- [Model Selection Guide](#model-selection-guide)
- [Cost Optimization](#cost-optimization)

---

## OpenRouter (Required)

OpenRouter is the only API key you need for Synod. It routes requests to various AI providers and handles authentication, rate limiting, and failover.

### Setup

1. **Create an account** at [openrouter.ai](https://openrouter.ai)

2. **Generate an API key** at [openrouter.ai/keys](https://openrouter.ai/keys)

3. **Add credits** - OpenRouter uses prepaid credits. Add funds at [openrouter.ai/credits](https://openrouter.ai/credits)

4. **Configure Synod**:
   ```bash
   # Option 1: Environment variable
   export OPENROUTER_API_KEY="sk-or-v1-..."

   # Option 2: Run config wizard
   synod config
   ```

### Pricing

OpenRouter charges per token with small margins on top of provider costs. View current pricing at [openrouter.ai/models](https://openrouter.ai/models).

**Typical costs per Synod debate:**
- Simple query (3 bishops, 1 round): ~$0.02-0.05
- Complex query (5 bishops, 3 rounds): ~$0.10-0.30
- With Claude Opus 4.5 as Pope: Add ~$0.05-0.15

---

## Using Your Own Cloud Accounts

If you already have accounts with cloud providers, you can link them to OpenRouter and use your existing credits/contracts. **No markup fees** - you pay your provider's rates directly.

### Azure OpenAI

Use your Azure OpenAI deployments through OpenRouter.

#### Setup

1. Go to [openrouter.ai/settings/integrations](https://openrouter.ai/settings/integrations)

2. Click **"Connect Azure"**

3. Enter your Azure credentials:
   - **Endpoint URL**: `https://your-resource.openai.azure.com/`
   - **API Key**: Your Azure OpenAI API key
   - **Deployment Names**: Map your deployments to models

4. Once connected, select Azure-routed models in Synod:
   ```bash
   synod config
   # Choose models with "Azure" routing when available
   ```

#### Supported Models via Azure
- GPT-4o
- GPT-4 Turbo
- GPT-4
- GPT-3.5 Turbo

---

### AWS Bedrock

Use your AWS Bedrock access for Anthropic Claude and other models.

#### Setup

1. Go to [openrouter.ai/settings/integrations](https://openrouter.ai/settings/integrations)

2. Click **"Connect AWS"**

3. Enter your AWS credentials:
   - **Access Key ID**
   - **Secret Access Key**
   - **Region**: e.g., `us-east-1`

4. Ensure you have Bedrock model access enabled in your AWS account:
   - Go to AWS Console → Bedrock → Model access
   - Request access to Claude, Llama, etc.

#### Supported Models via Bedrock
- Claude 3.5 Sonnet
- Claude 3 Opus
- Claude 3 Haiku
- Llama 3.1 (70B, 405B)
- Mistral Large

---

### Google Vertex AI

Use your Google Cloud credits for Gemini models.

#### Setup

1. Go to [openrouter.ai/settings/integrations](https://openrouter.ai/settings/integrations)

2. Click **"Connect Google Cloud"**

3. Authenticate with your Google Cloud account

4. Select your GCP project with Vertex AI enabled

#### Supported Models via Vertex AI
- Gemini 2.0 Flash
- Gemini 1.5 Pro
- Gemini 1.5 Flash

---

### Anthropic Direct

Use your Anthropic API key directly (useful if you have volume discounts).

#### Setup

1. Go to [openrouter.ai/settings/integrations](https://openrouter.ai/settings/integrations)

2. Click **"Connect Anthropic"**

3. Enter your Anthropic API key from [console.anthropic.com](https://console.anthropic.com)

#### Supported Models
- Claude Opus 4.5
- Claude Sonnet 4
- Claude 3.5 Sonnet
- Claude 3 Haiku

---

## Model Selection Guide

Synod uses two roles: **Bishops** (proposers) and **Pope** (synthesizer).

### Recommended Pope Models

The Pope needs strong reasoning and synthesis capabilities:

| Model | Strength | Cost |
|-------|----------|------|
| **Claude Opus 4.5** | Best overall reasoning | $$$ |
| **Claude Sonnet 4** | Great balance | $$ |
| **GPT-4o** | Strong general purpose | $$ |
| **Gemini 1.5 Pro** | Good with long context | $$ |

### Recommended Bishop Models

Bishops benefit from diversity - use different model families:

| Model | Strength | Best For |
|-------|----------|----------|
| **Claude Opus 4.5** | Deep reasoning | Complex architecture |
| **Claude Sonnet 4** | Balanced | General coding |
| **GPT-4o** | Broad knowledge | API design, patterns |
| **Gemini 2.0 Flash** | Fast, capable | Quick iterations |
| **DeepSeek V3** | Strong coding | Algorithms, optimization |
| **Llama 3.1 405B** | Open weights | Diverse perspective |

### Default Configuration

Synod's default setup balances quality and cost:

```yaml
bishops:
  - anthropic/claude-sonnet-4
  - openai/gpt-4o
  - google/gemini-2.0-flash
pope: anthropic/claude-opus-4-5
```

---

## Cost Optimization

### Tips to Reduce Costs

1. **Use fewer bishops for simple queries**
   - Synod's pre-debate intelligence automatically adjusts, but you can configure defaults

2. **Use faster models for bishops**
   - Gemini Flash and DeepSeek are cost-effective bishops
   - Reserve expensive models (Opus) for the Pope role

3. **Link your cloud accounts**
   - If you have Azure/AWS/GCP credits, use them instead of OpenRouter's rates

4. **Monitor usage**
   ```bash
   synod> /cost    # View session costs
   synod> /stats   # View detailed statistics
   ```

### Cost Comparison (approximate per 1M tokens)

| Model | Input | Output |
|-------|-------|--------|
| Claude Opus 4.5 | $15 | $75 |
| Claude Sonnet 4 | $3 | $15 |
| GPT-4o | $2.50 | $10 |
| Gemini 2.0 Flash | $0.10 | $0.40 |
| DeepSeek V3 | $0.27 | $1.10 |

*Prices as of late 2024. Check [openrouter.ai/models](https://openrouter.ai/models) for current rates.*

---

## Troubleshooting

### "Invalid API key"
- Ensure your OpenRouter key starts with `sk-or-v1-`
- Check that you have credits in your account

### "Model not available"
- Some models require linking your own cloud account
- Check model availability at [openrouter.ai/models](https://openrouter.ai/models)

### "Rate limited"
- OpenRouter has per-minute limits
- Linked cloud accounts may have higher limits

### Need Help?

- OpenRouter docs: [openrouter.ai/docs](https://openrouter.ai/docs)
- Synod issues: [github.com/KekwanuLabs/synod-cli/issues](https://github.com/KekwanuLabs/synod-cli/issues)
