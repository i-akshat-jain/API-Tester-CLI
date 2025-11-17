"""
Tests for TestGenerator router pattern
"""

import pytest
from apitest.core.test_generator import TestGenerator, TestCase


class TestTestGeneratorRouter:
    """Test TestGenerator router functionality"""
    
    def test_schema_mode_generation(self):
        """Test schema mode generates tests correctly"""
        generator = TestGenerator(mode='schema')
        
        schema = {
            'openapi': '3.0.0',
            'paths': {
                '/users': {
                    'get': {
                        'responses': {'200': {'description': 'OK'}}
                    },
                    'post': {
                        'requestBody': {
                            'content': {
                                'application/json': {
                                    'schema': {
                                        'type': 'object',
                                        'properties': {
                                            'name': {'type': 'string'},
                                            'email': {'type': 'string', 'format': 'email'}
                                        }
                                    }
                                }
                            }
                        },
                        'responses': {'201': {'description': 'Created'}}
                    }
                }
            }
        }
        
        endpoints = [
            ('GET', '/users', schema['paths']['/users']['get']),
            ('POST', '/users', schema['paths']['/users']['post'])
        ]
        
        test_cases = generator.generate_tests(schema, endpoints)
        
        assert len(test_cases) == 2
        assert test_cases[0].method == 'GET'
        assert test_cases[0].path == '/users'
        assert test_cases[0].is_ai_generated is False
        assert test_cases[1].method == 'POST'
        assert test_cases[1].path == '/users'
        assert test_cases[1].request_body is not None
        assert 'name' in test_cases[1].request_body
        assert 'email' in test_cases[1].request_body
    
    def test_ai_mode_placeholder(self):
        """Test AI mode returns empty list (placeholder)"""
        generator = TestGenerator(mode='ai')
        
        schema = {'openapi': '3.0.0', 'paths': {}}
        endpoints = [('GET', '/test', {})]
        
        test_cases = generator.generate_tests(schema, endpoints)
        
        # Should return empty list for now (AI not implemented yet)
        assert test_cases == []
    
    def test_hybrid_mode_combines(self):
        """Test hybrid mode combines schema and AI tests"""
        generator = TestGenerator(mode='hybrid')
        
        schema = {
            'openapi': '3.0.0',
            'paths': {
                '/users': {
                    'get': {
                        'responses': {'200': {'description': 'OK'}}
                    }
                }
            }
        }
        
        endpoints = [('GET', '/users', schema['paths']['/users']['get'])]
        
        test_cases = generator.generate_tests(schema, endpoints)
        
        # Should return schema tests (AI returns empty for now)
        assert len(test_cases) == 1
        assert test_cases[0].method == 'GET'
        assert test_cases[0].is_ai_generated is False
    
    def test_combine_tests_deduplication(self):
        """Test test combination with deduplication"""
        generator = TestGenerator(mode='hybrid')
        
        schema_test = TestCase(
            method='POST',
            path='/users',
            request_body={'name': 'Test', 'email': 'test@example.com'},
            is_ai_generated=False
        )
        
        ai_test_similar = TestCase(
            method='POST',
            path='/users',
            request_body={'name': 'Different', 'email': 'different@example.com'},  # Same keys
            is_ai_generated=True
        )
        
        ai_test_different = TestCase(
            method='POST',
            path='/users',
            request_body={'name': 'Test', 'age': 25},  # Different keys
            is_ai_generated=True
        )
        
        combined = generator._combine_tests([schema_test], [ai_test_similar, ai_test_different])
        
        # ai_test_similar should be deduplicated (same keys)
        # ai_test_different should be added (different keys)
        assert len(combined) == 2
        assert combined[0].is_ai_generated is False
        assert combined[1].is_ai_generated is True
        assert 'age' in combined[1].request_body
    
    def test_static_method_backward_compatibility(self):
        """Test static method still works for backward compatibility"""
        request_body = {
            'content': {
                'application/json': {
                    'schema': {
                        'type': 'object',
                        'properties': {
                            'name': {'type': 'string', 'example': 'John'},
                            'age': {'type': 'integer'}
                        }
                    }
                }
            }
        }
        
        data = TestGenerator.generate_test_data(request_body)
        
        assert 'name' in data
        assert data['name'] == 'John'  # Uses example
        assert 'age' in data
        assert isinstance(data['age'], int)
    
    def test_test_case_dataclass(self):
        """Test TestCase dataclass"""
        test_case = TestCase(
            method='POST',
            path='/users',
            request_body={'name': 'Test'},
            expected_response={'status': 201},
            test_scenario='Test scenario',
            is_ai_generated=True,
            ai_metadata={'model': 'llama-3-groq-70b'}
        )
        
        assert test_case.method == 'POST'
        assert test_case.path == '/users'
        assert test_case.request_body == {'name': 'Test'}
        assert test_case.is_ai_generated is True
        assert test_case.ai_metadata == {'model': 'llama-3-groq-70b'}

