"""Fireworks AI client wrapper for LLM calls with function calling."""

import json
import os
import time
from typing import Any

from dotenv import load_dotenv
from fireworks.client import Fireworks

from .models import FireworksAPIError

# Load environment variables
load_dotenv()

# Initialize client
_api_key = os.environ.get("FIREWORKS_API_KEY")
if not _api_key:
    raise ValueError("FIREWORKS_API_KEY environment variable is required")

client = Fireworks(api_key=_api_key)

# Default model - can be overridden via environment
MODEL = os.environ.get(
    "FIREWORKS_MODEL", 
    "accounts/fireworks/models/llama-v3p1-70b-instruct"
)

# Retry configuration
MAX_RETRIES = 2
INITIAL_BACKOFF = 1.0  # seconds
BACKOFF_MULTIPLIER = 2.0


def call_with_tools(
    messages: list[dict[str, Any]], 
    tools: list[dict[str, Any]],
    model: str | None = None,
    max_retries: int = MAX_RETRIES
) -> dict[str, Any]:
    """
    Make a Fireworks API call with tool definitions.
    
    Includes retry logic with exponential backoff for handling timeouts
    and transient API errors.
    
    Args:
        messages: List of chat messages in OpenAI format
        tools: List of tool definitions for function calling
        model: Optional model override
        max_retries: Maximum number of retry attempts (default: 2)
        
    Returns:
        Dict containing:
            - content: Text response (if any)
            - tool_calls: List of parsed tool calls (if any)
            - raw_response: The full API response object
            
    Raises:
        FireworksAPIError: If all retry attempts fail
    """
    last_error = None
    backoff = INITIAL_BACKOFF
    
    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model or MODEL,
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )
            return parse_response(response)
            
        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            
            # Check if this is a retryable error (timeout, rate limit, server error)
            is_retryable = any(keyword in error_str for keyword in [
                "timeout", "timed out", "rate limit", "429", "500", "502", "503", "504",
                "connection", "network", "temporarily unavailable"
            ])
            
            if not is_retryable or attempt >= max_retries:
                # Non-retryable error or exhausted retries
                raise FireworksAPIError(str(e), retries=attempt)
            
            # Wait before retrying with exponential backoff
            time.sleep(backoff)
            backoff *= BACKOFF_MULTIPLIER
    
    # Should not reach here, but just in case
    raise FireworksAPIError(str(last_error), retries=max_retries)


def parse_response(response) -> dict[str, Any]:
    """
    Parse the Fireworks API response and extract tool calls.
    
    Args:
        response: Raw Fireworks API response
        
    Returns:
        Dict with content, tool_calls, and raw_response
    """
    message = response.choices[0].message
    
    result = {
        "content": message.content,
        "tool_calls": [],
        "raw_response": response
    }
    
    if message.tool_calls:
        for tool_call in message.tool_calls:
            parsed_call = {
                "id": tool_call.id,
                "name": tool_call.function.name,
                "arguments": parse_tool_arguments(tool_call.function.arguments)
            }
            result["tool_calls"].append(parsed_call)
    
    return result


def parse_tool_arguments(arguments: str) -> dict[str, Any]:
    """
    Parse tool call arguments from JSON string.
    
    Args:
        arguments: JSON string of function arguments
        
    Returns:
        Parsed dictionary of arguments
        
    Raises:
        ValueError: If arguments cannot be parsed as JSON
    """
    try:
        return json.loads(arguments)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse tool arguments: {e}")
