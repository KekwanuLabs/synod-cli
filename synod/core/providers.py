"""Multi-provider LLM client supporting Azure, Anthropic, OpenAI, AWS Bedrock, Google Vertex AI, and OpenRouter.

This module provides a unified interface for querying different LLM providers,
allowing users to use their existing cloud credits instead of being locked into OpenRouter.
"""

import httpx
import os
import json
import asyncio
from typing import List, Dict, Any, Optional, Callable, TypeVar
from enum import Enum
from functools import wraps
from dotenv import load_dotenv

# Type variable for generic async function return type
T = TypeVar('T')


def async_retry(
    max_retries: int = 2,
    retry_delay: float = 1.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: tuple = (
        httpx.RemoteProtocolError,  # "peer closed connection without sending complete message body"
        httpx.ReadTimeout,
        httpx.ConnectTimeout,
        httpx.ConnectError,
    )
):
    """
    Decorator for async functions that adds retry logic with exponential backoff.

    This does NOT block other parallel requests - each request retries independently.

    Args:
        max_retries: Maximum number of retry attempts (default: 2)
        retry_delay: Initial delay between retries in seconds (default: 1.0)
        backoff_factor: Multiplier for delay after each retry (default: 2.0)
        retryable_exceptions: Tuple of exception types that trigger a retry
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None
            delay = retry_delay

            # Check if silent mode is enabled (look for 'silent' kwarg)
            silent = kwargs.get('silent', False)

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        # Extract model name for logging (usually first positional arg)
                        model = args[0] if args else "unknown"
                        if not silent:
                            print(f"  ↻ Retry {attempt + 1}/{max_retries} for {model}: {type(e).__name__}")
                        await asyncio.sleep(delay)
                        delay *= backoff_factor
                    else:
                        # Final attempt failed - return None (don't crash the whole debate)
                        model = args[0] if args else "unknown"
                        if not silent:
                            print(f"  ✗ All retries failed for {model}: {type(e).__name__}")
                        return None
                except Exception:
                    # Non-retryable exception, raise immediately
                    raise

            # Should not reach here, but just in case
            return None

        return wrapper
    return decorator


# Note: get_current_session is imported lazily inside functions to avoid circular import

# Load .env file to ensure environment variables are available
# Check home directory first, then fallback to local
_home_env = os.path.join(os.path.expanduser("~"), ".synod-cli", ".env")
if os.path.exists(_home_env):
    load_dotenv(_home_env)
else:
    load_dotenv()  # Fallback to local .env


class Provider(Enum):
    """Supported LLM providers."""
    OPENROUTER = "openrouter"
    AZURE_OPENAI = "azure_openai"
    AZURE_FOUNDRY = "azure_foundry"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    AWS_BEDROCK = "aws_bedrock"
    GOOGLE_VERTEX = "google_vertex"


# Provider-specific endpoints
PROVIDER_ENDPOINTS = {
    Provider.OPENROUTER: "https://openrouter.ai/api/v1/chat/completions",
    Provider.ANTHROPIC: "https://api.anthropic.com/v1/messages",
    Provider.OPENAI: "https://api.openai.com/v1/chat/completions",
    # Azure and Vertex endpoints are dynamic (user-configured)
}


# Models that are ONLY available on OpenRouter (not on other providers)
# These models will always be routed to OpenRouter regardless of user configuration
OPENROUTER_ONLY_MODELS = [
    "x-ai/grok-4.1-fast:free",
    "x-ai/grok-4.1-fast",
    "z-ai/glm-4.6",
]


# Model mappings for different providers
# Maps canonical model names to provider-specific model IDs
MODEL_MAPPINGS = {
    Provider.OPENROUTER: {
        "claude-sonnet-4.5": "anthropic/claude-sonnet-4.5",
        "claude-opus-4": "anthropic/claude-opus-4",
        "gpt-5.1": "openai/gpt-5.1",
        "gpt-4o": "openai/gpt-4o",
        "gemini-3-pro": "google/gemini-3-pro-preview",
        "grok-4.1": "x-ai/grok-4.1-fast",
        "glm-4.6": "z-ai/glm-4.6",
    },
    Provider.AZURE_OPENAI: {
        # Azure uses deployment names, which users configure
        # We'll use the canonical names as deployment names by default
        "claude-sonnet-4.5": "claude-sonnet-4-5",  # Example deployment name
        "gpt-5.1": "gpt-5-1",
        "gpt-4o": "gpt-4o",
    },
    Provider.ANTHROPIC: {
        "claude-sonnet-4.5": "claude-sonnet-4.5-20250129",
        "claude-opus-4": "claude-opus-4-20250514",
        "claude-haiku-4.5": "claude-haiku-4.5-20250403",
    },
    Provider.OPENAI: {
        "gpt-5.1": "gpt-5.1",
        "gpt-4o": "gpt-4o",
        "gpt-4-turbo": "gpt-4-turbo-preview",
    },
    Provider.AWS_BEDROCK: {
        "claude-sonnet-4.5": "anthropic.claude-sonnet-4.5-v2",
        "claude-opus-4": "anthropic.claude-opus-4-v1",
    },
    Provider.GOOGLE_VERTEX: {
        "gemini-3-pro": "gemini-3-pro-preview",
        "gemini-2-flash": "gemini-2-flash-preview",
    },
}


# Recommended model configurations for each provider
RECOMMENDED_BISHOPS = {
    Provider.OPENROUTER: [
        "anthropic/claude-sonnet-4.5",
        "openai/gpt-5.1",
        "x-ai/grok-4.1-fast",
        "google/gemini-3-pro-preview",
    ],
    Provider.AZURE_OPENAI: [
        "gpt-5.1",
        "gpt-4o",
        "claude-sonnet-4.5",  # If available in Azure
    ],
    Provider.AZURE_FOUNDRY: [
        "gpt-5.1-chat",
        "claude-sonnet-4-5",
        "DeepSeek-V3.1",
        "Meta-Llama-3.1-405B-Instruct",
    ],
    Provider.ANTHROPIC: [
        "claude-sonnet-4.5-20250129",
        "claude-opus-4-20250514",
        "claude-haiku-4.5-20250403",
    ],
    Provider.OPENAI: [
        "gpt-5.1",
        "gpt-4o",
        "gpt-4-turbo-preview",
    ],
    Provider.AWS_BEDROCK: [
        "anthropic.claude-sonnet-4.5-v2",
        "anthropic.claude-opus-4-v1",
    ],
    Provider.GOOGLE_VERTEX: [
        "gemini-3-pro-preview",
        "gemini-2-flash-preview",
    ],
}


class ProviderConfig:
    """Configuration for a specific provider."""

    def __init__(
        self,
        provider: Provider,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        **kwargs
    ):
        self.provider = provider
        self.api_key = api_key
        self.endpoint = endpoint or PROVIDER_ENDPOINTS.get(provider)
        self.extra_config = kwargs

    @classmethod
    def from_env(cls, provider: Provider) -> "ProviderConfig":
        """Load provider configuration from environment variables."""
        if provider == Provider.OPENROUTER:
            return cls(
                provider=provider,
                api_key=os.getenv("OPENROUTER_API_KEY"),
            )

        elif provider == Provider.AZURE_OPENAI:
            endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            api_key = os.getenv("AZURE_OPENAI_API_KEY")
            api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-01-preview")
            return cls(
                provider=provider,
                api_key=api_key,
                endpoint=endpoint,
                api_version=api_version,
            )

        elif provider == Provider.AZURE_FOUNDRY:
            endpoint = os.getenv("AZURE_FOUNDRY_ENDPOINT")
            api_key = os.getenv("AZURE_FOUNDRY_API_KEY")
            api_version = os.getenv("AZURE_FOUNDRY_API_VERSION", "2024-05-01-preview")
            return cls(
                provider=provider,
                api_key=api_key,
                endpoint=endpoint,
                api_version=api_version,
            )

        elif provider == Provider.ANTHROPIC:
            return cls(
                provider=provider,
                api_key=os.getenv("ANTHROPIC_API_KEY"),
            )

        elif provider == Provider.OPENAI:
            return cls(
                provider=provider,
                api_key=os.getenv("OPENAI_API_KEY"),
            )

        elif provider == Provider.AWS_BEDROCK:
            return cls(
                provider=provider,
                region=os.getenv("AWS_REGION", "us-east-1"),
                access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            )

        elif provider == Provider.GOOGLE_VERTEX:
            return cls(
                provider=provider,
                project_id=os.getenv("GOOGLE_CLOUD_PROJECT"),
                region=os.getenv("GOOGLE_CLOUD_REGION", "us-central1"),
            )

        return cls(provider=provider)


def get_provider_for_model(model: str) -> str:
    """
    Get the provider for a specific model.

    Checks for per-model provider configuration first, then falls back to global provider.
    Note: Some models (Grok, GLM) are only available on OpenRouter and will always use it.

    Args:
        model: Model identifier (e.g., "anthropic/claude-sonnet-4.5")

    Returns:
        Provider name (e.g., "azure_foundry", "openrouter")
    """
    # Enforce OpenRouter for models that are only available there
    if model in OPENROUTER_ONLY_MODELS:
        return "openrouter"

    # Convert model ID to env var format
    # anthropic/claude-sonnet-4.5 -> ANTHROPIC_CLAUDE_SONNET_4_5_PROVIDER
    model_key = model.replace('/', '_').replace('-', '_').replace('.', '_').upper()
    env_key = f"{model_key}_PROVIDER"

    # Check for per-model provider
    per_model_provider = os.getenv(env_key)
    if per_model_provider:
        return per_model_provider.lower()

    # Fall back to global provider
    from .config import get_provider
    return get_provider()


async def query_model_unified(
    model: str,
    messages: List[Dict[str, str]],
    provider_config: ProviderConfig,
    timeout: float = 120.0
) -> Optional[Dict[str, Any]]:
    """
    Query a model using the specified provider.

    Args:
        model: Model identifier (provider-specific format)
        messages: List of message dicts with 'role' and 'content'
        provider_config: Configuration for the provider
        timeout: Request timeout in seconds

    Returns:
        Response dict with 'content' and optional 'reasoning_details', or None if failed
    """
    provider = provider_config.provider

    if provider == Provider.OPENROUTER:
        return await _query_openrouter(model, messages, provider_config, timeout)

    elif provider == Provider.AZURE_OPENAI:
        return await _query_azure_openai(model, messages, provider_config, timeout)

    elif provider == Provider.AZURE_FOUNDRY:
        return await _query_azure_foundry(model, messages, provider_config, timeout)

    elif provider == Provider.ANTHROPIC:
        return await _query_anthropic(model, messages, provider_config, timeout)

    elif provider == Provider.OPENAI:
        return await _query_openai(model, messages, provider_config, timeout)

    elif provider == Provider.AWS_BEDROCK:
        return await _query_bedrock(model, messages, provider_config, timeout)

    elif provider == Provider.GOOGLE_VERTEX:
        return await _query_vertex(model, messages, provider_config, timeout)

    else:
        print(f"Error: Unsupported provider {provider}")
        return None


@async_retry(max_retries=2, retry_delay=1.0)
async def _query_openrouter(
    model: str,
    messages: List[Dict[str, str]],
    config: ProviderConfig,
    timeout: float
) -> Optional[Dict[str, Any]]:
    """Query OpenRouter API with automatic retry on transient failures."""
    if not config.api_key:
        print("Error: OpenRouter API key not found")
        return None

    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(config.endpoint, headers=headers, json=payload)
            response.raise_for_status()

            data = response.json()
            message = data['choices'][0]['message']

            # Track usage
            usage = data.get('usage', {})
            from .session import get_current_session
            session = get_current_session()
            session.record_api_call(
                model_id=model,
                provider=config.provider, # Added provider
                input_tokens=usage.get('prompt_tokens', 0),
                output_tokens=usage.get('completion_tokens', 0),
            )

            return {
                'content': message.get('content'),
                'reasoning_details': message.get('reasoning_details')
            }

    except Exception as e:
        print(f"Error querying OpenRouter model {model}: {e}")
        return None


async def _query_azure_openai(
    model: str,
    messages: List[Dict[str, str]],
    config: ProviderConfig,
    timeout: float
) -> Optional[Dict[str, Any]]:
    """Query Azure OpenAI API."""
    if not config.api_key or not config.endpoint:
        print("Error: Azure OpenAI configuration incomplete (need endpoint and API key)")
        return None

    # Map canonical model IDs to Azure deployment names
    # Based on user's confirmed Azure setup
    deployment_mapping = {
        "openai/gpt-5.1": "gpt-5.1",
        "openai/gpt-5.1-chat": "gpt-5.1-chat",
        "gpt-5.1": "gpt-5.1",
        "gpt-5.1-chat": "gpt-5.1-chat",
        "openai/gpt-4o": "gpt-4o",
        "gpt-4o": "gpt-4o",
    }

    # Use mapping or fallback to sanitized model ID
    deployment_name = deployment_mapping.get(model, model.replace("/", "-").replace(".", "-"))

    # Azure uses deployment names in the URL
    api_version = config.extra_config.get('api_version', '2024-12-01-preview')
    url = f"{config.endpoint}/openai/deployments/{deployment_name}/chat/completions?api-version={api_version}"

    headers = {
        "api-key": config.api_key,
        "Content-Type": "application/json",
    }

    payload = {
        "messages": messages,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()

            data = response.json()
            message = data['choices'][0]['message']

            # Track usage
            usage = data.get('usage', {})
            from .session import get_current_session
            session = get_current_session()
            session.record_api_call(
                model_id=model,
                provider=config.provider, # Added provider
                input_tokens=usage.get('prompt_tokens', 0),
                output_tokens=usage.get('completion_tokens', 0),
            )

            return {
                'content': message.get('content'),
            }

    except Exception as e:
        print(f"Error querying Azure OpenAI model {model} (deployment: {deployment_name}): {e}")
        return None


async def _query_azure_foundry(
    model: str,
    messages: List[Dict[str, str]],
    config: ProviderConfig,
    timeout: float
) -> Optional[Dict[str, Any]]:
    """
    Query Azure AI Foundry API.

    Azure AI Foundry uses different endpoint formats for different providers:
    - Anthropic/Claude: /anthropic/v1/messages (Anthropic Messages API)
    - OpenAI/GPT: /openai/deployments/{name}/chat/completions (Azure OpenAI API)
    - Others (DeepSeek, Llama): /models/chat/completions (Unified API)
    """
    if not config.api_key or not config.endpoint:
        print("Error: Azure AI Foundry configuration incomplete (need endpoint and API key)")
        return None

    # Extract base resource URL (remove any path after the domain)
    # Example: https://synod2-resource.services.ai.azure.com/api/projects/synod2
    #       -> https://synod2-resource.services.ai.azure.com
    from urllib.parse import urlparse
    parsed = urlparse(config.endpoint)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    # Map standard model IDs to Azure deployment names
    # Standard format: provider/model-name -> Azure deployment name
    model_mapping = {
        # Anthropic models (matching user's provided deployment names)
        'anthropic/claude-sonnet-4.5': 'claude-sonnet-4-5',
        'anthropic/claude-opus-4.5': 'claude-opus-4-5',
        'anthropic/claude-haiku-4.5': 'claude-haiku-4-5',

        # OpenAI models (matching user's provided deployment name)
        'openai/gpt-5.1-chat': 'gpt-5.1-chat',
        'openai/gpt-5.1': 'gpt-5.1', # Assuming 'gpt-5.1' is a distinct deployment name if used

        # DeepSeek models (matching user's provided deployment name)
        'deepseek/deepseek-v3.1': 'DeepSeek-V3.1',

        # Google models (if available on Azure)
        'google/gemini-3-pro-preview': 'gemini-3-pro-preview',
        'google/gemini-2.5-flash': 'gemini-2-5-flash',
    }

    deployment_name = model_mapping.get(model, model)
    if '/' in deployment_name:
        deployment_name = deployment_name.split('/')[-1]

    # Determine provider from model ID
    provider = model.split('/')[0] if '/' in model else 'unknown'

    headers = {
        "api-key": config.api_key,
        "Content-Type": "application/json",
    }

    try:
        # Route to appropriate API based on provider
        if provider == 'anthropic':
            # Anthropic models use native Messages API
            url = f"{base_url}/anthropic/v1/messages"

            # Anthropic uses x-api-key header (not api-key)
            headers["x-api-key"] = headers.pop("api-key")
            headers["anthropic-version"] = "2023-06-01"

            # Convert chat messages to Anthropic format
            anthropic_messages = []
            system_message = None
            for msg in messages:
                if msg['role'] == 'system':
                    system_message = msg['content']
                else:
                    anthropic_messages.append({
                        'role': msg['role'],
                        'content': msg['content']
                    })

            payload = {
                "model": deployment_name,
                "messages": anthropic_messages,
                "max_tokens": 4096,
            }
            if system_message:
                payload["system"] = system_message

            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

                # Anthropic response format
                content = data['content'][0]['text'] if data['content'] else ''
                usage = data.get('usage', {})

                from .session import get_current_session
                session = get_current_session()
                session.record_api_call(
                    model_id=model,
                    provider=config.provider, # Added provider
                    input_tokens=usage.get('input_tokens', 0),
                    output_tokens=usage.get('output_tokens', 0),
                )

                return {'content': content}

        elif provider == 'openai':
            # OpenAI models use Azure OpenAI API
            api_version = config.extra_config.get('api_version', '2025-11-13') # Updated API version
            url = f"{base_url}/openai/deployments/{deployment_name}/chat/completions?api-version={api_version}"

            payload = {
                "messages": messages,
            }

            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

                message = data['choices'][0]['message']
                usage = data.get('usage', {})

                from .session import get_current_session
                session = get_current_session()
                session.record_api_call(
                    model_id=model,
                    provider=config.provider, # Added provider
                    input_tokens=usage.get('prompt_tokens', 0),
                    output_tokens=usage.get('completion_tokens', 0),
                )

                return {'content': message.get('content')}

        else:
            # Other models (DeepSeek, Llama, etc.) use unified Models API
            api_version = config.extra_config.get('api_version', '2024-05-01-preview') # DeepSeek's API version
            url = f"{base_url}/models/chat/completions?api-version={api_version}"

            payload = {
                "model": deployment_name,
                "messages": messages,
            }

            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

                message = data['choices'][0]['message']
                usage = data.get('usage', {})

                from .session import get_current_session
                session = get_current_session()
                session.record_api_call(
                    model_id=model,
                    provider=config.provider, # Added provider
                    input_tokens=usage.get('prompt_tokens', 0),
                    output_tokens=usage.get('completion_tokens', 0),
                )

                return {'content': message.get('content')}

    except Exception as e:
        print(f"Error querying Azure AI Foundry model {model}: {e}")
        return None


async def _query_anthropic(
    model: str,
    messages: List[Dict[str, str]],
    config: ProviderConfig,
    timeout: float
) -> Optional[Dict[str, Any]]:
    """Query Anthropic API directly."""
    if not config.api_key:
        print("Error: Anthropic API key not found")
        return None

    headers = {
        "x-api-key": config.api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }

    # Convert OpenAI-style messages to Anthropic format
    system_message = None
    anthropic_messages = []

    for msg in messages:
        if msg['role'] == 'system':
            system_message = msg['content']
        else:
            anthropic_messages.append({
                "role": msg['role'],
                "content": msg['content']
            })

    payload = {
        "model": model,
        "messages": anthropic_messages,
        "max_tokens": 4096,
    }

    if system_message:
        payload["system"] = system_message

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(config.endpoint, headers=headers, json=payload)
            response.raise_for_status()

            data = response.json()
            content = data['content'][0]['text']

            # Track usage
            usage = data.get('usage', {})
            from .session import get_current_session
            session = get_current_session()
            session.record_api_call(
                model_id=model,
                provider=config.provider, # Added provider
                input_tokens=usage.get('input_tokens', 0),
                output_tokens=usage.get('output_tokens', 0),
            )

            return {
                'content': content,
            }

    except Exception as e:
        print(f"Error querying Anthropic model {model}: {e}")
        return None


async def _query_openai(
    model: str,
    messages: List[Dict[str, str]],
    config: ProviderConfig,
    timeout: float
) -> Optional[Dict[str, Any]]:
    """Query OpenAI API directly."""
    if not config.api_key:
        print("Error: OpenAI API key not found")
        return None

    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(config.endpoint, headers=headers, json=payload)
            response.raise_for_status()

            data = response.json()
            message = data['choices'][0]['message']

            # Track usage
            usage = data.get('usage', {})
            from .session import get_current_session
            session = get_current_session()
            session.record_api_call(
                model_id=model,
                provider=config.provider, # Added provider
                input_tokens=usage.get('prompt_tokens', 0),
                output_tokens=usage.get('completion_tokens', 0),
            )

            return {
                'content': message.get('content'),
                'reasoning_details': message.get('reasoning_content')  # For o1/o3 models
            }

    except Exception as e:
        print(f"Error querying OpenAI model {model}: {e}")
        return None


async def _query_bedrock(
    model: str,
    messages: List[Dict[str, str]],
    config: ProviderConfig,
    timeout: float
) -> Optional[Dict[str, Any]]:
    """Query AWS Bedrock API."""
    print("Error: AWS Bedrock support coming soon. Please use Azure OpenAI or Anthropic direct for now.")
    return None


async def _query_vertex(
    model: str,
    messages: List[Dict[str, str]],
    config: ProviderConfig,
    timeout: float
) -> Optional[Dict[str, Any]]:
    """Query Google Vertex AI API."""
    print("Error: Google Vertex AI support coming soon. Please use OpenRouter for Gemini models for now.")
    return None


async def query_model_auto(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0
) -> Optional[Dict[str, Any]]:
    """
    Query a model with automatic provider detection and routing.

    This function automatically:
    1. Detects which provider to use for the model
    2. Loads the appropriate credentials
    3. Routes the request to that provider

    Args:
        model: Model identifier (e.g., "anthropic/claude-sonnet-4.5")
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds

    Returns:
        Response dict with 'content' and optional 'reasoning_details', or None if failed
    """
    # Get provider for this specific model
    provider_name = get_provider_for_model(model)

    # Convert provider name to enum
    try:
        provider_enum = Provider(provider_name)
    except ValueError:
        print(f"Error: Unknown provider '{provider_name}' for model {model}")
        return None

    # Load provider configuration
    provider_config = ProviderConfig.from_env(provider_enum)

    # Query the model
    return await query_model_unified(model, messages, provider_config, timeout)


async def query_model_stream_auto(
    model: str,
    messages: List[Dict[str, str]],
    chunk_callback: Optional[callable] = None,
    timeout: float = 120.0,
    silent: bool = False
) -> Optional[str]:
    """
    Query a model with streaming and automatic provider detection.

    This function automatically routes streaming requests to the correct provider.
    Currently supports streaming for OpenRouter and Azure Foundry (Anthropic only).

    Args:
        model: Model identifier (e.g., "anthropic/claude-sonnet-4.5")
        messages: List of message dicts with 'role' and 'content'
        chunk_callback: Optional callback function called with each content chunk
        timeout: Request timeout in seconds
        silent: If True, suppress error messages

    Returns:
        Full response content as string, or None if failed
    """
    # Get provider for this specific model
    provider_name = get_provider_for_model(model)

    # Convert provider name to enum
    try:
        provider_enum = Provider(provider_name)
    except ValueError:
        if not silent:
            print(f"Error: Unknown provider '{provider_name}' for model {model}")
        return None

    # Load provider configuration
    provider_config = ProviderConfig.from_env(provider_enum)

    # Route to appropriate streaming implementation
    if provider_enum == Provider.OPENROUTER:
        return await _stream_openrouter(model, messages, provider_config, chunk_callback, timeout, silent)
    elif provider_enum == Provider.AZURE_FOUNDRY:
        return await _stream_azure_foundry(model, messages, provider_config, chunk_callback, timeout, silent)
    else:
        if not silent:
            print(f"Error: Streaming not yet supported for provider {provider_name}. Falling back to non-streaming.")
        # Fallback: use non-streaming and call callback once with full response
        result = await query_model_unified(model, messages, provider_config, timeout)
        if result and chunk_callback:
            chunk_callback(result.get('content', ''))
        return result.get('content') if result else None


@async_retry(max_retries=2, retry_delay=1.0)
async def _stream_openrouter(
    model: str,
    messages: List[Dict[str, str]],
    config: ProviderConfig,
    chunk_callback: Optional[callable],
    timeout: float,
    silent: bool
) -> Optional[str]:
    """Stream from OpenRouter API with automatic retry on transient failures."""
    if not config.api_key:
        if not silent:
            print("Error: OpenRouter API key not found")
        return None

    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }

    full_content = []
    total_input_tokens = 0
    total_output_tokens = 0

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                config.endpoint,
                headers=headers,
                json=payload
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line or line.strip() == "":
                        continue

                    # SSE format: "data: {...}"
                    if line.startswith("data: "):
                        line = line[6:]

                    # Skip [DONE] marker
                    if line.strip() == "[DONE]":
                        break

                    try:
                        chunk_data = json.loads(line)

                        # Extract content delta
                        if "choices" in chunk_data and len(chunk_data["choices"]) > 0:
                            delta = chunk_data["choices"][0].get("delta", {})
                            content = delta.get("content", "")

                            if content:
                                full_content.append(content)
                                if chunk_callback:
                                    chunk_callback(content)

                        # Track usage if present
                        if "usage" in chunk_data:
                            usage = chunk_data["usage"]
                            total_input_tokens = usage.get("prompt_tokens", 0)
                            total_output_tokens = usage.get("completion_tokens", 0)

                    except json.JSONDecodeError:
                        # Skip malformed JSON lines
                        continue

                # Record usage outside the loop once we have the final tokens
                if total_input_tokens > 0 or total_output_tokens > 0:
                    from .session import get_current_session
                    session = get_current_session()
                    session.record_api_call(
                        model_id=model,
                        provider=config.provider, # Added provider
                        input_tokens=total_input_tokens,
                        output_tokens=total_output_tokens,
                    )

        return "".join(full_content)

    except httpx.RemoteProtocolError as e:
        if not silent:
            print(f"Error streaming from OpenRouter model {model}: Connection closed unexpectedly")
            print(f"  Details: {type(e).__name__}: {e}")
        raise  # Let retry decorator handle this
    except httpx.TimeoutException as e:
        if not silent:
            print(f"Error streaming from OpenRouter model {model}: Request timed out")
            print(f"  Details: {type(e).__name__}: {e}")
        raise  # Let retry decorator handle this
    except httpx.HTTPStatusError as e:
        if not silent:
            print(f"Error streaming from OpenRouter model {model}: HTTP {e.response.status_code}")
            try:
                error_body = e.response.text[:500]
                print(f"  Response: {error_body}")
            except:
                pass
        return None  # Don't retry HTTP errors (4xx, 5xx) - they're not transient
    except Exception as e:
        if not silent:
            print(f"Error streaming from OpenRouter model {model}: {type(e).__name__}: {e}")
        return None


@async_retry(max_retries=2, retry_delay=1.0)
async def _stream_azure_foundry(
    model: str,
    messages: List[Dict[str, str]],
    config: ProviderConfig,
    chunk_callback: Optional[callable],
    timeout: float,
    silent: bool
) -> Optional[str]:
    """Stream from Azure AI Foundry API with automatic retry on transient failures."""
    if not config.api_key or not config.endpoint:
        if not silent:
            print("Error: Azure AI Foundry configuration incomplete")
        return None

    # Extract base URL
    from urllib.parse import urlparse
    parsed = urlparse(config.endpoint)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    # Map model to deployment name
    model_mapping = {
        # Anthropic models
        'anthropic/claude-sonnet-4.5': 'claude-sonnet-4-5',
        'anthropic/claude-opus-4.5': 'claude-opus-4-5',
        'anthropic/claude-opus-4': 'claude-opus-4-5',
        'anthropic/claude-haiku-4.5': 'claude-haiku-4-5',
        # OpenAI models
        'openai/gpt-5.1-chat': 'gpt-5.1-chat',
        'openai/gpt-5.1': 'gpt-5.1',
        'openai/gpt-4o': 'gpt-4o',
        'openai/gpt-4-turbo': 'gpt-4-turbo',
    }

    deployment_name = model_mapping.get(model)
    if not deployment_name:
        # Fallback: extract model name from model ID
        deployment_name = model.split('/')[-1] if '/' in model else model

    provider = model.split('/')[0] if '/' in model else 'unknown'

    full_content = []
    total_input_tokens = 0
    total_output_tokens = 0

    try:
        # Route to appropriate streaming API based on provider
        if provider == 'anthropic':
            # Anthropic models use native Messages API with streaming
            url = f"{base_url}/anthropic/v1/messages"

            headers = {
                "x-api-key": config.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }

            # Convert messages to Anthropic format
            anthropic_messages = []
            system_message = None
            for msg in messages:
                if msg['role'] == 'system':
                    system_message = msg['content']
                else:
                    anthropic_messages.append({
                        'role': msg['role'],
                        'content': msg['content']
                    })

            payload = {
                "model": deployment_name,
                "messages": anthropic_messages,
                "max_tokens": 4096,
                "stream": True,
            }
            if system_message:
                payload["system"] = system_message

            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if not line or line.strip() == "":
                            continue

                        if line.startswith("data: "):
                            line = line[6:]

                        if line.strip() == "[DONE]":
                            break

                        try:
                            chunk_data = json.loads(line)

                            # Anthropic streaming format
                            if chunk_data.get("type") == "content_block_delta":
                                delta = chunk_data.get("delta", {})
                                content = delta.get("text", "")

                                if content:
                                    full_content.append(content)
                                    if chunk_callback:
                                        chunk_callback(content)

                            # Track usage from message_delta event
                            elif chunk_data.get("type") == "message_delta":
                                usage = chunk_data.get("usage", {})
                                total_output_tokens = usage.get("output_tokens", 0)

                            # Get input tokens from message_start event
                            elif chunk_data.get("type") == "message_start":
                                usage = chunk_data.get("message", {}).get("usage", {})
                                total_input_tokens = usage.get("input_tokens", 0)

                        except json.JSONDecodeError:
                            continue

        elif provider == 'openai':
            # OpenAI models use Azure OpenAI API with streaming
            api_version = config.extra_config.get('api_version', '2024-10-21')
            url = f"{base_url}/openai/deployments/{deployment_name}/chat/completions?api-version={api_version}"

            headers = {
                "api-key": config.api_key,
                "Content-Type": "application/json",
            }

            payload = {
                "messages": messages,
                "stream": True,
            }

            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if not line or line.strip() == "":
                            continue

                        if line.startswith("data: "):
                            line = line[6:]

                        if line.strip() == "[DONE]":
                            break

                        try:
                            chunk_data = json.loads(line)

                            # OpenAI streaming format
                            if "choices" in chunk_data and len(chunk_data["choices"]) > 0:
                                delta = chunk_data["choices"][0].get("delta", {})
                                content = delta.get("content", "")

                                if content:
                                    full_content.append(content)
                                    if chunk_callback:
                                        chunk_callback(content)

                            # Track usage if present
                            if "usage" in chunk_data:
                                usage = chunk_data["usage"]
                                total_input_tokens = usage.get("prompt_tokens", 0)
                                total_output_tokens = usage.get("completion_tokens", 0)

                        except json.JSONDecodeError:
                            continue

        else:
            # Other models (DeepSeek, Llama, etc.) use unified Models API with streaming
            api_version = config.extra_config.get('api_version', '2024-05-01-preview')
            url = f"{base_url}/models/chat/completions?api-version={api_version}"

            headers = {
                "api-key": config.api_key,
                "Content-Type": "application/json",
            }

            payload = {
                "model": deployment_name,
                "messages": messages,
                "stream": True,
            }

            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if not line or line.strip() == "":
                            continue

                        if line.startswith("data: "):
                            line = line[6:]

                        if line.strip() == "[DONE]":
                            break

                        try:
                            chunk_data = json.loads(line)

                            # OpenAI-compatible streaming format (used by DeepSeek, etc.)
                            if "choices" in chunk_data and len(chunk_data["choices"]) > 0:
                                delta = chunk_data["choices"][0].get("delta", {})
                                content = delta.get("content", "")

                                if content:
                                    full_content.append(content)
                                    if chunk_callback:
                                        chunk_callback(content)

                            # Track usage if present
                            if "usage" in chunk_data:
                                usage = chunk_data["usage"]
                                total_input_tokens = usage.get("prompt_tokens", 0)
                                total_output_tokens = usage.get("completion_tokens", 0)

                        except json.JSONDecodeError:
                            continue

        # Record usage
        if total_input_tokens > 0 or total_output_tokens > 0:
            from .session import get_current_session
            session = get_current_session()
            session.record_api_call(
                model_id=model,
                provider=config.provider,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
            )

        return "".join(full_content)

    except httpx.HTTPStatusError as e:
        if not silent:
            # Show more detailed error info for debugging
            error_body = ""
            try:
                error_body = e.response.text[:500]  # First 500 chars of error response
            except:
                pass
            print(f"Error streaming from Azure Foundry model {model}: HTTP {e.response.status_code}")
            if error_body:
                print(f"  Response: {error_body}")
        return None
    except Exception as e:
        if not silent:
            print(f"Error streaming from Azure Foundry model {model}: {type(e).__name__}: {e}")
        return None


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]],
    provider_config: ProviderConfig = None
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple models in parallel with automatic provider routing.

    Args:
        models: List of model identifiers
        messages: List of message dicts to send to each model
        provider_config: (Optional) Provider configuration (deprecated - use auto-routing)

    Returns:
        Dict mapping model identifier to response dict (or None if failed)
    """
    import asyncio

    if provider_config:
        # Legacy mode: use same provider for all models
        tasks = [query_model_unified(model, messages, provider_config) for model in models]
    else:
        # New mode: auto-route each model to its configured provider
        tasks = [query_model_auto(model, messages) for model in models]

    responses = await asyncio.gather(*tasks)

    return {model: response for model, response in zip(models, responses)}
