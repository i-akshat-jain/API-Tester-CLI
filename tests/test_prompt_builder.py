"""
Tests for prompt builder
"""

import pytest
import json
from unittest.mock import Mock, MagicMock
from apitest.ai.prompt_builder import (
    PromptBuilder,
    DEFAULT_BASIC_PROMPT,
    DEFAULT_ADVANCED_PROMPT,
    DEFAULT_EDGE_CASES_PROMPT,
    initialize_default_prompts
)


class TestPromptBuilder:
    """Test PromptBuilder class"""
    
    def test_init_without_storage(self):
        """Test PromptBuilder initialization without storage"""
        builder = PromptBuilder()
        assert builder.storage is None
        assert builder._default_templates is not None
        assert PromptBuilder.TEMPLATE_BASIC in builder._default_templates
    
    def test_init_with_storage(self):
        """Test PromptBuilder initialization with storage"""
        storage = Mock()
        builder = PromptBuilder(storage)
        assert builder.storage == storage
    
    def test_build_prompt_basic_template(self):
        """Test building a prompt with basic template"""
        builder = PromptBuilder()
        
        context = {
            'history': {
                'count': 10,
                'success_rate': 0.9,
                'common_status_codes': {'200': 8, '404': 2},
                'recent_results': []
            },
            'validated_examples': [],
            'patterns': []
        }
        
        endpoint_info = {
            'method': 'POST',
            'path': '/api/users',
            'summary': 'Create a new user',
            'description': 'Creates a new user account',
            'operation_id': 'createUser',
            'tags': ['users'],
            'request_schema': {
                'type': 'object',
                'properties': {
                    'name': {'type': 'string'},
                    'email': {'type': 'string'}
                }
            },
            'response_schemas': {
                '201': {'type': 'object', 'properties': {'id': {'type': 'integer'}}}
            },
            'parameters': []
        }
        
        prompt = builder.build_prompt(context, endpoint_info, PromptBuilder.TEMPLATE_BASIC)
        
        assert 'POST' in prompt
        assert '/api/users' in prompt
        assert 'Create a new user' in prompt
        assert 'test_cases' in prompt.lower()
    
    def test_build_prompt_advanced_template(self):
        """Test building a prompt with advanced template"""
        builder = PromptBuilder()
        
        context = {
            'history': {
                'count': 20,
                'success_rate': 0.85,
                'common_status_codes': {'200': 15, '400': 3, '500': 2},
                'recent_results': [
                    {'status': 'success', 'status_code': 200, 'response_time_ms': 150}
                ]
            },
            'validated_examples': [
                {
                    'test_scenario': 'Create user with valid data',
                    'request_body': {'name': 'John', 'email': 'john@example.com'},
                    'validation_status': 'approved'
                }
            ],
            'patterns': [
                {
                    'pattern_type': 'email_format',
                    'pattern_data': {'format': 'email'},
                    'effectiveness': 0.9
                }
            ]
        }
        
        endpoint_info = {
            'method': 'POST',
            'path': '/api/users',
            'summary': 'Create user',
            'description': 'Creates a new user',
            'operation_id': 'createUser',
            'tags': ['users'],
            'request_schema': {'type': 'object'},
            'response_schemas': {'201': {}},
            'parameters': [
                {'name': 'Authorization', 'in': 'header', 'required': True, 'schema': {'type': 'string'}}
            ]
        }
        
        prompt = builder.build_prompt(context, endpoint_info, PromptBuilder.TEMPLATE_ADVANCED)
        
        assert 'POST' in prompt
        assert 'Happy path' in prompt or 'edge cases' in prompt.lower()
        assert 'validated examples' in prompt.lower() or 'Example' in prompt
        assert 'patterns' in prompt.lower()
    
    def test_build_prompt_edge_cases_template(self):
        """Test building a prompt with edge cases template"""
        builder = PromptBuilder()
        
        context = {
            'history': {
                'count': 15,
                'success_rate': 0.8,
                'common_status_codes': {'200': 10, '400': 5},
                'recent_results': []
            },
            'validated_examples': [],
            'patterns': []
        }
        
        endpoint_info = {
            'method': 'POST',
            'path': '/api/users',
            'summary': 'Create user',
            'description': 'Creates a new user',
            'operation_id': 'createUser',
            'tags': [],
            'request_schema': {'type': 'object'},
            'response_schemas': {'400': {}},
            'parameters': []
        }
        
        prompt = builder.build_prompt(context, endpoint_info, PromptBuilder.TEMPLATE_EDGE_CASES)
        
        assert 'edge case' in prompt.lower() or 'error scenario' in prompt.lower()
        assert 'boundary' in prompt.lower() or 'invalid' in prompt.lower()
    
    def test_load_template_from_storage(self):
        """Test loading template from storage"""
        storage = Mock()
        storage.ai_prompts = Mock()
        storage.ai_prompts.get_active_prompt = Mock(return_value={
            'prompt_template': 'Custom template from storage: {method} {path}'
        })
        
        builder = PromptBuilder(storage)
        template = builder._load_template(PromptBuilder.TEMPLATE_BASIC)
        
        assert template == 'Custom template from storage: {method} {path}'
        storage.ai_prompts.get_active_prompt.assert_called_once_with(PromptBuilder.TEMPLATE_BASIC)
    
    def test_load_template_fallback_to_latest(self):
        """Test fallback to latest version if no active prompt"""
        storage = Mock()
        storage.ai_prompts = Mock()
        storage.ai_prompts.get_active_prompt = Mock(return_value=None)
        storage.ai_prompts.get_latest_prompt = Mock(return_value={
            'prompt_template': 'Latest template: {method}'
        })
        
        builder = PromptBuilder(storage)
        template = builder._load_template(PromptBuilder.TEMPLATE_BASIC)
        
        assert template == 'Latest template: {method}'
        storage.ai_prompts.get_active_prompt.assert_called_once()
        storage.ai_prompts.get_latest_prompt.assert_called_once()
    
    def test_load_template_fallback_to_default(self):
        """Test fallback to default template if not in storage"""
        storage = Mock()
        storage.ai_prompts = Mock()
        storage.ai_prompts.get_active_prompt = Mock(return_value=None)
        storage.ai_prompts.get_latest_prompt = Mock(return_value=None)
        
        builder = PromptBuilder(storage)
        template = builder._load_template(PromptBuilder.TEMPLATE_BASIC)
        
        assert template == DEFAULT_BASIC_PROMPT
    
    def test_load_template_unknown_template(self):
        """Test loading unknown template falls back to basic"""
        builder = PromptBuilder()
        template = builder._load_template('unknown_template')
        
        assert template == DEFAULT_BASIC_PROMPT
    
    def test_prepare_template_variables(self):
        """Test preparing template variables from context"""
        builder = PromptBuilder()
        
        context = {
            'history': {
                'count': 5,
                'success_rate': 0.8,
                'common_status_codes': {'200': 4, '404': 1},
                'recent_results': [
                    {'status': 'success', 'status_code': 200, 'response_time_ms': 100}
                ]
            },
            'validated_examples': [
                {
                    'test_scenario': 'Test scenario',
                    'request_body': {'key': 'value'},
                    'validation_status': 'approved'
                }
            ],
            'patterns': [
                {
                    'pattern_type': 'test_pattern',
                    'pattern_data': {'data': 'value'},
                    'effectiveness': 0.9
                }
            ]
        }
        
        endpoint_info = {
            'method': 'GET',
            'path': '/api/test',
            'summary': 'Test endpoint',
            'description': 'A test endpoint',
            'operation_id': 'testEndpoint',
            'tags': ['test', 'api'],
            'request_schema': {'type': 'object'},
            'response_schemas': {'200': {}},
            'parameters': [
                {'name': 'id', 'in': 'path', 'required': True, 'schema': {'type': 'integer'}}
            ]
        }
        
        vars_dict = builder._prepare_template_variables(context, endpoint_info)
        
        assert vars_dict['method'] == 'GET'
        assert vars_dict['path'] == '/api/test'
        assert vars_dict['summary'] == 'Test endpoint'
        assert vars_dict['history_count'] == 5
        assert '80.0%' in vars_dict['success_rate']
        assert '200(4)' in vars_dict['common_status_codes']
        assert 'id' in vars_dict['parameters']
    
    def test_format_schema(self):
        """Test schema formatting"""
        builder = PromptBuilder()
        
        schema = {
            'type': 'object',
            'properties': {
                'name': {'type': 'string'},
                'age': {'type': 'integer'}
            }
        }
        
        formatted = builder._format_schema(schema)
        assert 'name' in formatted
        assert 'age' in formatted
        assert 'string' in formatted
    
    def test_format_schema_empty(self):
        """Test formatting empty schema"""
        builder = PromptBuilder()
        formatted = builder._format_schema({})
        assert 'No request body schema' in formatted
    
    def test_format_response_schemas(self):
        """Test response schemas formatting"""
        builder = PromptBuilder()
        
        schemas = {
            '200': {'type': 'object', 'properties': {'id': {'type': 'integer'}}},
            '400': {'type': 'object', 'properties': {'error': {'type': 'string'}}}
        }
        
        formatted = builder._format_response_schemas(schemas)
        assert 'Status 200' in formatted
        assert 'Status 400' in formatted
        assert 'id' in formatted
    
    def test_format_parameters(self):
        """Test parameters formatting"""
        builder = PromptBuilder()
        
        parameters = [
            {'name': 'id', 'in': 'path', 'required': True, 'schema': {'type': 'integer'}},
            {'name': 'limit', 'in': 'query', 'required': False, 'schema': {'type': 'integer'}}
        ]
        
        formatted = builder._format_parameters(parameters)
        assert 'id' in formatted
        assert 'path' in formatted
        assert 'required' in formatted
        assert 'limit' in formatted
        assert 'optional' in formatted
    
    def test_format_recent_results(self):
        """Test recent results formatting"""
        builder = PromptBuilder()
        
        results = [
            {'status': 'success', 'status_code': 200, 'response_time_ms': 150},
            {'status': 'error', 'status_code': 404, 'response_time_ms': 50}
        ]
        
        formatted = builder._format_recent_results(results)
        assert 'success' in formatted
        assert '200' in formatted
        assert '150ms' in formatted
        assert '404' in formatted
    
    def test_format_validated_examples(self):
        """Test validated examples formatting"""
        builder = PromptBuilder()
        
        examples = [
            {
                'test_scenario': 'Create user',
                'request_body': {'name': 'John', 'email': 'john@example.com'},
                'validation_status': 'approved'
            }
        ]
        
        formatted = builder._format_validated_examples(examples)
        assert 'Create user' in formatted
        assert 'approved' in formatted
        assert 'john@example.com' in formatted
    
    def test_format_patterns(self):
        """Test patterns formatting"""
        builder = PromptBuilder()
        
        patterns = [
            {
                'pattern_type': 'email_format',
                'pattern_data': {'format': 'email'},
                'effectiveness': 0.9
            }
        ]
        
        formatted = builder._format_patterns(patterns)
        assert 'email_format' in formatted
        assert '0.90' in formatted or '0.9' in formatted
    
    def test_render_template(self):
        """Test template rendering"""
        builder = PromptBuilder()
        
        template = "Method: {method}, Path: {path}, Count: {history_count}"
        variables = {
            'method': 'POST',
            'path': '/api/test',
            'history_count': 10
        }
        
        rendered = builder._render_template(template, variables)
        assert rendered == "Method: POST, Path: /api/test, Count: 10"
    
    def test_render_template_missing_variable(self):
        """Test template rendering with missing variable"""
        builder = PromptBuilder()
        
        template = "Method: {method}, Path: {path}"
        variables = {
            'method': 'POST'
            # Missing 'path'
        }
        
        # Should handle gracefully
        rendered = builder._render_template(template, variables)
        # Should either raise or use default
        assert 'POST' in rendered


