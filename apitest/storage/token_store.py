"""
Encrypted token storage using system keyring

All tokens are stored locally in the system keyring (macOS Keychain, 
Windows Credential Manager, Linux Secret Service).
Never sent to external servers.
"""

import keyring
import json
import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Service name for keyring (all tokens stored under this service)
KEYRING_SERVICE = "apitest-cli"


class TokenStore:
    """Encrypted token storage using system keyring"""
    
    def __init__(self, service_name: str = KEYRING_SERVICE):
        """
        Initialize token store
        
        Args:
            service_name: Service name for keyring storage
        """
        self.service_name = service_name
        self._verify_keyring_available()
    
    def _verify_keyring_available(self):
        """Verify that keyring backend is available"""
        try:
            # Test keyring functionality
            test_key = f"__test_{os.getpid()}"
            keyring.set_password(self.service_name, test_key, "test")
            keyring.delete_password(self.service_name, test_key)
        except Exception as e:
            logger.warning(f"Keyring backend may not be available: {e}")
            logger.warning("Token caching will be disabled. Install keyring backend for your system:")
            logger.warning("  - macOS: Should work out of the box")
            logger.warning("  - Linux: Install python3-secretstorage or keyrings.alt")
            logger.warning("  - Windows: Should work out of the box")
    
    def _get_key_name(self, identifier: str) -> str:
        """
        Get keyring key name for a token identifier
        
        Args:
            identifier: Unique identifier for the token (e.g., "schema_file:base_url")
            
        Returns:
            Key name for keyring
        """
        return f"token:{identifier}"
    
    def _get_metadata_key_name(self, identifier: str) -> str:
        """Get key name for token metadata"""
        return f"metadata:{identifier}"
    
    def store_token(self, identifier: str, token: str, 
                   expires_at: Optional[datetime] = None,
                   refresh_token: Optional[str] = None,
                   token_type: str = "bearer",
                   metadata: Optional[Dict[str, Any]] = None):
        """
        Store encrypted token in system keyring
        
        Args:
            identifier: Unique identifier for the token (e.g., "schema_file:base_url")
            token: Token value to store
            expires_at: Optional expiration datetime
            refresh_token: Optional refresh token (for OAuth)
            token_type: Type of token (default: "bearer")
            metadata: Optional additional metadata
        """
        try:
            # Store token
            key_name = self._get_key_name(identifier)
            keyring.set_password(self.service_name, key_name, token)
            
            # Store metadata (including expiration and refresh token)
            metadata_key = self._get_metadata_key_name(identifier)
            metadata_dict = {
                'token_type': token_type,
                'expires_at': expires_at.isoformat() if expires_at else None,
                'refresh_token': refresh_token,  # Will be stored if provided
                'created_at': datetime.now().isoformat(),
                **(metadata or {})
            }
            metadata_json = json.dumps(metadata_dict)
            keyring.set_password(self.service_name, metadata_key, metadata_json)
            
            logger.debug(f"Token stored for identifier: {identifier}")
        except Exception as e:
            logger.error(f"Failed to store token: {e}")
            raise
    
    def get_token(self, identifier: str) -> Optional[str]:
        """
        Get token from system keyring
        
        Args:
            identifier: Unique identifier for the token
            
        Returns:
            Token value or None if not found/expired
        """
        try:
            key_name = self._get_key_name(identifier)
            token = keyring.get_password(self.service_name, key_name)
            
            if not token:
                return None
            
            # Check if token is expired
            if self.is_token_expired(identifier):
                logger.debug(f"Token expired for identifier: {identifier}")
                # Optionally delete expired token
                # self.delete_token(identifier)
                return None
            
            return token
        except Exception as e:
            logger.error(f"Failed to retrieve token: {e}")
            return None
    
    def get_token_metadata(self, identifier: str) -> Optional[Dict[str, Any]]:
        """
        Get token metadata
        
        Args:
            identifier: Unique identifier for the token
            
        Returns:
            Metadata dictionary or None if not found
        """
        try:
            metadata_key = self._get_metadata_key_name(identifier)
            metadata_json = keyring.get_password(self.service_name, metadata_key)
            
            if not metadata_json:
                return None
            
            return json.loads(metadata_json)
        except Exception as e:
            logger.error(f"Failed to retrieve token metadata: {e}")
            return None
    
    def is_token_expired(self, identifier: str) -> bool:
        """
        Check if token is expired
        
        Args:
            identifier: Unique identifier for the token
            
        Returns:
            True if token is expired, False otherwise (or if expiration not set)
        """
        metadata = self.get_token_metadata(identifier)
        if not metadata or not metadata.get('expires_at'):
            return False  # No expiration set, assume not expired
        
        try:
            expires_at = datetime.fromisoformat(metadata['expires_at'])
            return datetime.now() >= expires_at
        except (ValueError, KeyError):
            return False
    
    def get_refresh_token(self, identifier: str) -> Optional[str]:
        """
        Get refresh token if available
        
        Args:
            identifier: Unique identifier for the token
            
        Returns:
            Refresh token or None if not found
        """
        metadata = self.get_token_metadata(identifier)
        if not metadata:
            return None
        
        return metadata.get('refresh_token')
    
    def delete_token(self, identifier: str):
        """
        Delete token and metadata from keyring
        
        Args:
            identifier: Unique identifier for the token
        """
        try:
            key_name = self._get_key_name(identifier)
            metadata_key = self._get_metadata_key_name(identifier)
            
            keyring.delete_password(self.service_name, key_name)
            keyring.delete_password(self.service_name, metadata_key)
            
            logger.debug(f"Token deleted for identifier: {identifier}")
        except Exception as e:
            logger.warning(f"Failed to delete token (may not exist): {e}")
    
    def token_exists(self, identifier: str) -> bool:
        """
        Check if token exists (and is not expired)
        
        Args:
            identifier: Unique identifier for the token
            
        Returns:
            True if token exists and is not expired
        """
        token = self.get_token(identifier)
        return token is not None
    
    def list_token_identifiers(self) -> list:
        """
        List all stored token identifiers
        
        Note: This may not work with all keyring backends.
        Returns empty list if listing is not supported.
        
        Returns:
            List of token identifiers
        """
        # Most keyring backends don't support listing keys
        # This is a limitation we'll need to document
        # For now, return empty list
        logger.warning("Listing token identifiers is not supported by all keyring backends")
        return []
    
    @staticmethod
    def create_identifier(schema_file: str, base_url: str, auth_type: str = "default") -> str:
        """
        Create a unique identifier for a token
        
        Args:
            schema_file: Path or identifier for the schema file
            base_url: Base URL of the API
            auth_type: Type of authentication (e.g., "oauth2", "bearer")
            
        Returns:
            Unique identifier string
        """
        # Normalize inputs
        schema_file = os.path.abspath(schema_file) if os.path.exists(schema_file) else schema_file
        base_url = base_url.rstrip('/')
        
        return f"{schema_file}:{base_url}:{auth_type}"

