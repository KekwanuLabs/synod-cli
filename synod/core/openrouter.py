"""LLM API client with multi-provider support."""

import httpx
import json
from typing import List, Dict, Any, Optional, AsyncIterator, Callable
from .config import get_api_key, get_provider, get_provider_config, OPENROUTER_API_URL, OPENROUTER_MODELS_URL
from .session import get_current_session, parse_openrouter_usage


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0,
    silent: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Query a single model with automatic provider detection and routing.

    This function automatically detects which provider to use for each model
    based on per-model configuration (MODEL_PROVIDER env vars) or falls back
    to global provider configuration.

    Args:
        model: Model identifier (provider-specific format)
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds
        silent: If True, suppress error messages (useful for fallback chains)

    Returns:
        Response dict with 'content' and optional 'reasoning_details', or None if failed
    """
    # Try using auto-routing from providers module
    try:
        from .providers import query_model_auto
        return await query_model_auto(model, messages, timeout)
    except Exception as e:
        if not silent:
            print(f"Error with auto-routing for {model}: {e}")
            print("Falling back to legacy OpenRouter mode...")

    # Legacy fallback: use global provider
    provider = get_provider()

    # Use provider-specific implementation
    if provider != "openrouter":
        # Import the unified provider client
        try:
            from .providers import query_model_unified, ProviderConfig, Provider

            provider_enum = Provider(provider)
            provider_config = ProviderConfig.from_env(provider_enum)

            return await query_model_unified(model, messages, provider_config, timeout)
        except Exception as e:
            if not silent:
                print(f"Error initializing provider {provider}: {e}")
                print("Falling back to OpenRouter...")
            # Fall through to OpenRouter implementation

    # Default OpenRouter implementation
    api_key = get_api_key()
    if not api_key:
        print(f"Error: API Key not found. Please run 'synod config' or set appropriate API key environment variable.")
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                OPENROUTER_API_URL,
                headers=headers,
                json=payload
            )
            response.raise_for_status()

            data = response.json()
            message = data['choices'][0]['message']

            # Track token usage in session
            usage = parse_openrouter_usage(data)
            session = get_current_session()
            session.record_api_call(
                model_id=model,
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
            )

            return {
                'content': message.get('content'),
                'reasoning_details': message.get('reasoning_details')
            }

    except Exception as e:
        if not silent:
            print(f"Error querying model {model}: {e}")
        return None


async def query_model_stream(
    model: str,
    messages: List[Dict[str, str]],
    chunk_callback: Optional[Callable[[str], None]] = None,
    timeout: float = 120.0,
    silent: bool = False
) -> Optional[str]:
    """
    Query a model with streaming support.

    Args:
        model: Model identifier
        messages: List of message dicts with 'role' and 'content'
        chunk_callback: Optional callback function called with each content chunk
        timeout: Request timeout in seconds
        silent: If True, suppress error messages

    Returns:
        Full response content as string, or None if failed
    """
    api_key = get_api_key()
    if not api_key:
        if not silent:
            print(f"Error: API Key not found. Please run 'synod config' or set appropriate API key environment variable.")
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
        "stream": True,  # Enable streaming
    }

    full_content = []
    total_input_tokens = 0
    total_output_tokens = 0

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                OPENROUTER_API_URL,
                headers=headers,
                json=payload
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line or line.strip() == "":
                        continue

                    # SSE format: "data: {...}"
                    if line.startswith("data: "):
                        line = line[6:]  # Remove "data: " prefix

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
                                # Call callback if provided
                                if chunk_callback:
                                    chunk_callback(content)

                        # Track usage if present (usually in final chunk)
                        if "usage" in chunk_data:
                            usage = chunk_data["usage"]
                            total_input_tokens = usage.get("prompt_tokens", 0)
                            total_output_tokens = usage.get("completion_tokens", 0)

                    except json.JSONDecodeError:
                        # Skip malformed JSON
                        continue

        # Record token usage in session
        if total_input_tokens > 0 or total_output_tokens > 0:
            session = get_current_session()
            session.record_api_call(
                model_id=model,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
            )

        return "".join(full_content)

    except Exception as e:
        if not silent:
            print(f"Error streaming from model {model}: {e}")
        return None


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]]
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple models in parallel.

    Args:
        models: List of OpenRouter model identifiers
        messages: List of message dicts to send to each model

    Returns:
        Dict mapping model identifier to response dict (or None if failed)
    """
    import asyncio

    # Create tasks for all models
    tasks = [query_model(model, messages) for model in models]

    # Wait for all to complete
    responses = await asyncio.gather(*tasks)

    # Map models to their responses
    return {model: response for model, response in zip(models, responses)}


async def query_model_list() -> List[Dict[str, Any]]:
    """
    Fetches a list of available models from the OpenRouter API.

    Returns:
        A list of dictionaries, each representing a model, or an empty list if failed.
    """
    api_key = get_api_key()
    if not api_key:
        # Don't print error here as this might be called during config setup before key is saved
        return []

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(OPENROUTER_MODELS_URL, headers=headers)
            response.raise_for_status()
            return response.json()['data']
    except Exception as e:
        print(f"Error fetching model list from OpenRouter: {e}")
        return []