class TestInitializeDefaultPrompts:
    """Test initialize_default_prompts function"""
    
    def test_initialize_default_prompts(self):
        """Test initializing default prompts in storage"""
        storage = Mock()
        storage.ai_prompts = Mock()
        storage.ai_prompts.get_latest_prompt = Mock(return_value=None)
        storage.ai_prompts.save_prompt = Mock(return_value=1)
        storage.ai_prompts.set_active_prompt = Mock()
        
        initialize_default_prompts(storage)
        
        # Should save 3 templates
        assert storage.ai_prompts.save_prompt.call_count == 3
        # Should set active for 3 templates
        assert storage.ai_prompts.set_active_prompt.call_count == 3
    
    def test_initialize_default_prompts_skips_existing(self):
        """Test that initialization skips existing prompts"""
        storage = Mock()
        storage.ai_prompts = Mock()
        storage.ai_prompts.get_latest_prompt = Mock(return_value={
            'prompt_template': 'Existing template'
        })
        storage.ai_prompts.save_prompt = Mock()
        
        initialize_default_prompts(storage)
        
        # Should not save if already exists
        storage.ai_prompts.save_prompt.assert_not_called()
    
    def test_initialize_default_prompts_no_storage(self):
        """Test initialization with no storage (should not crash)"""
        initialize_default_prompts(None)
        # Should not raise exception
    
    def test_initialize_default_prompts_storage_error(self):
        """Test initialization handles storage errors gracefully"""
        storage = Mock()
        storage.ai_prompts = Mock()
        storage.ai_prompts.get_latest_prompt = Mock(side_effect=Exception("Storage error"))
        
        # Should not raise exception
        initialize_default_prompts(storage)

