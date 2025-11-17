"""
Tests for AI test generator
"""

import pytest
import json
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from apitest.ai.ai_generator import AITestGenerator
from apitest.config import AIConfig
from apitest.core.test_generator import TestCase as TestCaseData


class TestAITestGenerator:
    """Test AITestGenerator class"""
    
    def test_init_with_groq_config(self):
        """Test AITestGenerator initialization with Groq config"""
        ai_config = AIConfig(
            provider='groq',
            model='llama-3-groq-70b',
            api_key='test-key',
            temperature=0.7,
            max_tokens=2000
        )
        storage = Mock()
        
        generator = AITestGenerator(ai_config, storage)
        
        assert generator.ai_config == ai_config
        assert generator.storage == storage
        assert generator.context_builder is not None
        assert generator.prompt_builder is not None
        assert generator.response_parser is not None
        assert generator.ai_client is not None
    
    def test_init_without_storage(self):
        """Test AITestGenerator initialization without storage"""
        ai_config = AIConfig(
            provider='groq',
            model='llama-3-groq-70b',
            api_key='test-key'
        )
        
        generator = AITestGenerator(ai_config, None)
        
        assert generator.storage is None
        assert generator.context_builder is not None
        assert generator.prompt_builder is not None
    
    def test_init_missing_api_key(self):
        """Test initialization fails without API key"""
        ai_config = AIConfig(
            provider='groq',
            model='llama-3-groq-70b',
            api_key=None
        )
        
        with pytest.raises(ValueError, match="API key is required"):
            AITestGenerator(ai_config, None)
    
    def test_init_unsupported_provider(self):
        """Test initialization fails with unsupported provider"""
        ai_config = AIConfig(
            provider='unsupported',
            model='test-model',
            api_key='test-key'
        )
        
        with pytest.raises(ValueError, match="Unsupported AI provider"):
            AITestGenerator(ai_config, None)
    
    @patch('apitest.ai.ai_generator.GroqClient')
    def test_generate_tests_success(self, mock_groq_client_class):
        """Test successful test generation"""
        # Setup mocks
        mock_groq_client = Mock()
        mock_groq_client.generate.return_value = json.dumps({
            "test_cases": [
                {
                    "test_scenario": "Create user with valid data",
                    "request_body": {"name": "John", "email": "john@example.com"},
                    "expected_response": {
                        "status_code": 201,
                        "body": {"id": 1}
                    }
                }
            ]
        })
        mock_groq_client.tokens_used = 100
        mock_groq_client.tokens_limit = 1000
        mock_groq_client_class.return_value = mock_groq_client
        
        # Setup storage mocks
        storage = Mock()
        storage.results = Mock()
        storage.results.get_test_history = Mock(return_value=[])
        storage.ai_tests = Mock()
        storage.ai_tests.get_validated_ai_test_cases = Mock(return_value=[])
        storage.patterns = Mock()
        storage.patterns.get_patterns = Mock(return_value=[])
        
        # Create generator
        ai_config = AIConfig(
            provider='groq',
            model='llama-3-groq-70b',
            api_key='test-key'
        )
        generator = AITestGenerator(ai_config, storage)
        generator.ai_client = mock_groq_client
        
        # Generate tests
        schema = {
            'paths': {
                '/api/users': {
                    'post': {
                        'summary': 'Create user',
                        'requestBody': {
                            'content': {
                                'application/json': {
                                    'schema': {
                                        'type': 'object',
                                        'properties': {
                                            'name': {'type': 'string'},
                                            'email': {'type': 'string'}
                                        }
                                    }
                                }
                            }
                        },
                        'responses': {
                            '201': {
                                'description': 'Created'
                            }
                        }
                    }
                }
            }
        }
        
        endpoints = [('POST', '/api/users', schema['paths']['/api/users']['post'])]
        
        test_cases = generator.generate_tests(schema, 'test-schema.yaml', endpoints)
        
        # Verify results
        assert len(test_cases) == 1
        assert test_cases[0].method == 'POST'
        assert test_cases[0].path == '/api/users'
        assert test_cases[0].is_ai_generated is True
        assert test_cases[0].test_scenario == "Create user with valid data"
        assert test_cases[0].request_body['name'] == "John"
        assert test_cases[0].expected_response['status_code'] == 201
        assert test_cases[0].ai_metadata is not None
        assert test_cases[0].ai_metadata['model'] == 'llama-3-groq-70b'
        assert test_cases[0].ai_metadata['provider'] == 'groq'
    
    @patch('apitest.ai.ai_generator.GroqClient')
    def test_generate_tests_multiple_endpoints(self, mock_groq_client_class):
        """Test generating tests for multiple endpoints"""
        # Setup mocks
        mock_groq_client = Mock()
        mock_groq_client.generate.return_value = json.dumps({
            "test_cases": [
                {
                    "test_scenario": "Test case",
                    "request_body": {"key": "value"},
                    "expected_response": {"status_code": 200}
                }
            ]
        })
        mock_groq_client.tokens_used = 50
        mock_groq_client.tokens_limit = 1000
        mock_groq_client_class.return_value = mock_groq_client
        
        storage = Mock()
        storage.results = Mock()
        storage.results.get_test_history = Mock(return_value=[])
        storage.ai_tests = Mock()
        storage.ai_tests.get_validated_ai_test_cases = Mock(return_value=[])
        storage.patterns = Mock()
        storage.patterns.get_patterns = Mock(return_value=[])
        
        ai_config = AIConfig(
            provider='groq',
            model='llama-3-groq-70b',
            api_key='test-key'
        )
        generator = AITestGenerator(ai_config, storage)
        generator.ai_client = mock_groq_client
        
        schema = {
            'paths': {
                '/api/users': {
                    'get': {'summary': 'Get users', 'responses': {'200': {}}},
                    'post': {'summary': 'Create user', 'responses': {'201': {}}}
                }
            }
        }
        
        endpoints = [
            ('GET', '/api/users', schema['paths']['/api/users']['get']),
            ('POST', '/api/users', schema['paths']['/api/users']['post'])
        ]
        
        test_cases = generator.generate_tests(schema, 'test-schema.yaml', endpoints)
        
        # Should have test cases for both endpoints
        assert len(test_cases) == 2
        assert mock_groq_client.generate.call_count == 2
    
    @patch('apitest.ai.ai_generator.GroqClient')
    def test_generate_tests_api_error(self, mock_groq_client_class):
        """Test handling of API errors during generation"""
        from apitest.ai.groq_client import GroqAPIError
        
        # Setup mocks
        mock_groq_client = Mock()
        mock_groq_client.generate.side_effect = GroqAPIError("API error occurred")
        mock_groq_client_class.return_value = mock_groq_client
        
        storage = Mock()
        storage.results = Mock()
        storage.results.get_test_history = Mock(return_value=[])
        storage.ai_tests = Mock()
        storage.ai_tests.get_validated_ai_test_cases = Mock(return_value=[])
        storage.patterns = Mock()
        storage.patterns.get_patterns = Mock(return_value=[])
        
        ai_config = AIConfig(
            provider='groq',
            model='llama-3-groq-70b',
            api_key='test-key'
        )
        generator = AITestGenerator(ai_config, storage)
        generator.ai_client = mock_groq_client
        
        schema = {
            'paths': {
                '/api/users': {
                    'get': {'summary': 'Get users', 'responses': {'200': {}}}
                }
            }
        }
        
        endpoints = [('GET', '/api/users', schema['paths']['/api/users']['get'])]
        
        # Should not raise exception, but return empty list
        test_cases = generator.generate_tests(schema, 'test-schema.yaml', endpoints)
        
        assert len(test_cases) == 0
    
    @patch('apitest.ai.ai_generator.GroqClient')
    def test_generate_tests_rate_limit_error(self, mock_groq_client_class):
        """Test handling of rate limit errors"""
        from apitest.ai.groq_client import GroqRateLimitError
        
        mock_groq_client = Mock()
        mock_groq_client.generate.side_effect = GroqRateLimitError("Rate limit exceeded")
        mock_groq_client_class.return_value = mock_groq_client
        
        storage = Mock()
        storage.results = Mock()
        storage.results.get_test_history = Mock(return_value=[])
        storage.ai_tests = Mock()
        storage.ai_tests.get_validated_ai_test_cases = Mock(return_value=[])
        storage.patterns = Mock()
        storage.patterns.get_patterns = Mock(return_value=[])
        
        ai_config = AIConfig(
            provider='groq',
            model='llama-3-groq-70b',
            api_key='test-key'
        )
        generator = AITestGenerator(ai_config, storage)
        generator.ai_client = mock_groq_client
        
        schema = {
            'paths': {
                '/api/users': {
                    'get': {'summary': 'Get users', 'responses': {'200': {}}}
                }
            }
        }
        
        endpoints = [('GET', '/api/users', schema['paths']['/api/users']['get'])]
        
        test_cases = generator.generate_tests(schema, 'test-schema.yaml', endpoints)
        
        assert len(test_cases) == 0
    
    @patch('apitest.ai.ai_generator.GroqClient')
    def test_generate_tests_invalid_response(self, mock_groq_client_class):
        """Test handling of invalid AI response"""
        mock_groq_client = Mock()
        mock_groq_client.generate.return_value = "This is not valid JSON"
        mock_groq_client.tokens_used = 50
        mock_groq_client.tokens_limit = 1000
        mock_groq_client_class.return_value = mock_groq_client
        
        storage = Mock()
        storage.results = Mock()
        storage.results.get_test_history = Mock(return_value=[])
        storage.ai_tests = Mock()
        storage.ai_tests.get_validated_ai_test_cases = Mock(return_value=[])
        storage.patterns = Mock()
        storage.patterns.get_patterns = Mock(return_value=[])
        
        ai_config = AIConfig(
            provider='groq',
            model='llama-3-groq-70b',
            api_key='test-key'
        )
        generator = AITestGenerator(ai_config, storage)
        generator.ai_client = mock_groq_client
        
        schema = {
            'paths': {
                '/api/users': {
                    'get': {'summary': 'Get users', 'responses': {'200': {}}}
                }
            }
        }
        
        endpoints = [('GET', '/api/users', schema['paths']['/api/users']['get'])]
        
        test_cases = generator.generate_tests(schema, 'test-schema.yaml', endpoints)
        
        # Should return empty list when response can't be parsed
        assert len(test_cases) == 0
    
    def test_select_template_basic(self):
        """Test template selection for basic case"""
        from apitest.ai.prompt_builder import PromptBuilder
        
        ai_config = AIConfig(
            provider='groq',
            model='llama-3-groq-70b',
            api_key='test-key'
        )
        generator = AITestGenerator(ai_config, None)
        
        operation = {'summary': 'Test endpoint'}
        context = {
            'history': {'success_rate': 0.9},
            'validated_examples': [],
            'patterns': []
        }
        
        template = generator._select_template(operation, context)
        assert template == PromptBuilder.TEMPLATE_BASIC
    
    def test_select_template_advanced(self):
        """Test template selection for advanced case"""
        from apitest.ai.prompt_builder import PromptBuilder
        
        ai_config = AIConfig(
            provider='groq',
            model='llama-3-groq-70b',
            api_key='test-key'
        )
        generator = AITestGenerator(ai_config, None)
        
        operation = {'summary': 'Test endpoint'}
        context = {
            'history': {'success_rate': 0.9},
            'validated_examples': [{'test_scenario': 'Example'}],
            'patterns': []
        }
        
        template = generator._select_template(operation, context)
        assert template == PromptBuilder.TEMPLATE_ADVANCED
    
    def test_select_template_edge_cases(self):
        """Test template selection for edge cases"""
        from apitest.ai.prompt_builder import PromptBuilder
        
        ai_config = AIConfig(
            provider='groq',
            model='llama-3-groq-70b',
            api_key='test-key'
        )
        generator = AITestGenerator(ai_config, None)
        
        operation = {'summary': 'Test endpoint'}
        context = {
            'history': {'success_rate': 0.5},  # Low success rate
            'validated_examples': [],
            'patterns': []
        }
        
        template = generator._select_template(operation, context)
        assert template == PromptBuilder.TEMPLATE_EDGE_CASES
    
    def test_create_test_case(self):
        """Test creating TestCase from parsed case"""
        ai_config = AIConfig(
            provider='groq',
            model='llama-3-groq-70b',
            api_key='test-key',
            temperature=0.8,
            max_tokens=1500
        )
        generator = AITestGenerator(ai_config, None)
        
        # Mock AI client for metadata
        generator.ai_client = Mock()
        generator.ai_client.tokens_used = 200
        generator.ai_client.tokens_limit = 2000
        
        parsed_case = {
            'test_scenario': 'Test scenario',
            'request_body': {'name': 'John'},
            'expected_response': {
                'status_code': 201,
                'body': {'id': 1}
            },
            'rationale': 'Test rationale'
        }
        
        test_case = generator._create_test_case(
            parsed_case=parsed_case,
            method='POST',
            path='/api/users',
            schema_file='test-schema.yaml'
        )
        
        assert isinstance(test_case, TestCaseData)
        assert test_case.method == 'POST'
        assert test_case.path == '/api/users'
        assert test_case.is_ai_generated is True
        assert test_case.test_scenario == 'Test scenario'
        assert test_case.request_body == {'name': 'John'}
        assert test_case.expected_response['status_code'] == 201
        assert test_case.ai_metadata is not None
        assert test_case.ai_metadata['model'] == 'llama-3-groq-70b'
        assert test_case.ai_metadata['provider'] == 'groq'
        assert test_case.ai_metadata['temperature'] == 0.8
        assert test_case.ai_metadata['max_tokens'] == 1500
        assert test_case.ai_metadata['tokens_used'] == 200
        assert 'generation_timestamp' in test_case.ai_metadata

