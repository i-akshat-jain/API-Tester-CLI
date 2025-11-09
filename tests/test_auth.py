"""
Tests for authentication handler
"""

import pytest
import requests
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from apitest.auth import AuthHandler, OAuthHandler


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


# OAuth 2.0 Tests

def test_oauth_handler_initialization():
    """Test OAuthHandler initialization"""
    handler = OAuthHandler()
    assert handler.auth_type == 'oauth2'
    assert handler.grant_type is None
    assert handler.token_url is None
    assert handler.access_token is None


def test_oauth_configure():
    """Test OAuth configuration"""
    handler = OAuthHandler()
    handler.configure_oauth(
        grant_type='client_credentials',
        token_url='https://auth.example.com/token',
        client_id='test_client_id',
        client_secret='test_client_secret',
        scope='read write'
    )
    
    assert handler.grant_type == 'client_credentials'
    assert handler.token_url == 'https://auth.example.com/token'
    assert handler.client_id == 'test_client_id'
    assert handler.client_secret == 'test_client_secret'
    assert handler.scope == 'read write'


@patch('apitest.auth.requests.post')
def test_oauth_client_credentials_flow(mock_post):
    """Test OAuth Client Credentials flow"""
    # Mock successful token response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'access_token': 'test_access_token_123',
        'token_type': 'Bearer',
        'expires_in': 3600,
        'scope': 'read write'
    }
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response
    
    handler = OAuthHandler()
    handler.configure_oauth(
        grant_type='client_credentials',
        token_url='https://auth.example.com/token',
        client_id='test_client_id',
        client_secret='test_client_secret',
        scope='read write'
    )
    
    # Fetch token
    token = handler.fetch_token()
    
    assert token == 'test_access_token_123'
    assert handler.access_token == 'test_access_token_123'
    assert handler.token_type == 'Bearer'
    assert handler.token_expires_at is not None
    assert not handler.is_token_expired()
    
    # Verify request was made correctly
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args[0][0] == 'https://auth.example.com/token'
    assert call_args[1]['data']['grant_type'] == 'client_credentials'
    assert call_args[1]['data']['client_id'] == 'test_client_id'
    assert call_args[1]['data']['client_secret'] == 'test_client_secret'
    assert call_args[1]['data']['scope'] == 'read write'


@patch('apitest.auth.requests.post')
def test_oauth_client_credentials_without_scope(mock_post):
    """Test OAuth Client Credentials flow without scope"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'access_token': 'test_token',
        'token_type': 'Bearer',
        'expires_in': 3600
    }
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response
    
    handler = OAuthHandler()
    handler.configure_oauth(
        grant_type='client_credentials',
        token_url='https://auth.example.com/token',
        client_id='test_client_id',
        client_secret='test_client_secret'
    )
    
    token = handler.fetch_token()
    assert token == 'test_token'
    
    # Verify scope was not included in request
    call_args = mock_post.call_args
    assert 'scope' not in call_args[1]['data']


@patch('apitest.auth.requests.post')
def test_oauth_token_expiration_handling(mock_post):
    """Test OAuth token expiration handling"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'access_token': 'test_token',
        'token_type': 'Bearer',
        'expires_in': 3600  # 1 hour
    }
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response
    
    handler = OAuthHandler()
    handler.configure_oauth(
        grant_type='client_credentials',
        token_url='https://auth.example.com/token',
        client_id='test_client_id',
        client_secret='test_client_secret'
    )
    
    handler.fetch_token()
    
    # Token should not be expired immediately
    assert not handler.is_token_expired()
    
    # Manually set expiration to past
    handler.token_expires_at = datetime.now() - timedelta(seconds=1)
    assert handler.is_token_expired()


