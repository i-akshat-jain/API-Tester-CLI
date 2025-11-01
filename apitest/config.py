"""
Configuration manager for API Tester CLI profiles
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Union, List
from dataclasses import dataclass, field


@dataclass
class Profile:
    """Represents an API testing profile"""
    name: str
    base_url: Optional[str] = None
    auth: Optional[Union[str, List[str]]] = None  # Can be a string or list of strings (for multiple auth attempts)
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
            
            # Expand environment variables in auth and path_params
            # Support both single auth string and list of auth strings (for multiple attempts)
            auth = profile_data.get('auth')
            if auth:
                if isinstance(auth, list):
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

