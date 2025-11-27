"""Model availability registry - maps models to available providers.

This module defines which models are available on which providers,
enabling smart routing and credential collection during onboarding.
"""

from typing import Dict, List, Set
from enum import Enum


class ModelProvider(Enum):
    """Available LLM providers."""
    OPENROUTER = "openrouter"
    AZURE_OPENAI = "azure_openai"
    AZURE_FOUNDRY = "azure_foundry"
    AWS_BEDROCK = "aws_bedrock"
    GOOGLE_VERTEX = "google_vertex"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    XAI = "xai"
    DEEPSEEK = "deepseek"


# Model availability matrix
# Format: model_pattern -> set of providers that have it
MODEL_AVAILABILITY: Dict[str, Set[ModelProvider]] = {
    # Claude models
    "claude-sonnet-4.5": {
        ModelProvider.AZURE_FOUNDRY,
        ModelProvider.AWS_BEDROCK,
        ModelProvider.ANTHROPIC,
        ModelProvider.OPENROUTER,
    },
    "claude-opus-4.5": {
        ModelProvider.AZURE_FOUNDRY,
        ModelProvider.AWS_BEDROCK,
        ModelProvider.ANTHROPIC,
        ModelProvider.OPENROUTER,
    },
    "claude-haiku-4.5": {
        ModelProvider.AZURE_FOUNDRY,
        ModelProvider.AWS_BEDROCK,
        ModelProvider.ANTHROPIC,
        ModelProvider.OPENROUTER,
    },

    # GPT models
    "gpt-5.1": {
        ModelProvider.AZURE_OPENAI,
        ModelProvider.AZURE_FOUNDRY,
        ModelProvider.OPENAI,
        ModelProvider.OPENROUTER,
    },
    "gpt-5": {
        ModelProvider.AZURE_OPENAI,
        ModelProvider.AZURE_FOUNDRY,
        ModelProvider.OPENAI,
        ModelProvider.OPENROUTER,
    },
    "gpt-4o": {
        ModelProvider.AZURE_OPENAI,
        ModelProvider.AZURE_FOUNDRY,
        ModelProvider.OPENAI,
        ModelProvider.OPENROUTER,
    },
    "gpt-4": {
        ModelProvider.AZURE_OPENAI,
        ModelProvider.AZURE_FOUNDRY,
        ModelProvider.OPENAI,
        ModelProvider.OPENROUTER,
    },

    # Gemini models
    "gemini-3-pro": {
        ModelProvider.GOOGLE_VERTEX,
        ModelProvider.OPENROUTER,
    },
    "gemini-2-flash": {
        ModelProvider.GOOGLE_VERTEX,
        ModelProvider.OPENROUTER,
    },

    # Grok models (xAI)
    "x-ai/grok-4.1-fast:free": {
        ModelProvider.OPENROUTER,  # Only via OpenRouter (free tier!)
    },

    # DeepSeek models
    "deepseek-v3.1": {
        ModelProvider.AZURE_FOUNDRY,
        ModelProvider.DEEPSEEK,
        ModelProvider.OPENROUTER,
    },

    # GLM models (Zhipu AI)
    "glm-4.6": {
        ModelProvider.OPENROUTER,
    },
}


def get_model_key(model_id: str) -> str:
    """
    Extract model key from full model ID.

    Examples:
        anthropic/claude-sonnet-4.5 -> claude-sonnet-4.5
        openai/gpt-5.1 -> gpt-5.1
        gpt-5.1-chat -> gpt-5.1
    """
    # Remove provider prefix
    if '/' in model_id:
        model_id = model_id.split('/')[-1]

    # Normalize common variations
    model_id = model_id.lower()

    # Map specific variants to base keys
    mappings = {
        'claude-sonnet-4-5': 'claude-sonnet-4.5',
        'claude-opus-4-5': 'claude-opus-4.5',
        'claude-haiku-4-5': 'claude-haiku-4.5',
        'deepseek-chat-v3.1': 'deepseek-v3.1', # Explicitly normalize OpenRouter's deepseek model
        'gemini-3-pro-preview': 'gemini-3-pro',
        'gemini-2-flash-preview': 'gemini-2-flash',
    }

    if model_id in mappings:
        return mappings[model_id]

    # Try to extract base version for unknown models
    for key in MODEL_AVAILABILITY.keys():
        if key in model_id:
            return key

    return model_id


def get_available_providers(model_id: str) -> Set[ModelProvider]:
    """Get set of providers that have this model."""
    model_key = get_model_key(model_id)
    return MODEL_AVAILABILITY.get(model_key, {ModelProvider.OPENROUTER})


def get_required_providers(model_ids: List[str]) -> Set[ModelProvider]:
    """
    Determine minimum set of providers needed to access all models.

    Smart algorithm:
    1. If OpenRouter can serve all models, suggest OpenRouter only
    2. Otherwise, find optimal combination of providers
    """
    all_providers = set()

    # Check if OpenRouter has everything
    openrouter_has_all = all(
        ModelProvider.OPENROUTER in get_available_providers(model_id)
        for model_id in model_ids
    )

    if openrouter_has_all:
        return {ModelProvider.OPENROUTER}

    # Find models that require specific providers
    required = set()
    for model_id in model_ids:
        providers = get_available_providers(model_id)
        if len(providers) == 1:
            # Model only available on one provider
            required.update(providers)
        all_providers.update(providers)

    return required if required else all_providers


def get_all_potential_providers(model_ids: List[str]) -> Set[ModelProvider]:
    """
    Get ALL possible providers for the selected models.
    Used for 'Custom' setup where user wants to see all options.
    """
    all_providers = set()
    for model_id in model_ids:
        providers = get_available_providers(model_id)
        all_providers.update(providers)
    return all_providers


def suggest_optimal_provider(model_id: str, configured_providers: Set[ModelProvider]) -> ModelProvider:
    """
    Suggest best provider for a model based on what's already configured.

    Priority:
    1. Providers already configured (reuse credentials)
    2. OpenRouter (easiest fallback)
    3. First available provider
    """
    available = get_available_providers(model_id)

    # Use already-configured provider if available
    overlap = available & configured_providers
    if overlap:
        return next(iter(overlap))

    # Prefer OpenRouter if available
    if ModelProvider.OPENROUTER in available:
        return ModelProvider.OPENROUTER

    # Return first available
    return next(iter(available))


def is_free_tier(model_id: str) -> bool:
    """Check if model has a free tier available."""
    # Grok has free tier on OpenRouter
    if 'grok' in model_id.lower():
        return True

    # Some other free tiers we know about
    free_models = [
        'grok-4.1',
        'grok-3',
    ]

    model_key = get_model_key(model_id)
    return model_key in free_models


def get_provider_display_name(provider: ModelProvider) -> str:
    """Get human-readable provider name."""
    names = {
        ModelProvider.OPENROUTER: "OpenRouter",
        ModelProvider.AZURE_OPENAI: "Azure OpenAI",
        ModelProvider.AZURE_FOUNDRY: "Azure AI Foundry",
        ModelProvider.AWS_BEDROCK: "AWS Bedrock",
        ModelProvider.GOOGLE_VERTEX: "Google Vertex AI",
        ModelProvider.ANTHROPIC: "Anthropic",
        ModelProvider.OPENAI: "OpenAI",
        ModelProvider.XAI: "xAI",
        ModelProvider.DEEPSEEK: "DeepSeek",
    }
    return names.get(provider, provider.value)
