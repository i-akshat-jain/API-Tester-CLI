"""
Tests for Context Builder
"""

import time
import pytest
from unittest.mock import Mock, MagicMock
from apitest.ai.context_builder import ContextBuilder


class TestContextBuilder:
    """Test ContextBuilder class"""
    
    def test_initialization(self):
        """Test ContextBuilder initialization"""
        storage = Mock()
        builder = ContextBuilder(storage)
        
        assert builder.storage == storage
        assert builder._cache == {}
        assert builder._cache_ttl == 300
    
    def test_extract_endpoint_info(self):
        """Test endpoint info extraction from schema"""
        storage = Mock()
        builder = ContextBuilder(storage)
        
        schema = {
            'paths': {
                '/users': {
                    'post': {
                        'summary': 'Create user',
                        'description': 'Create a new user',
                        'operationId': 'createUser',
                        'tags': ['users'],
                        'parameters': [
                            {'name': 'id', 'in': 'path', 'required': True}
                        ],
                        'requestBody': {
                            'content': {
                                'application/json': {
                                    'schema': {
                                        'type': 'object',
                                        'properties': {
                                            'name': {'type': 'string'}
                                        }
                                    }
                                }
                            }
                        },
                        'responses': {
                            '201': {
                                'description': 'Created',
                                'content': {
                                    'application/json': {
                                        'schema': {
                                            'type': 'object',
                                            'properties': {
                                                'id': {'type': 'integer'}
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        
        endpoint_info = builder._extract_endpoint_info(schema, 'POST', '/users')
        
        assert endpoint_info['method'] == 'POST'
        assert endpoint_info['path'] == '/users'
        assert endpoint_info['summary'] == 'Create user'
        assert endpoint_info['description'] == 'Create a new user'
        assert endpoint_info['operation_id'] == 'createUser'
        assert endpoint_info['tags'] == ['users']
        assert len(endpoint_info['parameters']) == 1
        assert 'request_schema' in endpoint_info
        assert 'response_schemas' in endpoint_info
        assert '201' in endpoint_info['response_schemas']
    
    def test_extract_endpoint_info_missing_path(self):
        """Test endpoint info extraction when path doesn't exist"""
        storage = Mock()
        builder = ContextBuilder(storage)
        
        schema = {'paths': {}}
        
        endpoint_info = builder._extract_endpoint_info(schema, 'GET', '/nonexistent')
        
        assert endpoint_info['method'] == 'GET'
        assert endpoint_info['path'] == '/nonexistent'
        assert endpoint_info['summary'] == ''
        assert endpoint_info['request_schema'] == {}
        assert endpoint_info['response_schemas'] == {}
    
    def test_get_historical_context(self):
        """Test historical context retrieval"""
        storage = Mock()
        storage.results = Mock()
        storage.results.get_test_history = Mock(return_value=[
            {'status': 'success', 'status_code': 200, 'timestamp': '2024-01-01', 'response_time_ms': 100},
            {'status': 'success', 'status_code': 200, 'timestamp': '2024-01-02', 'response_time_ms': 150},
            {'status': 'error', 'status_code': 500, 'timestamp': '2024-01-03', 'response_time_ms': 200}
        ])
        
        builder = ContextBuilder(storage)
        history = builder._get_historical_context('schema.yaml', 'GET', '/users')
        
        assert history['count'] == 3
        assert history['success_rate'] == pytest.approx(2/3, 0.01)
        assert len(history['recent_results']) == 3
        assert history['common_status_codes'][200] == 2
        assert history['common_status_codes'][500] == 1
    
    def test_get_historical_context_empty(self):
        """Test historical context when no history exists"""
        storage = Mock()
        storage.results = Mock()
        storage.results.get_test_history = Mock(return_value=[])
        
        builder = ContextBuilder(storage)
        history = builder._get_historical_context('schema.yaml', 'GET', '/users')
        
        assert history['count'] == 0
        assert history['success_rate'] is None
        assert history['recent_results'] == []
    
    def test_get_historical_context_error(self):
        """Test historical context when storage raises error"""
        storage = Mock()
        storage.results = Mock()
        storage.results.get_test_history = Mock(side_effect=Exception("Database error"))
        
        builder = ContextBuilder(storage)
        history = builder._get_historical_context('schema.yaml', 'GET', '/users')
        
        # Should return empty context on error
        assert history['count'] == 0
        assert history['success_rate'] is None
    
    def test_get_validated_test_examples(self):
        """Test validated test examples retrieval"""
        storage = Mock()
        storage.ai_tests = Mock()
        storage.ai_tests.get_validated_ai_test_cases = Mock(return_value=[
            {
                'method': 'POST',
                'path': '/users',
                'test_case_json': {
                    'test_scenario': 'Test scenario 1',
                    'request_body': {'name': 'John'},
                    'expected_response': {'id': 1}
                },
                'validation_status': 'approved',
                'created_at': '2024-01-01'
            }
        ])
        
        builder = ContextBuilder(storage)
        examples = builder._get_validated_test_examples('schema.yaml', 'POST', '/users')
        
        assert len(examples) == 1
        assert examples[0]['test_scenario'] == 'Test scenario 1'
        assert examples[0]['request_body'] == {'name': 'John'}
    
    def test_get_validated_test_examples_empty(self):
        """Test validated test examples when none exist"""
        storage = Mock()
        storage.ai_tests = Mock()
        storage.ai_tests.get_validated_ai_test_cases = Mock(return_value=[])
        
        builder = ContextBuilder(storage)
        examples = builder._get_validated_test_examples('schema.yaml', 'POST', '/users')
        
        assert examples == []
    
    def test_get_relevant_patterns(self):
        """Test relevant patterns retrieval"""
        storage = Mock()
        storage.patterns = Mock()
        storage.patterns.get_patterns = Mock(return_value=[
            {
                'pattern_type': 'request_body',
                'pattern_data': {'name': 'string'},
                'effectiveness_score': 0.8
            },
            {
                'pattern_type': 'response',
                'pattern_data': {'id': 'integer'},
                'effectiveness_score': 0.6
            }
        ])
        
        builder = ContextBuilder(storage)
        patterns = builder._get_relevant_patterns('schema.yaml', 'POST', '/users')
        
        # Should only include patterns with effectiveness > 0.5
        assert len(patterns) == 2
        assert patterns[0]['effectiveness'] == 0.8  # Sorted by effectiveness
        assert patterns[1]['effectiveness'] == 0.6
    
    def test_get_relevant_patterns_empty(self):
        """Test relevant patterns when none exist"""
        storage = Mock()
        storage.patterns = Mock()
        storage.patterns.get_patterns = Mock(return_value=[])
        
        builder = ContextBuilder(storage)
        patterns = builder._get_relevant_patterns('schema.yaml', 'POST', '/users')
        
        assert patterns == []
    
    def test_build_context(self):
        """Test full context building"""
        storage = Mock()
        storage.results = Mock()
        storage.results.get_test_history = Mock(return_value=[])
        storage.ai_tests = Mock()
        storage.ai_tests.get_validated_ai_test_cases = Mock(return_value=[])
        storage.patterns = Mock()
        storage.patterns.get_patterns = Mock(return_value=[])
        
        builder = ContextBuilder(storage)
        
        schema = {
            'paths': {
                '/users': {
                    'get': {
                        'summary': 'Get users',
                        'responses': {'200': {'description': 'OK'}}
                    }
                }
            }
        }
        
        context = builder.build_context(schema, 'schema.yaml', 'GET', '/users')
        
        assert 'endpoint' in context
        assert 'history' in context
        assert 'validated_examples' in context
        assert 'patterns' in context
        assert context['schema_file'] == 'schema.yaml'
        assert context['endpoint']['method'] == 'GET'
        assert context['endpoint']['path'] == '/users'
    
    def test_build_context_caching(self):
        """Test context caching"""
        import time
        
        storage = Mock()
        storage.results = Mock()
        storage.results.get_test_history = Mock(return_value=[])
        storage.ai_tests = Mock()
        storage.ai_tests.get_validated_ai_test_cases = Mock(return_value=[])
        storage.patterns = Mock()
        storage.patterns.get_patterns = Mock(return_value=[])
        
        builder = ContextBuilder(storage)
        builder._cache_ttl = 1  # 1 second TTL for testing
        
        schema = {
            'paths': {
                '/users': {
                    'get': {'summary': 'Get users', 'responses': {}}
                }
            }
        }
        
        # First call
        context1 = builder.build_context(schema, 'schema.yaml', 'GET', '/users')
        
        # Second call should use cache
        context2 = builder.build_context(schema, 'schema.yaml', 'GET', '/users')
        
        # Should only call storage methods once
        assert storage.results.get_test_history.call_count == 1
        
        # Wait for cache to expire
        time.sleep(1.1)
        
        # Third call should rebuild
        context3 = builder.build_context(schema, 'schema.yaml', 'GET', '/users')
        
        # Should call storage methods again
        assert storage.results.get_test_history.call_count == 2
    
    def test_clear_cache(self):
        """Test cache clearing"""
        storage = Mock()
        builder = ContextBuilder(storage)
        
        # Add something to cache
        builder._cache['test'] = ({'data': 'test'}, time.time())
        
        assert len(builder._cache) == 1
        
        builder.clear_cache()
        
        assert len(builder._cache) == 0

