"""
Authentication handler for API requests
"""

import requests
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class AuthHandler:
    """Handle various authentication methods"""
    
    def __init__(self):
        self.auth_type: Optional[str] = None
        self.token: Optional[str] = None
        self.api_key_name: Optional[str] = None
        self.api_key_value: Optional[str] = None
        self.api_key_location: str = 'header'  # 'header' or 'query'
        self.custom_headers: Dict[str, str] = {}
    
    def parse_auth_string(self, auth_string: str):
        """
        Parse authentication string from CLI
        
        Supported formats:
        - bearer=TOKEN
        - apikey=KEY:VALUE
        - apikey=KEY:VALUE:location (location can be 'header' or 'query')
        - header=KEY:VALUE
        
        Args:
            auth_string: Authentication string from CLI
        """
        if not auth_string or not auth_string.strip():
            raise ValueError(
                "Auth string cannot be empty.\n"
                "Examples:\n"
                "  bearer=TOKEN\n"
                "  apikey=X-API-Key:value\n"
                "  apikey=key:value:query\n"
                "  header=Authorization:Basic base64"
            )
        
        if '=' not in auth_string:
            raise ValueError(
                f"Invalid auth format: '{auth_string}'\n"
                "Expected format: TYPE=VALUE\n\n"
                "Examples:\n"
                "  bearer=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...\n"
                "  apikey=X-API-Key:your_key_here\n"
                "  apikey=api_key:your_key_here:query\n"
                "  header=Authorization:Custom token123\n\n"
                "Supports $ENV_VAR for tokens: bearer=$API_TOKEN"
            )
        
        parts = auth_string.split('=', 1)
        auth_type = parts[0].lower().strip()
        auth_value = parts[1].strip()
        
        if not auth_value:
            raise ValueError(
                f"Auth value is empty for type '{auth_type}'.\n"
                "Example: bearer=TOKEN (replace TOKEN with your actual token)"
            )
        
        if auth_type == 'bearer':
            self.auth_type = 'bearer'
            self.token = auth_value
            if len(auth_value) < 10:  # Warn for very short tokens
                import warnings
                warnings.warn(f"Bearer token seems short ({len(auth_value)} chars). Make sure it's correct.")
        elif auth_type == 'apikey':
            # Format: apikey=KEY_NAME:KEY_VALUE or apikey=KEY_NAME:KEY_VALUE:location
            key_parts = auth_value.split(':')
            if len(key_parts) < 2:
                raise ValueError(
                    "Invalid API key format.\n\n"
                    "Expected: apikey=KEY_NAME:VALUE\n"
                    "   or:    apikey=KEY_NAME:VALUE:location (where location is 'header' or 'query')\n\n"
                    "Examples:\n"
                    "  apikey=X-API-Key:your_api_key_here\n"
                    "  apikey=api_key:your_key:query\n"
                    "  apikey=Authorization:Bearer $TOKEN:header"
                )
            self.auth_type = 'apikey'
            self.api_key_name = key_parts[0].strip()
            self.api_key_value = key_parts[1].strip()
            
            if not self.api_key_name:
                raise ValueError("API key name cannot be empty. Format: apikey=KEY_NAME:VALUE")
            if not self.api_key_value:
                raise ValueError("API key value cannot be empty. Format: apikey=KEY_NAME:VALUE")
            
            if len(key_parts) > 2:
                location = key_parts[2].strip().lower()
                if location not in ['header', 'query']:
                    raise ValueError(
                        f"Invalid API key location: '{location}'\n"
                        "Must be 'header' or 'query'\n"
                        "Example: apikey=X-API-Key:value:header"
                    )
                self.api_key_location = location
        elif auth_type == 'header':
            # Format: header=KEY:VALUE
            header_parts = auth_value.split(':', 1)
            if len(header_parts) < 2:
                raise ValueError(
                    "Invalid header format.\n\n"
                    "Expected: header=KEY:VALUE\n\n"
                    "Example:\n"
                    "  header=Authorization:Basic base64encoded"
                )
            header_key = header_parts[0].strip()
            header_value = header_parts[1].strip()
            if not header_key:
                raise ValueError("Header key cannot be empty. Format: header=KEY:VALUE")
            self.auth_type = 'header'
            self.custom_headers[header_key] = header_value
        else:
            raise ValueError(
                f"Unsupported auth type: '{auth_type}'\n\n"
                "Supported types:\n"
                "  bearer - Bearer token authentication\n"
                "  apikey - API key authentication (header or query)\n"
                "  header - Custom header authentication\n\n"
                "Examples:\n"
                "  bearer=$TOKEN\n"
                "  apikey=X-API-Key:value\n"
                "  header=Authorization:Custom value"
            )
    
    def get_headers(self) -> Dict[str, str]:
        """
        Get authentication headers
        
        Returns:
            Dictionary of headers to include in requests
        """
        headers = {}
        
        if self.auth_type == 'bearer' and self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        elif self.auth_type == 'apikey' and self.api_key_value and self.api_key_location == 'header':
            headers[self.api_key_name] = self.api_key_value
        
        # Add custom headers
        headers.update(self.custom_headers)
        
        return headers
    
    def get_query_params(self) -> Dict[str, str]:
        """
        Get authentication query parameters
        
        Returns:
            Dictionary of query parameters to include in requests
        """
        params = {}
        
        if self.auth_type == 'apikey' and self.api_key_value and self.api_key_location == 'query':
            params[self.api_key_name] = self.api_key_value
        
        return params


