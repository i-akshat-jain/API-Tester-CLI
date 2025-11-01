"""
Authentication handler for API requests
"""

from typing import Dict, Optional


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
        if '=' not in auth_string:
            raise ValueError(f"Invalid auth format: {auth_string}. Use 'bearer=TOKEN' or 'apikey=KEY:VALUE'")
        
        parts = auth_string.split('=', 1)
        auth_type = parts[0].lower()
        auth_value = parts[1]
        
        if auth_type == 'bearer':
            self.auth_type = 'bearer'
            self.token = auth_value
        elif auth_type == 'apikey':
            # Format: apikey=KEY_NAME:KEY_VALUE or apikey=KEY_NAME:KEY_VALUE:location
            key_parts = auth_value.split(':')
            if len(key_parts) < 2:
                raise ValueError("API key format: apikey=KEY_NAME:KEY_VALUE")
            self.auth_type = 'apikey'
            self.api_key_name = key_parts[0]
            self.api_key_value = key_parts[1]
            if len(key_parts) > 2:
                self.api_key_location = key_parts[2].lower()
        elif auth_type == 'header':
            # Format: header=KEY:VALUE
            header_parts = auth_value.split(':', 1)
            if len(header_parts) < 2:
                raise ValueError("Header format: header=KEY:VALUE")
            self.auth_type = 'header'
            self.custom_headers[header_parts[0]] = header_parts[1]
        else:
            raise ValueError(f"Unsupported auth type: {auth_type}. Use 'bearer', 'apikey', or 'header'")
    
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

