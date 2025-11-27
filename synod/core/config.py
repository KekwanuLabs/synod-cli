"""Configuration for the LLM Council."""

import os
import json
from dotenv import load_dotenv
from typing import Optional
from pathlib import Path

# Load environment from user home directory first, then local
_home_env = os.path.join(os.path.expanduser("~"), ".synod-cli", ".env")
if os.path.exists(_home_env):
    load_dotenv(_home_env)
else:
    load_dotenv()  # Fallback to local .env

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"

# Data directory for conversation storage
DATA_DIR = "data/conversations"

# Config paths - all in user home directory for cross-platform persistence
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".synod-cli")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
CONFIG_YAML = os.path.join(CONFIG_DIR, "config.yaml")  # Main config file
ENV_FILE = os.path.join(CONFIG_DIR, ".env")  # Environment variables


def get_provider() -> str:
    """
    Get the configured LLM provider.

    Returns:
        Provider name (openrouter, azure_openai, anthropic, openai, etc.)
    """
    # 1. Check environment variable
    provider = os.getenv("SYNOD_PROVIDER")
    if provider:
        return provider.lower()

    # 2. Check config file
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                provider = config.get("provider", "openrouter")
                return provider.lower()
        except Exception:
            pass

    # 3. Default to OpenRouter
    return "openrouter"


def get_api_key() -> str | None:
    """
    Retrieves the API key for the configured provider.
    Checks environment variables first, then config file.
    """
    provider = get_provider()

    # Provider-specific environment variable names
    env_keys = {
        "openrouter": "OPENROUTER_API_KEY",
        "azure_openai": "AZURE_OPENAI_API_KEY",
        "azure_foundry": "AZURE_FOUNDRY_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
    }

    # 1. Check provider-specific environment variable
    env_key = env_keys.get(provider, "OPENROUTER_API_KEY")
    api_key = os.getenv(env_key)
    if api_key:
        return api_key

    # 2. Check local config file
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                return config.get("api_key")
        except Exception:
            pass

    return None


def get_provider_config() -> dict:
    """
    Get full provider configuration including API keys, endpoints, etc.

    Returns:
        Dictionary with provider configuration
    """
    provider = get_provider()
    config = {
        "provider": provider,
        "api_key": get_api_key(),
    }

    if provider == "azure_openai":
        config["endpoint"] = os.getenv("AZURE_OPENAI_ENDPOINT")
        config["api_version"] = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-01-preview")

    elif provider == "azure_foundry":
        config["endpoint"] = os.getenv("AZURE_FOUNDRY_ENDPOINT")
        config["api_version"] = os.getenv("AZURE_FOUNDRY_API_VERSION", "2024-05-01-preview")

    elif provider == "aws_bedrock":
        config["region"] = os.getenv("AWS_REGION", "us-east-1")
        config["access_key_id"] = os.getenv("AWS_ACCESS_KEY_ID")
        config["secret_access_key"] = os.getenv("AWS_SECRET_ACCESS_KEY")

    elif provider == "google_vertex":
        config["project_id"] = os.getenv("GOOGLE_CLOUD_PROJECT")
        config["region"] = os.getenv("GOOGLE_CLOUD_REGION", "us-central1")

    # Check config file for additional settings
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                file_config = json.load(f)
                # Merge file config into provider config
                for key in ["endpoint", "api_version", "region", "project_id"]:
                    if key in file_config and key not in config:
                        config[key] = file_config[key]
        except Exception:
            pass

    return config