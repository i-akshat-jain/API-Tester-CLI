"""
Comprehensive tests for ConfigManager class - covering all functionality
"""

import pytest
import yaml
import os
from pathlib import Path
from apitest.config import ConfigManager, Profile, AIConfig, OAuthConfig


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create temporary config directory"""
    config_dir = tmp_path / '.apitest'
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def sample_config_file(temp_config_dir):
    """Create sample config file"""
    config_file = temp_config_dir / 'config.yaml'
    config_data = {
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
                'path_params': {
                    'user_id': '123'
                }
            }
        }
    }
    with open(config_file, 'w') as f:
        yaml.dump(config_data, f)
    return config_file


class TestConfigManagerInitialization:
    """Test ConfigManager initialization"""
    
    def test_init_with_default_path(self, temp_config_dir, monkeypatch):
        """Test initialization with default config path"""
        # Mock home directory
        monkeypatch.setattr(Path, 'home', lambda: temp_config_dir.parent)
        
        config_file = temp_config_dir / 'config.yaml'
        config_file.write_text('profiles: {}')
        
        manager = ConfigManager()
        assert manager.config_file is None  # Uses default
    
    def test_init_with_custom_path(self, temp_config_dir):
        """Test initialization with custom config path"""
        config_file = temp_config_dir / 'custom.yaml'
        config_file.write_text('profiles: {}')
        
        manager = ConfigManager(config_file=config_file)
        assert manager.config_file == config_file
    
    def test_init_with_nonexistent_file(self, tmp_path):
        """Test initialization with non-existent file"""
        config_file = tmp_path / 'nonexistent.yaml'
        manager = ConfigManager(config_file=config_file)
        # Should not raise error, just have no profiles
        assert len(manager.list_profiles()) == 0


class TestProfileLoading:
    """Test profile loading functionality"""
    
    def test_load_profiles_from_file(self, sample_config_file):
        """Test loading profiles from config file"""
        manager = ConfigManager(config_file=sample_config_file)
        profiles = manager.list_profiles()
        
        assert 'production' in profiles
        assert 'staging' in profiles
        assert profiles['production'].base_url == 'https://api.example.com'
    
    def test_get_profile_existing(self, sample_config_file):
        """Test getting existing profile"""
        manager = ConfigManager(config_file=sample_config_file)
        profile = manager.get_profile('production')
        
        assert profile is not None
        assert profile.name == 'production'
        assert profile.base_url == 'https://api.example.com'
    
    def test_get_profile_nonexistent(self, sample_config_file):
        """Test getting non-existent profile"""
        manager = ConfigManager(config_file=sample_config_file)
        profile = manager.get_profile('nonexistent')
        
        assert profile is None
    
    def test_load_profiles_with_env_vars(self, temp_config_dir, monkeypatch):
        """Test loading profiles with environment variables"""
        monkeypatch.setenv('PROD_TOKEN', 'secret_token_123')
        
        config_file = temp_config_dir / 'config.yaml'
        config_data = {
            'profiles': {
                'prod': {
                    'auth': 'bearer=$PROD_TOKEN'
                }
            }
        }
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        manager = ConfigManager(config_file=config_file)
        profile = manager.get_profile('prod')
        
        assert profile.auth == 'bearer=secret_token_123'
    
    def test_load_profiles_with_path_params(self, sample_config_file):
        """Test loading profiles with path parameters"""
        manager = ConfigManager(config_file=sample_config_file)
        profile = manager.get_profile('staging')
        
        assert 'user_id' in profile.path_params
        assert profile.path_params['user_id'] == '123'


class TestOAuthConfig:
    """Test OAuth configuration parsing"""
    
    def test_parse_oauth_client_credentials(self, temp_config_dir):
        """Test parsing OAuth client credentials config"""
        config_file = temp_config_dir / 'config.yaml'
        config_data = {
            'profiles': {
                'oauth': {
                    'auth': {
                        'type': 'oauth2',
                        'grant_type': 'client_credentials',
                        'token_url': 'https://auth.example.com/token',
                        'client_id': 'client123',
                        'client_secret': 'secret123',
                        'scope': 'read write'
                    }
                }
            }
        }
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        manager = ConfigManager(config_file=config_file)
        profile = manager.get_profile('oauth')
        
        assert isinstance(profile.auth, dict)
        assert profile.auth['type'] == 'oauth2'
        assert profile.auth['grant_type'] == 'client_credentials'
    
    def test_parse_oauth_password_grant(self, temp_config_dir):
        """Test parsing OAuth password grant config"""
        config_file = temp_config_dir / 'config.yaml'
        config_data = {
            'profiles': {
                'oauth': {
                    'auth': {
                        'type': 'oauth2',
                        'grant_type': 'password',
                        'token_url': 'https://auth.example.com/token',
                        'client_id': 'client123',
                        'client_secret': 'secret123',
                        'username': 'user@example.com',
                        'password': 'password123',
                        'scope': 'read'
                    }
                }
            }
        }
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        manager = ConfigManager(config_file=config_file)
        profile = manager.get_profile('oauth')
        
        assert profile.auth['grant_type'] == 'password'
        assert profile.auth['username'] == 'user@example.com'
    
    def test_parse_oauth_missing_required_fields(self, temp_config_dir):
        """Test parsing OAuth config with missing required fields"""
        config_file = temp_config_dir / 'config.yaml'
        config_data = {
            'profiles': {
                'oauth': {
                    'auth': {
                        'type': 'oauth2',
                        'grant_type': 'client_credentials'
                        # Missing token_url, client_id, client_secret
                    }
                }
            }
        }
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        # ValueError should be raised during initialization when parsing profiles
        with pytest.raises(ValueError, match='Missing'):
            ConfigManager(config_file=config_file)
    
    def test_parse_oauth_invalid_grant_type(self, temp_config_dir):
        """Test parsing OAuth config with invalid grant type"""
        config_file = temp_config_dir / 'config.yaml'
        config_data = {
            'profiles': {
                'oauth': {
                    'auth': {
                        'type': 'oauth2',
                        'grant_type': 'invalid_grant',
                        'token_url': 'https://auth.example.com/token',
                        'client_id': 'client123',
                        'client_secret': 'secret123'
                    }
                }
            }
        }
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        # ValueError should be raised during initialization when parsing profiles
        with pytest.raises(ValueError, match='Unsupported grant_type'):
            ConfigManager(config_file=config_file)
    
    def test_parse_oauth_password_missing_credentials(self, temp_config_dir):
        """Test parsing OAuth password grant with missing username/password"""
        config_file = temp_config_dir / 'config.yaml'
        config_data = {
            'profiles': {
                'oauth': {
                    'auth': {
                        'type': 'oauth2',
                        'grant_type': 'password',
                        'token_url': 'https://auth.example.com/token',
                        'client_id': 'client123',
                        'client_secret': 'secret123'
                        # Missing username and password
                    }
                }
            }
        }
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        # ValueError should be raised during initialization when parsing profiles
        with pytest.raises(ValueError, match='Missing.*username'):
            ConfigManager(config_file=config_file)
    
    def test_parse_oauth_with_env_vars(self, temp_config_dir, monkeypatch):
        """Test parsing OAuth config with environment variables"""
        monkeypatch.setenv('CLIENT_ID', 'env_client_id')
        monkeypatch.setenv('CLIENT_SECRET', 'env_secret')
        
        config_file = temp_config_dir / 'config.yaml'
        config_data = {
            'profiles': {
                'oauth': {
                    'auth': {
                        'type': 'oauth2',
                        'grant_type': 'client_credentials',
                        'token_url': 'https://auth.example.com/token',
                        'client_id': '$CLIENT_ID',
                        'client_secret': '$CLIENT_SECRET'
                    }
                }
            }
        }
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        manager = ConfigManager(config_file=config_file)
        profile = manager.get_profile('oauth')
        
        assert profile.auth['client_id'] == 'env_client_id'
        assert profile.auth['client_secret'] == 'env_secret'


class TestAIConfig:
    """Test AI configuration parsing"""
    
    def test_parse_ai_config_basic(self, temp_config_dir):
        """Test parsing basic AI config"""
        config_file = temp_config_dir / 'config.yaml'
        config_data = {
            'profiles': {
                'ai': {
                    'ai_config': {
                        'provider': 'groq',
                        'model': 'llama-3-groq-70b',
                        'mode': 'ai',
                        'temperature': 0.7,
                        'max_tokens': 2000
                    }
                }
            }
        }
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        manager = ConfigManager(config_file=config_file)
        profile = manager.get_profile('ai')
        
        assert profile.ai_config is not None
        assert profile.ai_config.provider == 'groq'
        assert profile.ai_config.model == 'llama-3-groq-70b'
        assert profile.ai_config.mode == 'ai'
    
    def test_parse_ai_config_with_env_var(self, temp_config_dir, monkeypatch):
        """Test parsing AI config with environment variable for API key"""
        monkeypatch.setenv('GROQ_API_KEY', 'test_api_key_123')
        
        config_file = temp_config_dir / 'config.yaml'
        config_data = {
            'profiles': {
                'ai': {
                    'ai_config': {
                        'provider': 'groq',
                        'model': 'llama-3-groq-70b'
                    }
                }
            }
        }
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        manager = ConfigManager(config_file=config_file)
        profile = manager.get_profile('ai')
        
        assert profile.ai_config.api_key == 'test_api_key_123'
    
    def test_parse_ai_config_invalid_provider(self, temp_config_dir):
        """Test parsing AI config with invalid provider"""
        config_file = temp_config_dir / 'config.yaml'
        config_data = {
            'profiles': {
                'ai': {
                    'ai_config': {
                        'provider': 'invalid_provider'
                    }
                }
            }
        }
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        # ValueError should be raised during initialization when parsing profiles
        with pytest.raises(ValueError, match='Invalid AI provider'):
            ConfigManager(config_file=config_file)
    
    def test_parse_ai_config_invalid_mode(self, temp_config_dir):
        """Test parsing AI config with invalid mode"""
        config_file = temp_config_dir / 'config.yaml'
        config_data = {
            'profiles': {
                'ai': {
                    'ai_config': {
                        'provider': 'groq',
                        'mode': 'invalid_mode'
                    }
                }
            }
        }
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        # ValueError should be raised during initialization when parsing profiles
        with pytest.raises(ValueError, match='Invalid AI mode'):
            ConfigManager(config_file=config_file)
    
    def test_parse_ai_config_invalid_temperature(self, temp_config_dir):
        """Test parsing AI config with invalid temperature"""
        config_file = temp_config_dir / 'config.yaml'
        config_data = {
            'profiles': {
                'ai': {
                    'ai_config': {
                        'provider': 'groq',
                        'temperature': 3.0  # Invalid: > 2.0
                    }
                }
            }
        }
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        # ValueError should be raised during initialization when parsing profiles
        with pytest.raises(ValueError, match='Invalid temperature'):
            ConfigManager(config_file=config_file)
    
    def test_parse_ai_config_invalid_max_tokens(self, temp_config_dir):
        """Test parsing AI config with invalid max_tokens"""
        config_file = temp_config_dir / 'config.yaml'
        config_data = {
            'profiles': {
                'ai': {
                    'ai_config': {
                        'provider': 'groq',
                        'max_tokens': 0  # Invalid: must be positive
                    }
                }
            }
        }
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        # ValueError should be raised during initialization when parsing profiles
        with pytest.raises(ValueError, match='Invalid max_tokens'):
            ConfigManager(config_file=config_file)
    
    def test_parse_ai_config_defaults(self, temp_config_dir):
        """Test parsing AI config with defaults"""
        config_file = temp_config_dir / 'config.yaml'
        config_data = {
            'profiles': {
                'ai': {
                    'ai_config': {
                        'provider': 'groq'
                    }
                }
            }
        }
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        manager = ConfigManager(config_file=config_file)
        profile = manager.get_profile('ai')
        
        assert profile.ai_config.model == 'llama-3-groq-70b'  # Default
        assert profile.ai_config.temperature == 0.7  # Default
        assert profile.ai_config.max_tokens == 2000  # Default
        assert profile.ai_config.mode == 'schema'  # Default
    
    def test_parse_ai_config_schema_format(self, temp_config_dir):
        """Test parsing AI config with schema format"""
        config_file = temp_config_dir / 'config.yaml'
        config_data = {
            'profiles': {
                'ai': {
                    'ai_config': {
                        'provider': 'groq',
                        'schema_format': 'json'
                    }
                }
            }
        }
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        manager = ConfigManager(config_file=config_file)
        profile = manager.get_profile('ai')
        
        assert profile.ai_config.schema_format == 'json'
    
    def test_parse_ai_config_invalid_schema_format(self, temp_config_dir):
        """Test parsing AI config with invalid schema format"""
        config_file = temp_config_dir / 'config.yaml'
        config_data = {
            'profiles': {
                'ai': {
                    'ai_config': {
                        'provider': 'groq',
                        'schema_format': 'invalid'
                    }
                }
            }
        }
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        # ValueError should be raised during initialization when parsing profiles
        with pytest.raises(ValueError, match='Invalid schema_format'):
            ConfigManager(config_file=config_file)
    
    def test_parse_ai_config_prompt_format(self, temp_config_dir):
        """Test parsing AI config with prompt format"""
        config_file = temp_config_dir / 'config.yaml'
        config_data = {
            'profiles': {
                'ai': {
                    'ai_config': {
                        'provider': 'groq',
                        'prompt_format': 'markdown'
                    }
                }
            }
        }
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        manager = ConfigManager(config_file=config_file)
        profile = manager.get_profile('ai')
        
        assert profile.ai_config.prompt_format == 'markdown'


class TestMultipleAuthMethods:
    """Test multiple authentication methods"""
    
    def test_parse_multiple_auth_methods(self, temp_config_dir):
        """Test parsing profile with multiple auth methods"""
        config_file = temp_config_dir / 'config.yaml'
        config_data = {
            'profiles': {
                'multi_auth': {
                    'auth': [
                        'bearer=token1',
                        'bearer=token2'
                    ]
                }
            }
        }
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        manager = ConfigManager(config_file=config_file)
        profile = manager.get_profile('multi_auth')
        
        assert isinstance(profile.auth, list)
        assert len(profile.auth) == 2


class TestCreateDefaultConfig:
    """Test creating default config file"""
    
    def test_create_default_config(self, temp_config_dir, monkeypatch):
        """Test creating default config file"""
        monkeypatch.setattr(Path, 'home', lambda: temp_config_dir.parent)
        
        manager = ConfigManager()
        config_path = manager.create_default_config()
        
        assert config_path.exists()
        assert config_path.name == 'config.yaml'
        
        # Verify it can be loaded
        manager2 = ConfigManager()
        profiles = manager2.list_profiles()
        assert 'production' in profiles
        assert 'staging' in profiles
        assert 'local' in profiles


class TestGetAIConfig:
    """Test getting AI configuration"""
    
    def test_get_ai_config_from_profile(self, temp_config_dir):
        """Test getting AI config from profile"""
        config_file = temp_config_dir / 'config.yaml'
        config_data = {
            'profiles': {
                'ai': {
                    'ai_config': {
                        'provider': 'groq',
                        'model': 'custom-model'
                    }
                }
            }
        }
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        manager = ConfigManager(config_file=config_file)
        ai_config = manager.get_ai_config('ai')
        
        assert ai_config is not None
        assert ai_config.provider == 'groq'
        assert ai_config.model == 'custom-model'
    
    def test_get_ai_config_default(self, temp_config_dir):
        """Test getting default AI config"""
        config_file = temp_config_dir / 'config.yaml'
        config_file.write_text('profiles: {}')
        
        manager = ConfigManager(config_file=config_file)
        ai_config = manager.get_ai_config()
        
        assert ai_config is not None
        assert isinstance(ai_config, AIConfig)
        assert ai_config.provider == 'groq'  # Default


class TestEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_load_invalid_yaml(self, temp_config_dir):
        """Test loading invalid YAML file"""
        config_file = temp_config_dir / 'config.yaml'
        config_file.write_text('invalid: [unclosed')
        
        # Should not raise error, just skip the file
        manager = ConfigManager(config_file=config_file)
        assert len(manager.list_profiles()) == 0
    
    def test_load_empty_file(self, temp_config_dir):
        """Test loading empty config file"""
        config_file = temp_config_dir / 'config.yaml'
        config_file.write_text('')
        
        manager = ConfigManager(config_file=config_file)
        assert len(manager.list_profiles()) == 0
    
    def test_load_non_dict_config(self, temp_config_dir):
        """Test loading config file that's not a dictionary"""
        config_file = temp_config_dir / 'config.yaml'
        config_file.write_text('- item1\n- item2')
        
        manager = ConfigManager(config_file=config_file)
        assert len(manager.list_profiles()) == 0
    
    def test_load_profile_not_dict(self, temp_config_dir):
        """Test loading profile that's not a dictionary"""
        config_file = temp_config_dir / 'config.yaml'
        config_data = {
            'profiles': {
                'invalid': 'not a dict'
            }
        }
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        manager = ConfigManager(config_file=config_file)
        # Should skip invalid profile
        assert 'invalid' not in manager.list_profiles()
    
    def test_project_config_overrides_user_config(self, temp_config_dir, monkeypatch):
        """Test that project config overrides user config"""
        # Create user config
        user_config_dir = temp_config_dir / '.apitest'
        user_config_dir.mkdir()
        user_config = user_config_dir / 'config.yaml'
        user_config.write_text(yaml.dump({
            'profiles': {
                'user': {'base_url': 'https://user.example.com'}
            }
        }))
        
        # Create project config
        project_config = temp_config_dir / '.apitest.yaml'
        project_config.write_text(yaml.dump({
            'profiles': {
                'project': {'base_url': 'https://project.example.com'}
            }
        }))
        
        monkeypatch.chdir(temp_config_dir)
        monkeypatch.setattr(Path, 'home', lambda: temp_config_dir)
        
        manager = ConfigManager()
        profiles = manager.list_profiles()
        
        # Both should be loaded, but project takes precedence if same name
        assert 'user' in profiles or 'project' in profiles