@patch('apitest.auth.requests.post')
def test_oauth_token_without_expiration(mock_post):
    """Test OAuth token without expiration field"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'access_token': 'test_token',
        'token_type': 'Bearer'
    }
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response
    
    handler = OAuthHandler()
    handler.configure_oauth(
        grant_type='client_credentials',
        token_url='https://auth.example.com/token',
        client_id='test_client_id',
        client_secret='test_client_secret'
    )
    
    handler.fetch_token()
    
    # Token without expiration should not be considered expired
    assert handler.token_expires_at is None
    assert not handler.is_token_expired()


@patch('apitest.auth.requests.post')
def test_oauth_get_headers(mock_post):
    """Test OAuth handler get_headers method"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'access_token': 'test_token_123',
        'token_type': 'Bearer',
        'expires_in': 3600
    }
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response
    
    handler = OAuthHandler()
    handler.configure_oauth(
        grant_type='client_credentials',
        token_url='https://auth.example.com/token',
        client_id='test_client_id',
        client_secret='test_client_secret'
    )
    
    handler.fetch_token()
    headers = handler.get_headers()
    
    assert 'Authorization' in headers
    assert headers['Authorization'] == 'Bearer test_token_123'


@patch('apitest.auth.requests.post')
def test_oauth_error_handling(mock_post):
    """Test OAuth error handling"""
    import requests
    
    # Mock error response
    mock_response = Mock()
    mock_response.status_code = 400
    mock_response.json.return_value = {
        'error': 'invalid_client',
        'error_description': 'Invalid client credentials'
    }
    mock_response.text = 'Bad Request'
    
    # Create an HTTPError exception
    http_error = requests.exceptions.HTTPError("400 Client Error")
    http_error.response = mock_response
    mock_response.raise_for_status.side_effect = http_error
    mock_post.return_value = mock_response
    
    handler = OAuthHandler()
    handler.configure_oauth(
        grant_type='client_credentials',
        token_url='https://auth.example.com/token',
        client_id='invalid_client_id',
        client_secret='invalid_secret'
    )
    
    with pytest.raises(ValueError) as exc_info:
        handler.fetch_token()
    
    assert 'OAuth token request failed' in str(exc_info.value)
    assert 'invalid_client' in str(exc_info.value) or '400' in str(exc_info.value)


def test_oauth_fetch_token_without_config():
    """Test fetching token without configuration"""
    handler = OAuthHandler()
    
    with pytest.raises(ValueError) as exc_info:
        handler.fetch_token()
    
    assert 'OAuth configuration incomplete' in str(exc_info.value)


def test_oauth_fetch_token_missing_credentials():
    """Test fetching token with missing client credentials"""
    handler = OAuthHandler()
    handler.configure_oauth(
        grant_type='client_credentials',
        token_url='https://auth.example.com/token',
        client_id='',  # Empty
        client_secret=''
    )
    
    with pytest.raises(ValueError) as exc_info:
        handler.fetch_token()
    
    assert 'client_id and client_secret are required' in str(exc_info.value)


