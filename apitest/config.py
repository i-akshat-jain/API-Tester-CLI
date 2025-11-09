"""
Configuration manager for API Tester CLI profiles
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Union, List
from dataclasses import dataclass, field


@dataclass
class OAuthConfig:
    """OAuth 2.0 configuration"""
    grant_type: str  # 'client_credentials' or 'password'
    token_url: str
    client_id: str
    client_secret: str
    type: str = "oauth2"
    username: Optional[str] = None  # For password grant
    password: Optional[str] = None  # For password grant
    scope: Optional[str] = None


@dataclass
class Profile:
    """Represents an API testing profile"""
    name: str
    base_url: Optional[str] = None
    auth: Optional[Union[str, List[str], Dict[str, Any]]] = None  # Can be a string, list of strings, or OAuth config dict
    path_params: Dict[str, str] = field(default_factory=dict)
    timeout: Optional[int] = None
    description: Optional[str] = None


class ConfigManager:
    """Manage profiles from configuration files"""
    
    DEFAULT_CONFIG_DIR = Path.home() / '.apitest'
    DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / 'config.yaml'
    PROJECT_CONFIG_FILE = Path('.apitest.yaml')  # Project-level config
    
    def __init__(self, config_file: Optional[Path] = None):
        """
        Initialize config manager
        
        Args:
            config_file: Optional path to config file. If None, uses default locations.
        """
        self.config_file = config_file
        self.profiles: Dict[str, Profile] = {}
        self._load_config()
    
    def _load_config(self):
        """Load profiles from config file(s)"""
        config_paths = []
        
        # Project-level config takes precedence
        if Path(self.PROJECT_CONFIG_FILE).exists():
            config_paths.append(self.PROJECT_CONFIG_FILE)
        
        # User config file if specified
        if self.config_file:
            if self.config_file.exists():
                config_paths.append(self.config_file)
        else:
            # Default user config
            if self.DEFAULT_CONFIG_FILE.exists():
                config_paths.append(self.DEFAULT_CONFIG_FILE)
        
        # Load from all found config files (project config overrides user config)
        for config_path in config_paths:
            try:
                with open(config_path, 'r') as f:
                    config_data = yaml.safe_load(f) or {}
                    self._parse_profiles(config_data, config_path)
            except Exception as e:
                # Silently skip if config file has issues (user might not have created one)
                pass
    
    def _parse_profiles(self, config_data: Dict[str, Any], config_path: Path):
        """
        Parse profiles from config data
        
        Args:
            config_data: Parsed YAML data
            config_path: Path to config file (for error messages)
        """
        if not isinstance(config_data, dict):
            return
        
        profiles_section = config_data.get('profiles', {})
        
        for profile_name, profile_data in profiles_section.items():
            if not isinstance(profile_data, dict):
                continue
            
            # Parse auth configuration
            # Support: string, list of strings, or OAuth config dict
            auth = profile_data.get('auth')
            if auth:
                if isinstance(auth, dict):
                    # OAuth 2.0 configuration
                    auth = self._parse_oauth_config(auth, config_path, profile_name)
                elif isinstance(auth, list):
                    # Expand env vars for each auth string in the list
                    auth = [self._expand_env_vars(str(a)) for a in auth]
                elif isinstance(auth, str):
                    auth = self._expand_env_vars(auth)
            
            path_params = {}
            for key, value in profile_data.get('path_params', {}).items():
                if isinstance(value, str):
                    path_params[key] = self._expand_env_vars(value)
                else:
                    path_params[key] = value
            
            profile = Profile(
                name=profile_name,
                base_url=profile_data.get('base_url'),
                auth=auth,
                path_params=path_params,
                timeout=profile_data.get('timeout'),
                description=profile_data.get('description')
            )
            
            self.profiles[profile_name] = profile
    
    def _expand_env_vars(self, value: Any) -> str:
        """Expand environment variables in string"""
        if not isinstance(value, str):
            value = str(value)
        # Support both $VAR and ${VAR} syntax
        import re
        
        def replace_var(match):
            var_name = match.group(1) or match.group(2)
            return os.getenv(var_name, match.group(0))
        
        # Match $VAR or ${VAR}
        return re.sub(r'\$(\w+|\{(\w+)\})', replace_var, value)
    
    def _parse_oauth_config(self, auth_dict: Dict[str, Any], config_path: Path, profile_name: str) -> Dict[str, Any]:
        """
        Parse OAuth 2.0 configuration from YAML
        
        Args:
            auth_dict: Dictionary containing OAuth config
            config_path: Path to config file (for error messages)
            profile_name: Name of the profile (for error messages)
            
        Returns:
            Dictionary with parsed and validated OAuth config
            
        Raises:
            ValueError: If OAuth config is invalid
        """
        # Validate that it's an OAuth config
        if auth_dict.get('type') != 'oauth2':
            raise ValueError(
                f"Invalid auth config in profile '{profile_name}' at {config_path}.\n"
                f"Expected 'type: oauth2' for OAuth configuration, got: {auth_dict.get('type')}"
            )
        
        # Required fields
        grant_type = auth_dict.get('grant_type')
        if not grant_type:
            raise ValueError(
                f"Missing 'grant_type' in OAuth config for profile '{profile_name}' at {config_path}.\n"
                f"Supported grant types: 'client_credentials', 'password'"
            )
        
        if grant_type not in ['client_credentials', 'password']:
            raise ValueError(
                f"Unsupported grant_type '{grant_type}' in OAuth config for profile '{profile_name}' at {config_path}.\n"
                f"Supported grant types: 'client_credentials', 'password'"
            )
        
        token_url = auth_dict.get('token_url')
        if not token_url:
            raise ValueError(
                f"Missing 'token_url' in OAuth config for profile '{profile_name}' at {config_path}."
            )
        
        client_id = auth_dict.get('client_id')
        if not client_id:
            raise ValueError(
                f"Missing 'client_id' in OAuth config for profile '{profile_name}' at {config_path}."
            )
        
        client_secret = auth_dict.get('client_secret')
        if not client_secret:
            raise ValueError(
                f"Missing 'client_secret' in OAuth config for profile '{profile_name}' at {config_path}."
            )
        
        # Expand environment variables in OAuth config fields
        token_url = self._expand_env_vars(token_url)
        client_id = self._expand_env_vars(client_id)
        client_secret = self._expand_env_vars(client_secret)
        
        # Build OAuth config dict
        oauth_config = {
            'type': 'oauth2',
            'grant_type': grant_type,
            'token_url': token_url,
            'client_id': client_id,
            'client_secret': client_secret
        }
        
        # Optional fields
        if 'scope' in auth_dict:
            oauth_config['scope'] = self._expand_env_vars(str(auth_dict['scope']))
        
        # For password grant, username and password are required
        if grant_type == 'password':
            username = auth_dict.get('username')
            password = auth_dict.get('password')
            
            if not username:
                raise ValueError(
                    f"Missing 'username' in OAuth config for profile '{profile_name}' at {config_path}.\n"
                    f"'username' is required for 'password' grant type."
                )
            if not password:
                raise ValueError(
                    f"Missing 'password' in OAuth config for profile '{profile_name}' at {config_path}.\n"
                    f"'password' is required for 'password' grant type."
                )
            
            oauth_config['username'] = self._expand_env_vars(username)
            oauth_config['password'] = self._expand_env_vars(password)
        
        return oauth_config
    
    def get_profile(self, profile_name: str) -> Optional[Profile]:
        """
        Get a profile by name
        
        Args:
            profile_name: Name of the profile
            
        Returns:
            Profile object or None if not found
        """
        return self.profiles.get(profile_name)
    
    def list_profiles(self) -> Dict[str, Profile]:
        """Get all available profiles"""
        return self.profiles.copy()
    
    def create_default_config(self) -> Path:
        """
        Create a default config file with example profiles
        
        Returns:
            Path to created config file
        """
        self.DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        
        example_config = {
            'profiles': {
                'production': {
                    'description': 'Production API',
                    'base_url': 'https://api.example.com',
                    'auth': 'bearer=$PROD_TOKEN',
                    'timeout': 30
                },
                'staging': {
                    'description': 'Staging API',
                    'base_url': 'https://staging.api.example.com',
                    'auth': 'bearer=$STAGING_TOKEN',
                    'timeout': 30
                },
                'local': {
                    'description': 'Local development',
                    'base_url': 'http://localhost:8000',
                    'auth': 'bearer=$LOCAL_TOKEN',
                    'path_params': {
                        'user_id': '123',
                        'account_id': '456'
                    }
                }
            }
        }
        
        with open(self.DEFAULT_CONFIG_FILE, 'w') as f:
            yaml.dump(example_config, f, default_flow_style=False, sort_keys=False)
        
        return self.DEFAULT_CONFIG_FILE
    
    @staticmethod
    def get_config_file_path(config_file: Optional[str] = None) -> Optional[Path]:
        """
        Get the config file path to use
        
        Args:
            config_file: Optional config file path from CLI
            
        Returns:
            Path to config file or None
        """
        if config_file:
            return Path(config_file)
        
        # Check project-level first
        if Path(ConfigManager.PROJECT_CONFIG_FILE).exists():
            return Path(ConfigManager.PROJECT_CONFIG_FILE)
        
        # Then user config
        if ConfigManager.DEFAULT_CONFIG_FILE.exists():
            return ConfigManager.DEFAULT_CONFIG_FILE
        
        return None

