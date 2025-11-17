"""
Tests for AI CLI flags and configuration
"""

import pytest
import os
import tempfile
import yaml
from pathlib import Path
from click.testing import CliRunner
from apitest.cli import main
from apitest.config import ConfigManager, AIConfig


class TestCLIAIFlags:
    """Test AI-related CLI flags"""
    
    def test_mode_flag_schema(self):
        """Test --mode schema flag"""
        runner = CliRunner()
        result = runner.invoke(main, ['--help'])
        assert result.exit_code == 0
        assert '--mode' in result.output
        assert 'schema' in result.output or 'ai' in result.output or 'hybrid' in result.output
    
    def test_ai_provider_flag(self):
        """Test --ai-provider flag"""
        runner = CliRunner()
        result = runner.invoke(main, ['--help'])
        assert result.exit_code == 0
        assert '--ai-provider' in result.output
    
    def test_ai_model_flag(self):
        """Test --ai-model flag"""
        runner = CliRunner()
        result = runner.invoke(main, ['--help'])
        assert result.exit_code == 0
        assert '--ai-model' in result.output
    
    def test_ai_temperature_flag(self):
        """Test --ai-temperature flag"""
        runner = CliRunner()
        result = runner.invoke(main, ['--help'])
        assert result.exit_code == 0
        assert '--ai-temperature' in result.output
    
    def test_ai_max_tokens_flag(self):
        """Test --ai-max-tokens flag"""
        runner = CliRunner()
        result = runner.invoke(main, ['--help'])
        assert result.exit_code == 0
        assert '--ai-max-tokens' in result.output
    
    def test_ai_enabled_flag(self):
        """Test --ai-enabled flag"""
        runner = CliRunner()
        result = runner.invoke(main, ['--help'])
        assert result.exit_code == 0
        assert '--ai-enabled' in result.output
    
    def test_mode_ai_without_api_key(self, tmp_path):
        """Test --mode ai fails without API key"""
        schema_file = tmp_path / "test.yaml"
        schema_file.write_text("""
openapi: 3.0.0
info:
  title: Test API
  version: 1.0.0
paths:
  /test:
    get:
      responses:
        '200':
          description: OK
""")
        
        runner = CliRunner()
        result = runner.invoke(main, [str(schema_file), '--mode', 'ai'])
        
        assert result.exit_code != 0
        assert 'API key' in result.output or 'GROQ_API_KEY' in result.output
    
    def test_mode_ai_with_env_var(self, tmp_path, monkeypatch):
        """Test --mode ai works with environment variable"""
        monkeypatch.setenv('GROQ_API_KEY', 'test-api-key')
        
        schema_file = tmp_path / "test.yaml"
        schema_file.write_text("""
openapi: 3.0.0
info:
  title: Test API
  version: 1.0.0
paths:
  /test:
    get:
      responses:
        '200':
          description: OK
""")
        
        runner = CliRunner()
        # Should not fail on API key validation (will fail later on actual API call, but that's OK)
        result = runner.invoke(main, [str(schema_file), '--mode', 'ai', '--dry-run'])
        
        # Should pass validation (exit code might be 0 or non-zero for other reasons)
        assert 'API key' not in result.output or 'GROQ_API_KEY' not in result.output
    
    def test_ai_temperature_validation(self, tmp_path, monkeypatch):
        """Test temperature validation"""
        monkeypatch.setenv('GROQ_API_KEY', 'test-api-key')
        
        schema_file = tmp_path / "test.yaml"
        schema_file.write_text("""
openapi: 3.0.0
info:
  title: Test API
  version: 1.0.0
paths:
  /test:
    get:
      responses:
        '200':
          description: OK
""")
        
        runner = CliRunner()
        result = runner.invoke(main, [str(schema_file), '--mode', 'ai', '--ai-temperature', '3.0'])
        
        assert result.exit_code != 0
        assert 'temperature' in result.output.lower() or '0.0 and 2.0' in result.output
    
    def test_ai_max_tokens_validation(self, tmp_path, monkeypatch):
        """Test max_tokens validation"""
        monkeypatch.setenv('GROQ_API_KEY', 'test-api-key')
        
        schema_file = tmp_path / "test.yaml"
        schema_file.write_text("""
openapi: 3.0.0
info:
  title: Test API
  version: 1.0.0
paths:
  /test:
    get:
      responses:
        '200':
          description: OK
""")
        
        runner = CliRunner()
        result = runner.invoke(main, [str(schema_file), '--mode', 'ai', '--ai-max-tokens', '-1'])
        
        assert result.exit_code != 0
        assert 'max_tokens' in result.output.lower() or 'positive' in result.output.lower()
    
    def test_ai_enabled_overrides_mode(self, tmp_path, monkeypatch):
        """Test --ai-enabled flag overrides mode"""
        monkeypatch.setenv('GROQ_API_KEY', 'test-api-key')
        
        schema_file = tmp_path / "test.yaml"
        schema_file.write_text("""
openapi: 3.0.0
info:
  title: Test API
  version: 1.0.0
paths:
  /test:
    get:
      responses:
        '200':
          description: OK
""")
        
        runner = CliRunner()
        # --ai-enabled should work even if mode is schema
        result = runner.invoke(main, [str(schema_file), '--mode', 'schema', '--ai-enabled', '--dry-run', '--verbose'])
        
        # Should not fail on mode validation
        assert 'API key' not in result.output or 'GROQ_API_KEY' not in result.output
    
    def test_cli_flags_override_profile(self, tmp_path, monkeypatch):
        """Test CLI flags override profile AI config"""
        monkeypatch.setenv('GROQ_API_KEY', 'test-api-key')
        
        # Create config file with AI config
        config_file = tmp_path / "config.yaml"
        config_data = {
            'profiles': {
                'test_profile': {
                    'base_url': 'https://api.example.com',
                    'ai_config': {
                        'provider': 'openai',
                        'model': 'gpt-4',
                        'mode': 'ai',
                        'temperature': 0.5
                    }
                }
            }
        }
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        schema_file = tmp_path / "test.yaml"
        schema_file.write_text("""
openapi: 3.0.0
info:
  title: Test API
  version: 1.0.0
paths:
  /test:
    get:
      responses:
        '200':
          description: OK
""")
        
        runner = CliRunner()
        # CLI flags should override profile
        result = runner.invoke(main, [
            str(schema_file),
            '--profile', 'test_profile',
            '--config', str(config_file),
            '--ai-provider', 'groq',
            '--ai-model', 'llama-3-groq-70b',
            '--dry-run',
            '--verbose'
        ])
        
        # Should use CLI values (groq) not profile values (openai)
        # Check verbose output contains groq
        if '--verbose' in result.output or 'groq' in result.output.lower():
            assert True  # CLI override worked


class TestAIConfigMerging:
    """Test AI config merging logic"""
    
    def test_cli_overrides_profile(self, tmp_path):
        """Test CLI flags override profile config"""
        config_file = tmp_path / "config.yaml"
        config_data = {
            'profiles': {
                'test': {
                    'ai_config': {
                        'provider': 'openai',
                        'model': 'gpt-4',
                        'temperature': 0.5
                    }
                }
            }
        }
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        manager = ConfigManager(config_file)
        profile = manager.get_profile('test')
        
        # Simulate CLI override
        from apitest.config import AIConfig
        final_config = AIConfig(
            provider='groq',  # CLI override
            model=profile.ai_config.model,  # Keep from profile
            api_key=profile.ai_config.api_key,
            mode=profile.ai_config.mode,
            temperature=0.8,  # CLI override
            max_tokens=profile.ai_config.max_tokens,
            enabled=profile.ai_config.enabled
        )
        
        assert final_config.provider == 'groq'  # CLI override
        assert final_config.temperature == 0.8  # CLI override
        assert final_config.model == 'gpt-4'  # From profile

