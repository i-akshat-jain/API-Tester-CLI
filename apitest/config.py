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
class AIConfig:
    """AI test generation configuration"""
    provider: str = "groq"  # groq, openai, anthropic
    model: str = "llama-3-groq-70b"
    api_key: Optional[str] = None
    mode: str = "schema"  # schema, ai, hybrid
    temperature: float = 0.7
    max_tokens: int = 2000
    enabled: bool = False


@dataclass
class Profile:
    """Represents an API testing profile"""
    name: str
    base_url: Optional[str] = None
    auth: Optional[Union[str, List[str], Dict[str, Any]]] = None  # Can be a string, list of strings, or OAuth config dict
    path_params: Dict[str, str] = field(default_factory=dict)
    timeout: Optional[int] = None
    description: Optional[str] = None
    ai_config: Optional[AIConfig] = None


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
            except ValueError:
                # Re-raise validation errors (don't silently skip)
                raise
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
            
            # Parse AI configuration
            ai_config = None
            ai_config_data = profile_data.get('ai_config')
            if ai_config_data:
                try:
                    ai_config = self._parse_ai_config(ai_config_data, config_path, profile_name)
                except ValueError as e:
                    # Re-raise validation errors (don't silently skip)
                    raise
                except Exception as e:
                    # Log other errors but continue (for backward compatibility)
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to parse AI config for profile '{profile_name}': {e}")
            
            profile = Profile(
                name=profile_name,
                base_url=profile_data.get('base_url'),
                auth=auth,
                path_params=path_params,
                timeout=profile_data.get('timeout'),
                description=profile_data.get('description'),
                ai_config=ai_config
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
    
    def _parse_ai_config(self, ai_config_data: Dict[str, Any], config_path: Path, profile_name: str) -> AIConfig:
        """
        Parse AI configuration from YAML
        
        Args:
            ai_config_data: Dictionary containing AI config
            config_path: Path to config file (for error messages)
            profile_name: Name of the profile (for error messages)
            
        Returns:
            AIConfig instance
            
        Raises:
            ValueError: If AI config is invalid
        """
        if not isinstance(ai_config_data, dict):
            raise ValueError(
                f"Invalid AI config in profile '{profile_name}' at {config_path}.\n"
                f"AI config must be a dictionary."
            )
        
        # Get provider (default: groq)
        provider = ai_config_data.get('provider', 'groq')
        if provider not in ['groq', 'openai', 'anthropic']:
            raise ValueError(
                f"Invalid AI provider '{provider}' in profile '{profile_name}' at {config_path}.\n"
                f"Supported providers: groq, openai, anthropic"
            )
        
        # Get API key from config or environment variable
        api_key = ai_config_data.get('api_key')
        if not api_key:
            # Try environment variable based on provider
            env_var_map = {
                'groq': 'GROQ_API_KEY',
                'openai': 'OPENAI_API_KEY',
                'anthropic': 'ANTHROPIC_API_KEY'
            }
            env_var = env_var_map.get(provider)
            if env_var:
                api_key = os.getenv(env_var)
            else:
                api_key = os.getenv('AI_API_KEY')  # Fallback
        
        # Expand environment variables if api_key is a string with $VAR
        if api_key and isinstance(api_key, str):
            api_key = self._expand_env_vars(api_key)
        
        # Get model (provider-specific defaults)
        model = ai_config_data.get('model')
        if not model:
            model_defaults = {
                'groq': 'llama-3-groq-70b',
                'openai': 'gpt-4',
                'anthropic': 'claude-3-opus-20240229'
            }
            model = model_defaults.get(provider, 'llama-3-groq-70b')
        
        # Get mode (default: schema)
        mode = ai_config_data.get('mode', 'schema')
        if mode not in ['schema', 'ai', 'hybrid']:
            raise ValueError(
                f"Invalid AI mode '{mode}' in profile '{profile_name}' at {config_path}.\n"
                f"Supported modes: schema, ai, hybrid"
            )
        
        # Get temperature (default: 0.7)
        temperature = ai_config_data.get('temperature', 0.7)
        if not isinstance(temperature, (int, float)) or temperature < 0.0 or temperature > 2.0:
            raise ValueError(
                f"Invalid temperature '{temperature}' in profile '{profile_name}' at {config_path}.\n"
                f"Temperature must be between 0.0 and 2.0"
            )
        
        # Get max_tokens (default: 2000)
        max_tokens = ai_config_data.get('max_tokens', 2000)
        if not isinstance(max_tokens, int) or max_tokens < 1:
            raise ValueError(
                f"Invalid max_tokens '{max_tokens}' in profile '{profile_name}' at {config_path}.\n"
                f"max_tokens must be a positive integer"
            )
        
        # Get enabled flag (default: False)
        enabled = ai_config_data.get('enabled', False)
        if not isinstance(enabled, bool):
            enabled = bool(enabled)
        
        return AIConfig(
            provider=provider,
            model=model,
            api_key=api_key,
            mode=mode,
            temperature=float(temperature),
            max_tokens=int(max_tokens),
            enabled=enabled
        )
    
    def get_ai_config(self, profile_name: Optional[str] = None) -> Optional[AIConfig]:
        """
        Get AI configuration for a profile or default
        
        Args:
            profile_name: Optional profile name. If None, returns default config.
            
        Returns:
            AIConfig instance or None
        """
        if profile_name:
            profile = self.get_profile(profile_name)
            if profile and profile.ai_config:
                return profile.ai_config
        
        # Return default AI config
        return AIConfig()
    
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