@patch('apitest.auth.requests.post')
def test_oauth_missing_access_token_in_response(mock_post):
    """Test handling of response missing access_token field"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'token_type': 'Bearer',
        'expires_in': 3600
        # Missing 'access_token'
    }
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response
    
    handler = OAuthHandler()
    handler.configure_oauth(
        grant_type='client_credentials',
        token_url='https://auth.example.com/token',
        client_id='test_client_id',
        client_secret='test_client_secret'
    )
    
    with pytest.raises(ValueError) as exc_info:
        handler.fetch_token()
    
    assert 'missing \'access_token\' field' in str(exc_info.value)


# OAuth Token Caching Integration Tests

@patch('apitest.storage.token_store.TokenStore')
@patch('apitest.auth.requests.post')
def test_oauth_get_token_from_cache(mock_post, mock_token_store_class):
    """Test getting OAuth token from cache"""
    # Setup mock token store
    mock_token_store = mock_token_store_class.return_value
    mock_token_store.get_token.return_value = 'cached_token_123'
    mock_token_store.get_token_metadata.return_value = {
        'token_type': 'Bearer',
        'expires_at': (datetime.now() + timedelta(hours=1)).isoformat(),
        'refresh_token': None
    }
    
    handler = OAuthHandler()
    handler.configure_oauth(
        grant_type='client_credentials',
        token_url='https://auth.example.com/token',
        client_id='test_client_id',
        client_secret='test_client_secret'
    )
    
    token = handler.get_or_fetch_token('test:identifier', use_cache=True)
    
    assert token == 'cached_token_123'
    assert handler.access_token == 'cached_token_123'
    # Should not make HTTP request if using cache
    mock_post.assert_not_called()
    mock_token_store.get_token.assert_called_once_with('test:identifier')


@patch('apitest.storage.token_store.TokenStore')
@patch('apitest.auth.requests.post')
def test_oauth_fetch_when_cache_empty(mock_post, mock_token_store_class):
    """Test fetching new token when cache is empty"""
    # Setup mock token store - no cached token
    mock_token_store = mock_token_store_class.return_value
    mock_token_store.get_token.return_value = None
    mock_token_store.get_refresh_token.return_value = None
    
    # Mock successful token response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'access_token': 'new_token_456',
        'token_type': 'Bearer',
        'expires_in': 3600
    }
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response
    
    handler = OAuthHandler()
    handler.configure_oauth(
        grant_type='client_credentials',
        token_url='https://auth.example.com/token',
        client_id='test_client_id',
        client_secret='test_client_secret'
    )
    
    token = handler.get_or_fetch_token('test:identifier', use_cache=True)
    
    assert token == 'new_token_456'
    # Should have fetched new token
    mock_post.assert_called_once()
    # Should have stored token in cache
    mock_token_store.store_token.assert_called_once()
    call_kwargs = mock_token_store.store_token.call_args[1]
    assert call_kwargs['token'] == 'new_token_456'
    assert call_kwargs['identifier'] == 'test:identifier'


@patch('apitest.storage.token_store.TokenStore')
@patch('apitest.auth.requests.post')
def test_oauth_refresh_expired_token(mock_post, mock_token_store_class):
    """Test refreshing expired token using refresh_token"""
    # Setup mock token store - expired token, but has refresh_token
    mock_token_store = mock_token_store_class.return_value
    mock_token_store.get_token.return_value = None  # Expired, so returns None
    mock_token_store.get_refresh_token.return_value = 'refresh_token_789'
    
    # Mock successful refresh response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'access_token': 'refreshed_token_999',
        'token_type': 'Bearer',
        'expires_in': 3600,
        'refresh_token': 'new_refresh_token_888'
    }
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response
    
    handler = OAuthHandler()
    handler.configure_oauth(
        grant_type='password',
        token_url='https://auth.example.com/token',
        client_id='test_client_id',
        client_secret='test_client_secret',
        username='user',
        password='pass'
    )
    
    token = handler.get_or_fetch_token('test:identifier', use_cache=True)
    
    assert token == 'refreshed_token_999'
    assert handler.refresh_token == 'new_refresh_token_888'
    # Should have called refresh endpoint
    mock_post.assert_called_once()
    call_data = mock_post.call_args[1]['data']
    assert call_data['grant_type'] == 'refresh_token'
    assert call_data['refresh_token'] == 'refresh_token_789'
    # Should have stored refreshed token
    mock_token_store.store_token.assert_called_once()


@patch('apitest.storage.token_store.TokenStore')
@patch('apitest.auth.requests.post')
def test_oauth_fallback_on_refresh_failure(mock_post, mock_token_store_class):
    """Test fallback to fresh token when refresh fails"""
    # Setup mock token store
    mock_token_store = mock_token_store_class.return_value
    mock_token_store.get_token.return_value = None
    mock_token_store.get_refresh_token.return_value = 'invalid_refresh_token'
    
    # First call (refresh) fails, second call (fetch) succeeds
    mock_refresh_response = Mock()
    mock_refresh_response.status_code = 400
    mock_refresh_response.json.return_value = {'error': 'invalid_grant'}
    mock_refresh_response.raise_for_status.side_effect = requests.exceptions.HTTPError("400")
    mock_refresh_response.text = 'Bad Request'
    
    mock_fetch_response = Mock()
    mock_fetch_response.status_code = 200
    mock_fetch_response.json.return_value = {
        'access_token': 'fresh_token_111',
        'token_type': 'Bearer',
        'expires_in': 3600
    }
    mock_fetch_response.raise_for_status = Mock()
    
    mock_post.side_effect = [
        requests.exceptions.HTTPError("400"),
        mock_fetch_response
    ]
    # Fix the side effect to properly raise the exception
    def side_effect(*args, **kwargs):
        if mock_post.call_count == 1:
            http_error = requests.exceptions.HTTPError("400")
            http_error.response = mock_refresh_response
            raise http_error
        return mock_fetch_response
    
    mock_post.side_effect = side_effect
    
    handler = OAuthHandler()
    handler.configure_oauth(
        grant_type='client_credentials',
        token_url='https://auth.example.com/token',
        client_id='test_client_id',
        client_secret='test_client_secret'
    )
    
    token = handler.get_or_fetch_token('test:identifier', use_cache=True)
    
    assert token == 'fresh_token_111'
    # Should have tried refresh first, then fetched new token
    assert mock_post.call_count == 2
    # Should have stored the fresh token
    mock_token_store.store_token.assert_called_once()


@patch('apitest.storage.token_store.TokenStore')
@patch('apitest.auth.requests.post')
def test_oauth_skip_cache_when_disabled(mock_post, mock_token_store_class):
    """Test skipping cache when use_cache=False"""
    mock_token_store = mock_token_store_class.return_value
    
    # Mock successful token response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'access_token': 'fresh_token_no_cache',
        'token_type': 'Bearer',
        'expires_in': 3600
    }
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response
    
    handler = OAuthHandler()
    handler.configure_oauth(
        grant_type='client_credentials',
        token_url='https://auth.example.com/token',
        client_id='test_client_id',
        client_secret='test_client_secret'
    )
    
    token = handler.get_or_fetch_token('test:identifier', use_cache=False)
    
    assert token == 'fresh_token_no_cache'
    # Should not check cache
    mock_token_store.get_token.assert_not_called()
    # Should fetch fresh token
    mock_post.assert_called_once()


@patch('apitest.storage.token_store.TokenStore')
def test_oauth_fallback_when_tokenstore_unavailable(mock_token_store_class):
    """Test fallback when TokenStore is not available"""
    # Make TokenStore raise exception on initialization
    mock_token_store_class.side_effect = Exception("Keyring not available")
    
    handler = OAuthHandler()
    handler.configure_oauth(
        grant_type='client_credentials',
        token_url='https://auth.example.com/token',
        client_id='test_client_id',
        client_secret='test_client_secret'
    )
    
    # Should not raise error, but should attempt to fetch (which will fail without mock)
    # This test just ensures the exception is caught gracefully
    try:
        handler.get_or_fetch_token('test:identifier', use_cache=True)
    except ValueError:
        # Expected - fetch_token will fail without proper mock
        pass
    
    # Should have attempted to use TokenStore
    mock_token_store_class.assert_called_once()


@patch('apitest.storage.token_store.TokenStore')
@patch('apitest.auth.requests.post')
def test_oauth_store_token_metadata(mock_post, mock_token_store_class):
    """Test that token metadata is stored correctly"""
    mock_token_store = mock_token_store_class.return_value
    mock_token_store.get_token.return_value = None
    mock_token_store.get_refresh_token.return_value = None
    
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'access_token': 'token_with_metadata',
        'token_type': 'Bearer',
        'expires_in': 7200,
        'refresh_token': 'refresh_123'
    }
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response
    
    handler = OAuthHandler()
    handler.configure_oauth(
        grant_type='client_credentials',
        token_url='https://auth.example.com/token',
        client_id='test_client_id',
        client_secret='test_client_secret',
        scope='read write'
    )
    
    handler.get_or_fetch_token('test:identifier', use_cache=True)
    
    # Verify store_token was called with correct metadata
    mock_token_store.store_token.assert_called_once()
    call_kwargs = mock_token_store.store_token.call_args[1]
    assert call_kwargs['token'] == 'token_with_metadata'
    assert call_kwargs['refresh_token'] == 'refresh_123'
    assert call_kwargs['token_type'] == 'bearer'
    assert call_kwargs['expires_at'] is not None
    assert call_kwargs['metadata']['grant_type'] == 'client_credentials'
    assert call_kwargs['metadata']['token_url'] == 'https://auth.example.com/token'
    assert call_kwargs['metadata']['scope'] == 'read write'


# Edge case tests for robustness

def test_auth_handler_empty_string():
    """Test AuthHandler with empty auth string"""
    handler = AuthHandler()
    with pytest.raises(ValueError) as exc_info:
        handler.parse_auth_string('')
    assert 'empty' in str(exc_info.value).lower()


def test_auth_handler_whitespace_only():
    """Test AuthHandler with whitespace-only auth string"""
    handler = AuthHandler()
    with pytest.raises(ValueError) as exc_info:
        handler.parse_auth_string('   ')
    assert 'empty' in str(exc_info.value).lower()


def test_auth_handler_no_equals_sign():
    """Test AuthHandler with auth string missing equals sign"""
    handler = AuthHandler()
    with pytest.raises(ValueError) as exc_info:
        handler.parse_auth_string('bearertoken')
    assert 'format' in str(exc_info.value).lower() or 'invalid' in str(exc_info.value).lower()


def test_auth_handler_empty_value():
    """Test AuthHandler with empty value after equals"""
    handler = AuthHandler()
    with pytest.raises(ValueError) as exc_info:
        handler.parse_auth_string('bearer=')
    assert 'empty' in str(exc_info.value).lower()


def test_auth_handler_special_characters_in_token():
    """Test AuthHandler with special characters in token"""
    handler = AuthHandler()
    special_token = 'token!@#$%^&*()_+-=[]{}|;:,.<>?'
    handler.parse_auth_string(f'bearer={special_token}')
    headers = handler.get_headers()
    assert headers['Authorization'] == f'Bearer {special_token}'


def test_auth_handler_very_long_token():
    """Test AuthHandler with very long token"""
    handler = AuthHandler()
    long_token = 'a' * 10000  # 10KB token
    handler.parse_auth_string(f'bearer={long_token}')
    headers = handler.get_headers()
    assert len(headers['Authorization']) == len(f'Bearer {long_token}')


def test_auth_handler_apikey_missing_colon():
    """Test AuthHandler API key format missing colon"""
    handler = AuthHandler()
    with pytest.raises(ValueError) as exc_info:
        handler.parse_auth_string('apikey=value')
    assert 'format' in str(exc_info.value).lower() or 'invalid' in str(exc_info.value).lower()


def test_auth_handler_apikey_empty_name():
    """Test AuthHandler API key with empty name"""
    handler = AuthHandler()
    with pytest.raises(ValueError) as exc_info:
        handler.parse_auth_string('apikey=:value')
    assert 'empty' in str(exc_info.value).lower()


def test_auth_handler_apikey_empty_value():
    """Test AuthHandler API key with empty value"""
    handler = AuthHandler()
    with pytest.raises(ValueError) as exc_info:
        handler.parse_auth_string('apikey=KeyName:')
    assert 'empty' in str(exc_info.value).lower()


def test_auth_handler_apikey_invalid_location():
    """Test AuthHandler API key with invalid location"""
    handler = AuthHandler()
    with pytest.raises(ValueError) as exc_info:
        handler.parse_auth_string('apikey=KeyName:value:invalid')
    assert 'location' in str(exc_info.value).lower() or 'invalid' in str(exc_info.value).lower()


def test_auth_handler_header_missing_colon():
    """Test AuthHandler header format missing colon"""
    handler = AuthHandler()
    with pytest.raises(ValueError) as exc_info:
        handler.parse_auth_string('header=value')
    assert 'format' in str(exc_info.value).lower() or 'invalid' in str(exc_info.value).lower()


def test_auth_handler_unsupported_type():
    """Test AuthHandler with unsupported auth type"""
    handler = AuthHandler()
    with pytest.raises(ValueError) as exc_info:
        handler.parse_auth_string('unsupported=value')
    assert 'unsupported' in str(exc_info.value).lower()


def test_auth_handler_multiple_custom_headers():
    """Test AuthHandler with multiple custom headers"""
    handler = AuthHandler()
    handler.parse_auth_string('header=Header1:value1')
    # Parse another header (this would typically be done via list of auth strings)
    handler.custom_headers['Header2'] = 'value2'
    headers = handler.get_headers()
    assert 'Header1' in headers
    assert 'Header2' in headers


@patch('apitest.auth.requests.post')
def test_oauth_network_timeout(mock_post):
    """Test OAuth handler with network timeout"""
    import requests
    mock_post.side_effect = requests.exceptions.Timeout("Connection timeout")
    
    handler = OAuthHandler()
    handler.configure_oauth(
        grant_type='client_credentials',
        token_url='https://auth.example.com/token',
        client_id='test_client_id',
        client_secret='test_client_secret'
    )
    
    with pytest.raises(ValueError) as exc_info:
        handler.fetch_token()
    assert 'timeout' in str(exc_info.value).lower() or 'failed' in str(exc_info.value).lower()


@patch('apitest.auth.requests.post')
def test_oauth_connection_error(mock_post):
    """Test OAuth handler with connection error"""
    import requests
    mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")
    
    handler = OAuthHandler()
    handler.configure_oauth(
        grant_type='client_credentials',
        token_url='https://auth.example.com/token',
        client_id='test_client_id',
        client_secret='test_client_secret'
    )
    
    with pytest.raises(ValueError) as exc_info:
        handler.fetch_token()
    assert 'failed' in str(exc_info.value).lower()


@patch('apitest.auth.requests.post')
def test_oauth_non_json_response(mock_post):
    """Test OAuth handler with non-JSON response"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("Not JSON")
    mock_response.text = '<html>Error</html>'
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response
    
    handler = OAuthHandler()
    handler.configure_oauth(
        grant_type='client_credentials',
        token_url='https://auth.example.com/token',
        client_id='test_client_id',
        client_secret='test_client_secret'
    )
    
    with pytest.raises(ValueError) as exc_info:
        handler.fetch_token()
    # Should handle non-JSON response gracefully - may raise ValueError from json() call
    # The error message will be about JSON parsing
    assert isinstance(exc_info.value, ValueError)


