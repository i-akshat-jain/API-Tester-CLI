"""
Tests for AI configuration in ConfigManager
"""

import pytest
import os
import tempfile
import yaml
from pathlib import Path
from apitest.config import ConfigManager, AIConfig, Profile


class TestAIConfig:
    """Test AIConfig dataclass"""
    
    def test_default_ai_config(self):
        """Test default AI config values"""
        config = AIConfig()
        assert config.provider == "groq"
        assert config.model == "llama-3-groq-70b"
        assert config.api_key is None
        assert config.mode == "schema"
        assert config.temperature == 0.7
        assert config.max_tokens == 2000
        assert config.enabled is False
    
    def test_custom_ai_config(self):
        """Test custom AI config"""
        config = AIConfig(
            provider="openai",
            model="gpt-4",
            api_key="test-key",
            mode="ai",
            temperature=0.9,
            max_tokens=3000,
            enabled=True
        )
        assert config.provider == "openai"
        assert config.model == "gpt-4"
        assert config.api_key == "test-key"
        assert config.mode == "ai"
        assert config.temperature == 0.9
        assert config.max_tokens == 3000
        assert config.enabled is True


class TestConfigManagerAI:
    """Test AI configuration in ConfigManager"""
    
    def test_parse_ai_config_from_yaml(self, tmp_path):
        """Test parsing AI config from YAML"""
        config_file = tmp_path / "config.yaml"
        config_data = {
            'profiles': {
                'test_profile': {
                    'base_url': 'https://api.example.com',
                    'ai_config': {
                        'provider': 'groq',
                        'model': 'llama-3-groq-70b',
                        'api_key': 'test-api-key',
                        'mode': 'ai',
                        'temperature': 0.8,
                        'max_tokens': 2500,
                        'enabled': True
                    }
                }
            }
        }
        
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        manager = ConfigManager(config_file)
        profile = manager.get_profile('test_profile')
        
        assert profile is not None
        assert profile.ai_config is not None
        assert profile.ai_config.provider == 'groq'
        assert profile.ai_config.model == 'llama-3-groq-70b'
        assert profile.ai_config.api_key == 'test-api-key'
        assert profile.ai_config.mode == 'ai'
        assert profile.ai_config.temperature == 0.8
        assert profile.ai_config.max_tokens == 2500
        assert profile.ai_config.enabled is True
    
    def test_ai_config_defaults(self, tmp_path):
        """Test AI config uses defaults when not fully specified"""
        config_file = tmp_path / "config.yaml"
        config_data = {
            'profiles': {
                'test_profile': {
                    'base_url': 'https://api.example.com',
                    'ai_config': {
                        'provider': 'openai'
                    }
                }
            }
        }
        
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        manager = ConfigManager(config_file)
        profile = manager.get_profile('test_profile')
        
        assert profile.ai_config is not None
        assert profile.ai_config.provider == 'openai'
        assert profile.ai_config.model == 'gpt-4'  # Default for openai
        assert profile.ai_config.mode == 'schema'  # Default
        assert profile.ai_config.temperature == 0.7  # Default
        assert profile.ai_config.max_tokens == 2000  # Default
        assert profile.ai_config.enabled is False  # Default
    
    def test_ai_config_from_env_var(self, tmp_path, monkeypatch):
        """Test AI config API key from environment variable"""
        monkeypatch.setenv('GROQ_API_KEY', 'env-api-key')
        
        config_file = tmp_path / "config.yaml"
        config_data = {
            'profiles': {
                'test_profile': {
                    'base_url': 'https://api.example.com',
                    'ai_config': {
                        'provider': 'groq'
                    }
                }
            }
        }
        
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        manager = ConfigManager(config_file)
        profile = manager.get_profile('test_profile')
        
        assert profile.ai_config is not None
        assert profile.ai_config.api_key == 'env-api-key'
    
    def test_ai_config_invalid_provider(self, tmp_path):
        """Test invalid AI provider raises error"""
        config_file = tmp_path / "config.yaml"
        config_data = {
            'profiles': {
                'test_profile': {
                    'ai_config': {
                        'provider': 'invalid_provider'
                    }
                }
            }
        }
        
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        with pytest.raises(ValueError, match="Invalid AI provider"):
            ConfigManager(config_file)
    
    def test_ai_config_invalid_mode(self, tmp_path):
        """Test invalid AI mode raises error"""
        config_file = tmp_path / "config.yaml"
        config_data = {
            'profiles': {
                'test_profile': {
                    'ai_config': {
                        'mode': 'invalid_mode'
                    }
                }
            }
        }
        
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        with pytest.raises(ValueError, match="Invalid AI mode"):
            ConfigManager(config_file)
    
    def test_ai_config_invalid_temperature(self, tmp_path):
        """Test invalid temperature raises error"""
        config_file = tmp_path / "config.yaml"
        config_data = {
            'profiles': {
                'test_profile': {
                    'ai_config': {
                        'temperature': 3.0  # Out of range
                    }
                }
            }
        }
        
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        with pytest.raises(ValueError, match="Invalid temperature"):
            ConfigManager(config_file)
    
    def test_ai_config_invalid_max_tokens(self, tmp_path):
        """Test invalid max_tokens raises error"""
        config_file = tmp_path / "config.yaml"
        config_data = {
            'profiles': {
                'test_profile': {
                    'ai_config': {
                        'max_tokens': -1  # Invalid
                    }
                }
            }
        }
        
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        with pytest.raises(ValueError, match="Invalid max_tokens"):
            ConfigManager(config_file)
    
    def test_get_ai_config_from_profile(self, tmp_path):
        """Test getting AI config from profile"""
        config_file = tmp_path / "config.yaml"
        config_data = {
            'profiles': {
                'test_profile': {
                    'ai_config': {
                        'provider': 'anthropic',
                        'mode': 'hybrid'
                    }
                }
            }
        }
        
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        manager = ConfigManager(config_file)
        ai_config = manager.get_ai_config('test_profile')
        
        assert ai_config is not None
        assert ai_config.provider == 'anthropic'
        assert ai_config.mode == 'hybrid'
    
    def test_get_ai_config_default(self):
        """Test getting default AI config when no profile"""
        manager = ConfigManager()
        ai_config = manager.get_ai_config()
        
        assert ai_config is not None
        assert isinstance(ai_config, AIConfig)
        assert ai_config.provider == 'groq'
        assert ai_config.mode == 'schema'
    
    def test_profile_without_ai_config(self, tmp_path):
        """Test profile without AI config"""
        config_file = tmp_path / "config.yaml"
        config_data = {
            'profiles': {
                'test_profile': {
                    'base_url': 'https://api.example.com'
                }
            }
        }
        
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        manager = ConfigManager(config_file)
        profile = manager.get_profile('test_profile')
        
        assert profile is not None
        assert profile.ai_config is None

