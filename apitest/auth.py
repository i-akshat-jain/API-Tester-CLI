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