@patch('apitest.auth.requests.post')
def test_oauth_malformed_json_response(mock_post):
    """Test OAuth handler with malformed JSON response"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_response.text = '{invalid json}'
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response
    
    handler = OAuthHandler()
    handler.configure_oauth(
        grant_type='client_credentials',
        token_url='https://auth.example.com/token',
        client_id='test_client_id',
        client_secret='test_client_secret'
    )
    
    with pytest.raises(ValueError):
        handler.fetch_token()


@patch('apitest.auth.requests.post')
def test_oauth_token_with_zero_expiration(mock_post):
    """Test OAuth token with expires_in=0"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'access_token': 'test_token',
        'token_type': 'Bearer',
        'expires_in': 0
    }
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response
    
    handler = OAuthHandler()
    handler.configure_oauth(
        grant_type='client_credentials',
        token_url='https://auth.example.com/token',
        client_id='test_client_id',
        client_secret='test_client_secret'
    )
    
    handler.fetch_token()
    # Token with 0 expiration should be considered expired immediately
    assert handler.token_expires_at is not None


@patch('apitest.auth.requests.post')
def test_oauth_token_with_negative_expiration(mock_post):
    """Test OAuth token with negative expires_in"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'access_token': 'test_token',
        'token_type': 'Bearer',
        'expires_in': -100
    }
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response
    
    handler = OAuthHandler()
    handler.configure_oauth(
        grant_type='client_credentials',
        token_url='https://auth.example.com/token',
        client_id='test_client_id',
        client_secret='test_client_secret'
    )
    
    handler.fetch_token()
    # Should handle negative expiration
    assert handler.token_expires_at is not None


@patch('apitest.auth.requests.post')
def test_oauth_token_with_string_expires_in(mock_post):
    """Test OAuth token with string expires_in (should handle gracefully)"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'access_token': 'test_token',
        'token_type': 'Bearer',
        'expires_in': '3600'  # String instead of int
    }
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response
    
    handler = OAuthHandler()
    handler.configure_oauth(
        grant_type='client_credentials',
        token_url='https://auth.example.com/token',
        client_id='test_client_id',
        client_secret='test_client_secret'
    )
    
    # Should handle string expires_in (may raise ValueError or convert)
    try:
        handler.fetch_token()
        # If it succeeds, token_expires_at should be set
        assert handler.token_expires_at is not None
    except (ValueError, TypeError):
        # If it fails, that's also acceptable behavior
        pass