class OAuthHandler(AuthHandler):
    """Handle OAuth 2.0 authentication flows"""
    
    def __init__(self):
        super().__init__()
        self.auth_type = 'oauth2'
        self.grant_type: Optional[str] = None
        self.token_url: Optional[str] = None
        self.client_id: Optional[str] = None
        self.client_secret: Optional[str] = None
        self.username: Optional[str] = None
        self.password: Optional[str] = None
        self.scope: Optional[str] = None
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self.token_type: str = 'Bearer'
    
    def configure_oauth(self, grant_type: str, token_url: str, 
                       client_id: str, client_secret: str,
                       username: Optional[str] = None,
                       password: Optional[str] = None,
                       scope: Optional[str] = None):
        """
        Configure OAuth 2.0 parameters
        
        Args:
            grant_type: OAuth grant type (e.g., 'client_credentials', 'password')
            token_url: URL of the OAuth token endpoint
            client_id: OAuth client ID
            client_secret: OAuth client secret
            username: Username for password grant (optional)
            password: Password for password grant (optional)
            scope: OAuth scope (optional)
        """
        self.grant_type = grant_type
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.password = password
        self.scope = scope
    
    def fetch_token(self, timeout: int = 30) -> str:
        """
        Fetch OAuth access token from token endpoint
        
        Args:
            timeout: Request timeout in seconds
            
        Returns:
            Access token string
            
        Raises:
            ValueError: If configuration is invalid
            requests.RequestException: If token request fails
        """
        if not self.grant_type or not self.token_url:
            raise ValueError("OAuth configuration incomplete. Call configure_oauth() first.")
        
        if not self.client_id or not self.client_secret:
            raise ValueError("OAuth client_id and client_secret are required.")
        
        # Prepare token request based on grant type
        if self.grant_type == 'client_credentials':
            return self._fetch_client_credentials_token(timeout)
        elif self.grant_type == 'password':
            return self._fetch_password_token(timeout)
        else:
            raise ValueError(f"Unsupported OAuth grant type: {self.grant_type}")
    
    def _fetch_client_credentials_token(self, timeout: int) -> str:
        """
        Fetch token using Client Credentials flow
        
        Args:
            timeout: Request timeout in seconds
            
        Returns:
            Access token string
        """
        logger.debug(f"Fetching OAuth token using client_credentials flow from {self.token_url}")
        
        # Prepare request data
        data = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        
        if self.scope:
            data['scope'] = self.scope
        
        # Make token request
        try:
            response = requests.post(
                self.token_url,
                data=data,
                timeout=timeout,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            response.raise_for_status()
            
            # Parse response
            token_data = response.json()
            
            # Extract access token
            if 'access_token' not in token_data:
                raise ValueError(
                    f"Token response missing 'access_token' field. "
                    f"Response: {token_data}"
                )
            
            self.access_token = token_data['access_token']
            self.token_type = token_data.get('token_type', 'Bearer')
            
            # Handle token expiration
            if 'expires_in' in token_data:
                expires_in = int(token_data['expires_in'])
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                logger.debug(f"Token expires in {expires_in} seconds")
            else:
                self.token_expires_at = None
                logger.debug("Token expiration not specified in response")
            
            # Store refresh token if provided
            if 'refresh_token' in token_data:
                self.refresh_token = token_data['refresh_token']
                logger.debug("Refresh token received")
            
            logger.debug("OAuth token fetched successfully")
            return self.access_token
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"OAuth token request failed with status {e.response.status_code}"
            try:
                error_data = e.response.json()
                if 'error' in error_data:
                    error_msg += f": {error_data.get('error_description', error_data['error'])}"
            except:
                error_msg += f": {e.response.text}"
            raise ValueError(error_msg) from e
        except requests.exceptions.RequestException as e:
            raise ValueError(f"OAuth token request failed: {str(e)}") from e
    
    def _fetch_password_token(self, timeout: int) -> str:
        """
        Fetch token using Password/Resource Owner flow
        
        Args:
            timeout: Request timeout in seconds
            
        Returns:
            Access token string
        """
        if not self.username or not self.password:
            raise ValueError("Username and password are required for password grant type.")
        
        logger.debug(f"Fetching OAuth token using password flow from {self.token_url}")
        
        # Prepare request data
        data = {
            'grant_type': 'password',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'username': self.username,
            'password': self.password
        }
        
        if self.scope:
            data['scope'] = self.scope
        
        # Make token request
        try:
            response = requests.post(
                self.token_url,
                data=data,
                timeout=timeout,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            response.raise_for_status()
            
            # Parse response
            token_data = response.json()
            
            # Extract access token
            if 'access_token' not in token_data:
                raise ValueError(
                    f"Token response missing 'access_token' field. "
                    f"Response: {token_data}"
                )
            
            self.access_token = token_data['access_token']
            self.token_type = token_data.get('token_type', 'Bearer')
            
            # Handle token expiration
            if 'expires_in' in token_data:
                expires_in = int(token_data['expires_in'])
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                logger.debug(f"Token expires in {expires_in} seconds")
            else:
                self.token_expires_at = None
                logger.debug("Token expiration not specified in response")
            
            # Store refresh token if provided
            if 'refresh_token' in token_data:
                self.refresh_token = token_data['refresh_token']
                logger.debug("Refresh token received")
            
            logger.debug("OAuth token fetched successfully")
            return self.access_token
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"OAuth token request failed with status {e.response.status_code}"
            try:
                error_data = e.response.json()
                if 'error' in error_data:
                    error_msg += f": {error_data.get('error_description', error_data['error'])}"
            except:
                error_msg += f": {e.response.text}"
            raise ValueError(error_msg) from e
        except requests.exceptions.RequestException as e:
            raise ValueError(f"OAuth token request failed: {str(e)}") from e
    
    def is_token_expired(self) -> bool:
        """
        Check if the current access token is expired
        
        Returns:
            True if token is expired or missing, False otherwise
        """
        if not self.access_token:
            return True
        
        if not self.token_expires_at:
            return False  # No expiration set, assume not expired
        
        return datetime.now() >= self.token_expires_at
    
    def get_headers(self) -> Dict[str, str]:
        """
        Get authentication headers with OAuth token
        
        Returns:
            Dictionary of headers to include in requests
        """
        headers = {}
        
        if self.access_token:
            headers['Authorization'] = f'{self.token_type} {self.access_token}'
        
        # Add custom headers
        headers.update(self.custom_headers)
        
        return headers
    
    def get_query_params(self) -> Dict[str, str]:
        """
        Get authentication query parameters (OAuth doesn't use query params)
        
        Returns:
            Empty dictionary (OAuth uses headers only)
        """
        return {}
    
    def get_or_fetch_token(self, identifier: str, timeout: int = 30, 
                           use_cache: bool = True) -> str:
        """
        Get token from cache or fetch new one if needed
        
        This method integrates with TokenStore to cache OAuth tokens.
        It checks cache first, refreshes if expired (if refresh_token available),
        or fetches a new token if needed.
        
        Args:
            identifier: Unique identifier for token caching (e.g., from TokenStore.create_identifier)
            timeout: Request timeout in seconds
            use_cache: Whether to use cached tokens (default: True)
            
        Returns:
            Access token string
            
        Raises:
            ValueError: If configuration is invalid or token fetch fails
        """
        if not use_cache:
            # Skip cache, fetch fresh token
            return self.fetch_token(timeout)
        
        try:
            from apitest.storage.token_store import TokenStore
            token_store = TokenStore()
        except Exception as e:
            logger.warning(f"TokenStore not available, fetching fresh token: {e}")
            return self.fetch_token(timeout)
        
        # Check if we have a cached token
        cached_token = token_store.get_token(identifier)
        if cached_token:
            logger.debug(f"Using cached OAuth token for identifier: {identifier}")
            self.access_token = cached_token
            # Load metadata to get token_type and expiration
            metadata = token_store.get_token_metadata(identifier)
            if metadata:
                self.token_type = metadata.get('token_type', 'Bearer')
                if metadata.get('expires_at'):
                    try:
                        self.token_expires_at = datetime.fromisoformat(metadata['expires_at'])
                    except (ValueError, KeyError):
                        pass
                if metadata.get('refresh_token'):
                    self.refresh_token = metadata['refresh_token']
            return cached_token
        
        # No cached token or expired - check if we can refresh
        refresh_token = token_store.get_refresh_token(identifier)
        if refresh_token:
            logger.debug(f"Attempting to refresh OAuth token for identifier: {identifier}")
            try:
                new_token = self._refresh_token(refresh_token, timeout)
                # Store the new token
                self._store_token_in_cache(identifier, token_store)
                return new_token
            except Exception as e:
                logger.warning(f"Token refresh failed, fetching new token: {e}")
                # Fall through to fetch new token
        
        # Fetch new token
        logger.debug(f"Fetching new OAuth token for identifier: {identifier}")
        token = self.fetch_token(timeout)
        
        # Store the new token in cache
        self._store_token_in_cache(identifier, token_store)
        
        return token
    
    def _refresh_token(self, refresh_token: str, timeout: int = 30) -> str:
        """
        Refresh OAuth access token using refresh_token
        
        Args:
            refresh_token: Refresh token to use
            timeout: Request timeout in seconds
            
        Returns:
            New access token string
            
        Raises:
            ValueError: If refresh fails
        """
        if not self.token_url:
            raise ValueError("OAuth token_url not configured. Cannot refresh token.")
        
        logger.debug(f"Refreshing OAuth token from {self.token_url}")
        
        # Prepare refresh request
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
        }
        
        if self.client_id:
            data['client_id'] = self.client_id
        if self.client_secret:
            data['client_secret'] = self.client_secret
        if self.scope:
            data['scope'] = self.scope
        
        try:
            response = requests.post(
                self.token_url,
                data=data,
                timeout=timeout,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            response.raise_for_status()
            
            # Parse response
            token_data = response.json()
            
            # Extract access token
            if 'access_token' not in token_data:
                raise ValueError(
                    f"Token refresh response missing 'access_token' field. "
                    f"Response: {token_data}"
                )
            
            self.access_token = token_data['access_token']
            self.token_type = token_data.get('token_type', 'Bearer')
            
            # Handle token expiration
            if 'expires_in' in token_data:
                expires_in = int(token_data['expires_in'])
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                logger.debug(f"Refreshed token expires in {expires_in} seconds")
            else:
                self.token_expires_at = None
            
            # Update refresh token if new one provided
            if 'refresh_token' in token_data:
                self.refresh_token = token_data['refresh_token']
                logger.debug("New refresh token received")
            
            logger.debug("OAuth token refreshed successfully")
            return self.access_token
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"OAuth token refresh failed with status {e.response.status_code}"
            try:
                error_data = e.response.json()
                if 'error' in error_data:
                    error_msg += f": {error_data.get('error_description', error_data['error'])}"
            except:
                error_msg += f": {e.response.text}"
            raise ValueError(error_msg) from e
        except requests.exceptions.RequestException as e:
            raise ValueError(f"OAuth token refresh failed: {str(e)}") from e
    
    def _store_token_in_cache(self, identifier: str, token_store):
        """
        Store current OAuth token in token store
        
        Args:
            identifier: Unique identifier for token caching
            token_store: TokenStore instance
        """
        try:
            metadata = {}
            if self.grant_type:
                metadata['grant_type'] = self.grant_type
            if self.token_url:
                metadata['token_url'] = self.token_url
            if self.scope:
                metadata['scope'] = self.scope
            
            token_store.store_token(
                identifier=identifier,
                token=self.access_token,
                expires_at=self.token_expires_at,
                refresh_token=self.refresh_token,
                token_type=self.token_type.lower() if self.token_type else 'bearer',
                metadata=metadata
            )
            logger.debug(f"OAuth token stored in cache for identifier: {identifier}")
        except Exception as e:
            logger.warning(f"Failed to store OAuth token in cache: {e}")
            # Don't fail if caching fails - token is still valid

