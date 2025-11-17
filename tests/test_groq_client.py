"""
Tests for Groq API client
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from apitest.ai.groq_client import (
    GroqClient, GroqAPIError, GroqRateLimitError, GroqAuthenticationError, GroqResponse
)


class TestGroqClient:
    """Test GroqClient class"""
    
    def test_initialization(self):
        """Test GroqClient initialization"""
        client = GroqClient(
            api_key='test-key',
            model='llama-3-groq-70b',
            temperature=0.8,
            max_tokens=3000
        )
        
        assert client.api_key == 'test-key'
        assert client.model == 'llama-3-groq-70b'
        assert client.temperature == 0.8
        assert client.max_tokens == 3000
        assert client.tokens_used == 0
    
    @patch('groq.Groq')
    def test_successful_generation(self, mock_groq_class):
        """Test successful API call"""
        # Mock Groq client and response
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Generated test case"
        mock_response.usage = Mock()
        mock_response.usage.total_tokens = 150
        
        mock_groq_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_response
        
        client = GroqClient(api_key='test-key')
        result = client.generate("Generate a test case")
        
        assert result == "Generated test case"
        assert client.tokens_used == 150
        mock_client.chat.completions.create.assert_called_once()
    
    @patch('groq.Groq')
    def test_rate_limit_error_with_retry(self, mock_groq_class):
        """Test rate limit error with retry logic"""
        import time
        from unittest.mock import call
        
        mock_client = Mock()
        mock_groq_class.return_value = mock_client
        
        # First call fails with rate limit, second succeeds
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Success after retry"
        mock_response.usage = Mock()
        mock_response.usage.total_tokens = 100
        
        mock_client.chat.completions.create.side_effect = [
            Exception("429 Rate limit exceeded"),
            mock_response
        ]
        
        client = GroqClient(api_key='test-key')
        
        with patch('time.sleep'):  # Mock sleep to speed up test
            result = client.generate("Test prompt")
        
        assert result == "Success after retry"
        assert mock_client.chat.completions.create.call_count == 2
    
    @patch('groq.Groq')
    def test_rate_limit_error_max_retries(self, mock_groq_class):
        """Test rate limit error after max retries"""
        mock_client = Mock()
        mock_groq_class.return_value = mock_client
        
        # All attempts fail with rate limit
        mock_client.chat.completions.create.side_effect = Exception("429 Rate limit exceeded")
        
        client = GroqClient(api_key='test-key')
        
        with patch('time.sleep'):  # Mock sleep
            with pytest.raises(GroqRateLimitError, match="Rate limit exceeded"):
                client.generate("Test prompt")
        
        # Should have tried max_retries times (default 3)
        assert mock_client.chat.completions.create.call_count == 3
    
    @patch('groq.Groq')
    def test_authentication_error(self, mock_groq_class):
        """Test authentication error"""
        mock_client = Mock()
        mock_groq_class.return_value = mock_client
        
        mock_client.chat.completions.create.side_effect = Exception("401 Unauthorized")
        
        client = GroqClient(api_key='invalid-key')
        
        with pytest.raises(GroqAuthenticationError, match="Authentication failed"):
            client.generate("Test prompt")
    
    @patch('groq.Groq')
    def test_api_error_with_retry(self, mock_groq_class):
        """Test API error (500) with retry"""
        mock_client = Mock()
        mock_groq_class.return_value = mock_client
        
        # First call fails with 500, second succeeds
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Success after retry"
        mock_response.usage = Mock()
        mock_response.usage.total_tokens = 100
        
        mock_client.chat.completions.create.side_effect = [
            Exception("500 Internal Server Error"),
            mock_response
        ]
        
        client = GroqClient(api_key='test-key')
        
        with patch('time.sleep'):  # Mock sleep
            result = client.generate("Test prompt")
        
        assert result == "Success after retry"
        assert mock_client.chat.completions.create.call_count == 2
    
    def test_missing_groq_library(self):
        """Test error when groq library is not installed"""
        # Mock the import to raise ImportError
        import sys
        import builtins
        original_import = builtins.__import__
        
        def mock_import(name, *args, **kwargs):
            if name == 'groq':
                raise ImportError("No module named 'groq'")
            return original_import(name, *args, **kwargs)
        
        builtins.__import__ = mock_import
        
        # Clear the module cache to force re-import
        if 'groq' in sys.modules:
            del sys.modules['groq']
        if 'apitest.ai.groq_client' in sys.modules:
            del sys.modules['apitest.ai.groq_client']
        
        # Re-import to trigger the import error
        from apitest.ai import groq_client
        client = groq_client.GroqClient(api_key='test-key')
        
        try:
            with pytest.raises(GroqAPIError, match="Groq library not installed"):
                client.generate("Test prompt")
        finally:
            # Restore original import
            builtins.__import__ = original_import
            # Clear cache again
            if 'groq' in sys.modules:
                del sys.modules['groq']
            if 'apitest.ai.groq_client' in sys.modules:
                del sys.modules['apitest.ai.groq_client']
    
    @patch('groq.Groq')
    def test_tokens_used_tracking(self, mock_groq_class):
        """Test token usage tracking"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.usage = Mock()
        mock_response.usage.total_tokens = 250
        
        mock_groq_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_response
        
        client = GroqClient(api_key='test-key')
        client.generate("Test")
        
        assert client.tokens_used == 250
    
    @patch('groq.Groq')
    def test_request_parameters(self, mock_groq_class):
        """Test that request parameters are passed correctly"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.usage = Mock()
        mock_response.usage.total_tokens = 100
        
        mock_groq_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_response
        
        client = GroqClient(
            api_key='test-key',
            model='llama-3-groq-70b',
            temperature=0.9,
            max_tokens=1500
        )
        
        client.generate("Test prompt")
        
        # Verify call was made with correct parameters
        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs['model'] == 'llama-3-groq-70b'
        assert call_args.kwargs['temperature'] == 0.9
        assert call_args.kwargs['max_tokens'] == 1500
        assert call_args.kwargs['messages'][0]['content'] == "Test prompt"


class TestGroqExceptions:
    """Test Groq exception classes"""
    
    def test_groq_api_error(self):
        """Test GroqAPIError exception"""
        error = GroqAPIError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)
    
    def test_groq_rate_limit_error(self):
        """Test GroqRateLimitError exception"""
        error = GroqRateLimitError("Rate limit exceeded")
        assert str(error) == "Rate limit exceeded"
        assert isinstance(error, GroqAPIError)
    
    def test_groq_authentication_error(self):
        """Test GroqAuthenticationError exception"""
        error = GroqAuthenticationError("Auth failed")
        assert str(error) == "Auth failed"
        assert isinstance(error, GroqAPIError)