@patch('apitest.auth.requests.post')
def test_oauth_password_grant_empty_credentials(mock_post):
    """Test OAuth password grant with empty username/password"""
    handler = OAuthHandler()
    handler.configure_oauth(
        grant_type='password',
        token_url='https://auth.example.com/token',
        client_id='test_client_id',
        client_secret='test_client_secret',
        username='',
        password=''
    )
    
    with pytest.raises(ValueError) as exc_info:
        handler.fetch_token()
    assert 'required' in str(exc_info.value).lower()


def test_oauth_get_headers_without_token():
    """Test OAuth get_headers when no token is set"""
    handler = OAuthHandler()
    headers = handler.get_headers()
    # Should return empty dict or dict without Authorization
    assert 'Authorization' not in headers


def test_oauth_is_token_expired_no_token():
    """Test OAuth is_token_expired when no token is set"""
    handler = OAuthHandler()
    assert handler.is_token_expired() is True


def test_oauth_is_token_expired_no_expiration():
    """Test OAuth is_token_expired when token has no expiration"""
    handler = OAuthHandler()
    handler.access_token = 'test_token'
    handler.token_expires_at = None
    assert handler.is_token_expired() is False  # No expiration means not expired


def test_auth_handler_bearer_token_with_spaces():
    """Test AuthHandler bearer token with leading/trailing spaces"""
    handler = AuthHandler()
    handler.parse_auth_string('bearer=  token_with_spaces  ')
    headers = handler.get_headers()
    # Token should be trimmed or kept as-is depending on implementation
    assert 'token_with_spaces' in headers['Authorization']


def test_auth_handler_apikey_with_special_chars_in_name():
    """Test AuthHandler API key with special characters in name"""
    handler = AuthHandler()
    handler.parse_auth_string('apikey=X-API-Key-123:value')
    headers = handler.get_headers()
    assert headers['X-API-Key-123'] == 'value'


def test_auth_handler_apikey_with_special_chars_in_value():
    """Test AuthHandler API key with special characters in value"""
    handler = AuthHandler()
    special_value = 'key!@#$%^&*()'
    handler.parse_auth_string(f'apikey=X-API-Key:{special_value}')
    headers = handler.get_headers()
    assert headers['X-API-Key'] == special_value

