"""
Tests for authentication handler
"""

import pytest
from apitest.auth import AuthHandler


def test_bearer_auth():
    """Test Bearer token authentication"""
    handler = AuthHandler()
    handler.parse_auth_string('bearer=test_token_123')
    
    headers = handler.get_headers()
    assert headers['Authorization'] == 'Bearer test_token_123'
    assert len(handler.get_query_params()) == 0


def test_api_key_header():
    """Test API key authentication in header"""
    handler = AuthHandler()
    handler.parse_auth_string('apikey=X-API-Key:my_api_key')
    
    headers = handler.get_headers()
    assert headers['X-API-Key'] == 'my_api_key'
    assert len(handler.get_query_params()) == 0


def test_api_key_query():
    """Test API key authentication in query parameter"""
    handler = AuthHandler()
    handler.parse_auth_string('apikey=api_key:my_key:query')
    
    params = handler.get_query_params()
    assert params['api_key'] == 'my_key'
    assert len(handler.get_headers()) == 0


def test_custom_header():
    """Test custom header authentication"""
    handler = AuthHandler()
    handler.parse_auth_string('header=Custom-Auth:custom_value')
    
    headers = handler.get_headers()
    assert headers['Custom-Auth'] == 'custom_value'

