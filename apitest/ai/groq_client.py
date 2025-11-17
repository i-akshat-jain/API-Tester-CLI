"""
Groq API client for AI test generation
"""

import time
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class GroqAPIError(Exception):
    """Base exception for Groq API errors"""
    pass


class GroqRateLimitError(GroqAPIError):
    """Exception raised when rate limit is exceeded"""
    pass


class GroqAuthenticationError(GroqAPIError):
    """Exception raised when authentication fails"""
    pass


@dataclass
class GroqResponse:
    """Response from Groq API"""
    content: str
    tokens_used: Optional[int] = None
    tokens_limit: Optional[int] = None
    model: Optional[str] = None


class GroqClient:
    """
    Client for interacting with Groq API
    
    Provides methods for generating test cases using Groq's LLM API
    with error handling, retry logic, and token usage tracking.
    """
    
    def __init__(self, api_key: str, model: str = 'llama-3-groq-70b', 
                 temperature: float = 0.7, max_tokens: int = 2000):
        """
        Initialize Groq client
        
        Args:
            api_key: Groq API key
            model: Model name (default: llama-3-groq-70b)
            temperature: Sampling temperature (0.0-2.0, default: 0.7)
            max_tokens: Maximum tokens to generate (default: 2000)
        """
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._tokens_used = 0
        self._tokens_limit = None
    
    def generate(self, prompt: str) -> str:
        """
        Generate text using Groq API
        
        Args:
            prompt: Input prompt for the model
            
        Returns:
            Generated text response
            
        Raises:
            GroqAPIError: For general API errors
            GroqRateLimitError: For rate limit errors
            GroqAuthenticationError: For authentication errors
        """
        try:
            response = self._make_request(prompt)
            return response.content
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            raise
    
    def _make_request(self, prompt: str, max_retries: int = 3) -> GroqResponse:
        """
        Make request to Groq API with retry logic
        
        Args:
            prompt: Input prompt
            max_retries: Maximum number of retry attempts
            
        Returns:
            GroqResponse object
            
        Raises:
            GroqAPIError: For API errors
            GroqRateLimitError: For rate limit errors
            GroqAuthenticationError: For authentication errors
        """
        # Import groq here to avoid import error if not installed
        try:
            from groq import Groq
        except ImportError:
            raise GroqAPIError(
                "Groq library not installed. Install it with: pip install groq"
            )
        
        client = Groq(api_key=self.api_key)
        
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens
                )
                
                # Extract response content
                content = response.choices[0].message.content
                
                # Track token usage
                if hasattr(response, 'usage'):
                    self._tokens_used = response.usage.total_tokens
                    if hasattr(response.usage, 'prompt_tokens') and hasattr(response.usage, 'completion_tokens'):
                        # Some models provide detailed usage
                        pass
                
                return GroqResponse(
                    content=content,
                    tokens_used=self._tokens_used,
                    model=self.model
                )
                
            except Exception as e:
                error_str = str(e).lower()
                
                # Handle rate limit errors (429)
                if '429' in error_str or 'rate limit' in error_str or 'quota' in error_str:
                    if attempt < max_retries - 1:
                        # Exponential backoff: 2^attempt seconds
                        wait_time = 2 ** attempt
                        logger.warning(f"Rate limit hit, retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise GroqRateLimitError(
                            f"Rate limit exceeded after {max_retries} attempts. "
                            f"Please wait before trying again."
                        ) from e
                
                # Handle authentication errors (401, 403)
                if '401' in error_str or '403' in error_str or 'unauthorized' in error_str or 'forbidden' in error_str:
                    raise GroqAuthenticationError(
                        f"Authentication failed: {e}. Please check your API key."
                    ) from e
                
                # Handle other API errors (400, 500, etc.)
                if '400' in error_str or '500' in error_str or '502' in error_str or '503' in error_str:
                    if attempt < max_retries - 1:
                        # Exponential backoff for server errors
                        wait_time = 2 ** attempt
                        logger.warning(f"API error, retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise GroqAPIError(
                            f"API error after {max_retries} attempts: {e}"
                        ) from e
                
                # For other errors, don't retry
                raise GroqAPIError(f"Unexpected error: {e}") from e
        
        # Should never reach here, but just in case
        raise GroqAPIError(f"Failed after {max_retries} attempts")
    
    @property
    def tokens_used(self) -> int:
        """Get total tokens used in this session"""
        return self._tokens_used
    
    @property
    def tokens_limit(self) -> Optional[int]:
        """Get token limit (if available)"""
        return self._tokens_limit

