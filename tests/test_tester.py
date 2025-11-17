"""
Comprehensive tests for APITester class
"""

import pytest
import requests
from unittest.mock import Mock, patch, MagicMock
from apitest.tester import APITester, TestResult, TestResults, TestStatus
from apitest.auth import AuthHandler
from apitest.schema_parser import SchemaParser


@pytest.fixture
def sample_schema():
    """Sample OpenAPI schema for testing"""
    return {
        'openapi': '3.0.0',
        'info': {'title': 'Test API', 'version': '1.0.0'},
        'servers': [{'url': 'https://api.example.com'}],
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
                                        'email': {'type': 'string'}
                                    }
                                }
                            }
                        }
                    },
                    'responses': {'201': {'description': 'Created'}}
                }
            },
            '/users/{id}': {
                'get': {
                    'parameters': [
                        {
                            'name': 'id',
                            'in': 'path',
                            'required': True,
                            'schema': {'type': 'integer'}
                        }
                    ],
                    'responses': {'200': {'description': 'OK'}}
                }
            }
        }
    }


@pytest.fixture
def empty_auth_handler():
    """Empty auth handler for testing"""
    return AuthHandler()


class TestAPITesterInitialization:
    """Test APITester initialization"""
    
    def test_init_with_valid_schema(self, sample_schema, empty_auth_handler):
        """Test initialization with valid schema"""
        tester = APITester(
            schema=sample_schema,
            auth_handlers=[empty_auth_handler],
            timeout=30
        )
        assert tester.schema == sample_schema
        assert tester.base_url == 'https://api.example.com'
        assert tester.timeout == 30
        assert tester.parallel is False
    
    def test_init_with_invalid_base_url(self, sample_schema, empty_auth_handler):
        """Test initialization with invalid base URL (should use default)"""
        schema = sample_schema.copy()
        schema['servers'] = [{'url': '/api'}]
        tester = APITester(
            schema=schema,
            auth_handlers=[empty_auth_handler],
            verbose=True
        )
        assert tester.base_url == 'http://localhost:8000'
    
    def test_init_with_empty_base_url(self, sample_schema, empty_auth_handler):
        """Test initialization with empty base URL"""
        schema = sample_schema.copy()
        schema['servers'] = [{'url': ''}]
        tester = APITester(
            schema=schema,
            auth_handlers=[empty_auth_handler]
        )
        assert tester.base_url == 'http://localhost:8000'
    
    def test_init_with_no_servers(self, sample_schema, empty_auth_handler):
        """Test initialization with no servers"""
        schema = sample_schema.copy()
        del schema['servers']
        tester = APITester(
            schema=schema,
            auth_handlers=[empty_auth_handler]
        )
        assert tester.base_url == 'http://localhost:8000'
    
    def test_init_with_multiple_auth_handlers(self, sample_schema):
        """Test initialization with multiple auth handlers"""
        handler1 = AuthHandler()
        handler1.parse_auth_string('bearer=token1')
        handler2 = AuthHandler()
        handler2.parse_auth_string('bearer=token2')
        
        tester = APITester(
            schema=sample_schema,
            auth_handlers=[handler1, handler2]
        )
        assert len(tester.auth_handlers) == 2
    
    def test_init_with_empty_auth_handlers_list(self, sample_schema):
        """Test initialization with empty auth handlers list"""
        tester = APITester(
            schema=sample_schema,
            auth_handlers=[]
        )
        assert len(tester.auth_handlers) == 1
        assert tester.auth_handlers[0].auth_type is None
    
    def test_init_with_single_auth_handler(self, sample_schema, empty_auth_handler):
        """Test initialization with single auth handler (not a list)"""
        tester = APITester(
            schema=sample_schema,
            auth_handlers=empty_auth_handler
        )
        assert len(tester.auth_handlers) == 1


class TestURLBuilding:
    """Test URL building functionality"""
    
    def test_build_url_simple_path(self, sample_schema, empty_auth_handler):
        """Test building URL for simple path"""
        tester = APITester(
            schema=sample_schema,
            auth_handlers=[empty_auth_handler]
        )
        url = tester._build_url('/users')
        assert url == 'https://api.example.com/users'
    
    def test_build_url_with_path_params(self, sample_schema, empty_auth_handler):
        """Test building URL with path parameters"""
        tester = APITester(
            schema=sample_schema,
            auth_handlers=[empty_auth_handler],
            path_params={'id': '123'}
        )
        operation = sample_schema['paths']['/users/{id}']['get']
        url = tester._build_url('/users/{id}', operation)
        assert url == 'https://api.example.com/users/123'
    
    def test_build_url_with_default_path_param(self, sample_schema, empty_auth_handler):
        """Test building URL with default path parameter value"""
        tester = APITester(
            schema=sample_schema,
            auth_handlers=[empty_auth_handler]
        )
        operation = sample_schema['paths']['/users/{id}']['get']
        url = tester._build_url('/users/{id}', operation)
        assert url == 'https://api.example.com/users/1'  # Default integer value
    
    def test_build_url_with_multiple_path_params(self, sample_schema, empty_auth_handler):
        """Test building URL with multiple path parameters"""
        schema = sample_schema.copy()
        schema['paths']['/users/{userId}/posts/{postId}'] = {
            'get': {
                'parameters': [
                    {'name': 'userId', 'in': 'path', 'schema': {'type': 'string'}},
                    {'name': 'postId', 'in': 'path', 'schema': {'type': 'integer'}}
                ],
                'responses': {'200': {'description': 'OK'}}
            }
        }
        tester = APITester(
            schema=schema,
            auth_handlers=[empty_auth_handler],
            path_params={'userId': 'user123', 'postId': '456'}
        )
        operation = schema['paths']['/users/{userId}/posts/{postId}']['get']
        url = tester._build_url('/users/{userId}/posts/{postId}', operation)
        assert url == 'https://api.example.com/users/user123/posts/456'
    
    def test_build_url_with_base_url_trailing_slash(self, sample_schema, empty_auth_handler):
        """Test building URL when base URL has trailing slash"""
        schema = sample_schema.copy()
        schema['servers'] = [{'url': 'https://api.example.com/'}]
        tester = APITester(
            schema=schema,
            auth_handlers=[empty_auth_handler]
        )
        url = tester._build_url('/users')
        assert url == 'https://api.example.com/users'
    
    def test_build_url_with_path_leading_slash(self, sample_schema, empty_auth_handler):
        """Test building URL when path has leading slash"""
        tester = APITester(
            schema=sample_schema,
            auth_handlers=[empty_auth_handler]
        )
        url = tester._build_url('users')  # No leading slash
        assert url == 'https://api.example.com/users'


class TestPathParameterGeneration:
    """Test path parameter value generation"""
    
    def test_generate_integer_path_param(self, sample_schema, empty_auth_handler):
        """Test generating integer path parameter"""
        tester = APITester(
            schema=sample_schema,
            auth_handlers=[empty_auth_handler]
        )
        operation = sample_schema['paths']['/users/{id}']['get']
        value = tester._generate_path_param_value('id', operation)
        assert value == 1
        assert isinstance(value, int)
    
    def test_generate_string_path_param(self, sample_schema, empty_auth_handler):
        """Test generating string path parameter"""
        schema = sample_schema.copy()
        schema['paths']['/users/{username}'] = {
            'get': {
                'parameters': [
                    {'name': 'username', 'in': 'path', 'schema': {'type': 'string'}}
                ],
                'responses': {'200': {'description': 'OK'}}
            }
        }
        tester = APITester(
            schema=schema,
            auth_handlers=[empty_auth_handler]
        )
        operation = schema['paths']['/users/{username}']['get']
        value = tester._generate_path_param_value('username', operation)
        assert value == 'test'
    
    def test_generate_uuid_path_param(self, sample_schema, empty_auth_handler):
        """Test generating UUID path parameter"""
        schema = sample_schema.copy()
        schema['paths']['/users/{uuid}'] = {
            'get': {
                'parameters': [
                    {'name': 'uuid', 'in': 'path', 'schema': {'type': 'string', 'format': 'uuid'}}
                ],
                'responses': {'200': {'description': 'OK'}}
            }
        }
        tester = APITester(
            schema=schema,
            auth_handlers=[empty_auth_handler]
        )
        operation = schema['paths']['/users/{uuid}']['get']
        value = tester._generate_path_param_value('uuid', operation)
        assert value == '123e4567-e89b-12d3-a456-426614174000'
    
    def test_generate_date_path_param(self, sample_schema, empty_auth_handler):
        """Test generating date path parameter"""
        schema = sample_schema.copy()
        schema['paths']['/events/{date}'] = {
            'get': {
                'parameters': [
                    {'name': 'date', 'in': 'path', 'schema': {'type': 'string', 'format': 'date'}}
                ],
                'responses': {'200': {'description': 'OK'}}
            }
        }
        tester = APITester(
            schema=schema,
            auth_handlers=[empty_auth_handler]
        )
        operation = schema['paths']['/events/{date}']['get']
        value = tester._generate_path_param_value('date', operation)
        assert value == '2024-01-01'
    
    def test_generate_path_param_no_operation(self, sample_schema, empty_auth_handler):
        """Test generating path parameter when operation is None"""
        tester = APITester(
            schema=sample_schema,
            auth_handlers=[empty_auth_handler]
        )
        value = tester._generate_path_param_value('id', None)
        assert value == 1  # Default fallback


class TestExpectedStatusCode:
    """Test expected status code extraction"""
    
    def test_get_expected_status_200(self, sample_schema, empty_auth_handler):
        """Test getting expected status code 200"""
        tester = APITester(
            schema=sample_schema,
            auth_handlers=[empty_auth_handler]
        )
        operation = sample_schema['paths']['/users']['get']
        status = tester._get_expected_status_code(operation)
        assert status == 200
    
    def test_get_expected_status_201(self, sample_schema, empty_auth_handler):
        """Test getting expected status code 201"""
        tester = APITester(
            schema=sample_schema,
            auth_handlers=[empty_auth_handler]
        )
        operation = sample_schema['paths']['/users']['post']
        status = tester._get_expected_status_code(operation)
        assert status == 201
    
    def test_get_expected_status_no_responses(self, sample_schema, empty_auth_handler):
        """Test getting expected status when no responses defined"""
        tester = APITester(
            schema=sample_schema,
            auth_handlers=[empty_auth_handler]
        )
        operation = {}
        status = tester._get_expected_status_code(operation)
        assert status is None
    
    def test_get_expected_status_first_available(self, sample_schema, empty_auth_handler):
        """Test getting first available status code"""
        tester = APITester(
            schema=sample_schema,
            auth_handlers=[empty_auth_handler]
        )
        operation = {'responses': {'400': {'description': 'Bad Request'}}}
        status = tester._get_expected_status_code(operation)
        assert status == 400


class TestTestExecution:
    """Test test execution functionality"""
    
    @patch('apitest.tester.requests.request')
    def test_test_endpoint_success(self, mock_request, sample_schema, empty_auth_handler):
        """Test successful endpoint test"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"id": 1, "name": "Test"}'
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.json.return_value = {'id': 1, 'name': 'Test'}
        mock_request.return_value = mock_response
        
        tester = APITester(
            schema=sample_schema,
            auth_handlers=[empty_auth_handler],
            timeout=30
        )
        operation = sample_schema['paths']['/users']['get']
        result = tester._test_endpoint('GET', '/users', operation)
        
        assert result.status == TestStatus.PASS
        assert result.status_code == 200
        assert result.method == 'GET'
        assert result.path == '/users'
        assert result.response_time_ms > 0
    
    @patch('apitest.tester.requests.request')
    def test_test_endpoint_with_auth(self, mock_request, sample_schema):
        """Test endpoint test with authentication"""
        handler = AuthHandler()
        handler.parse_auth_string('bearer=test_token')
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{}'
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.json.return_value = {}
        mock_request.return_value = mock_response
        
        tester = APITester(
            schema=sample_schema,
            auth_handlers=[handler]
        )
        operation = sample_schema['paths']['/users']['get']
        result = tester._test_endpoint('GET', '/users', operation)
        
        # Verify auth header was sent
        call_args = mock_request.call_args
        assert 'Authorization' in call_args[1]['headers']
        assert call_args[1]['headers']['Authorization'] == 'Bearer test_token'
    
    @patch('apitest.tester.requests.request')
    def test_test_endpoint_timeout(self, mock_request, sample_schema, empty_auth_handler):
        """Test endpoint test with timeout"""
        mock_request.side_effect = requests.exceptions.Timeout("Request timeout")
        
        tester = APITester(
            schema=sample_schema,
            auth_handlers=[empty_auth_handler],
            timeout=5
        )
        operation = sample_schema['paths']['/users']['get']
        result = tester._test_endpoint('GET', '/users', operation)
        
        assert result.status == TestStatus.ERROR
        assert result.status_code == 0
        assert 'timeout' in result.error_message.lower()
    
    @patch('apitest.tester.requests.request')
    def test_test_endpoint_connection_error(self, mock_request, sample_schema, empty_auth_handler):
        """Test endpoint test with connection error"""
        mock_request.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        tester = APITester(
            schema=sample_schema,
            auth_handlers=[empty_auth_handler]
        )
        operation = sample_schema['paths']['/users']['get']
        result = tester._test_endpoint('GET', '/users', operation)
        
        assert result.status == TestStatus.ERROR
        assert 'connection' in result.error_message.lower()
    
    @patch('apitest.tester.requests.request')
    def test_test_endpoint_invalid_url(self, mock_request, sample_schema, empty_auth_handler):
        """Test endpoint test with invalid URL"""
        mock_request.side_effect = requests.exceptions.InvalidURL("Invalid URL")
        
        tester = APITester(
            schema=sample_schema,
            auth_handlers=[empty_auth_handler]
        )
        operation = sample_schema['paths']['/users']['get']
        result = tester._test_endpoint('GET', '/users', operation)
        
        assert result.status == TestStatus.ERROR
        assert 'url' in result.error_message.lower()
    
    @patch('apitest.tester.requests.request')
    def test_test_endpoint_401_retry_auth(self, mock_request, sample_schema):
        """Test endpoint test with 401 retrying with different auth"""
        handler1 = AuthHandler()
        handler1.parse_auth_string('bearer=token1')
        handler2 = AuthHandler()
        handler2.parse_auth_string('bearer=token2')
        
        # First request returns 401, second returns 200
        mock_response1 = Mock()
        mock_response1.status_code = 401
        mock_response1.content = b''
        mock_response1.headers = {}
        
        mock_response2 = Mock()
        mock_response2.status_code = 200
        mock_response2.content = b'{}'
        mock_response2.headers = {'Content-Type': 'application/json'}
        mock_response2.json.return_value = {}
        
        mock_request.side_effect = [mock_response1, mock_response2]
        
        tester = APITester(
            schema=sample_schema,
            auth_handlers=[handler1, handler2]
        )
        operation = sample_schema['paths']['/users']['get']
        result = tester._test_endpoint('GET', '/users', operation)
        
        assert result.status == TestStatus.PASS
        assert result.status_code == 200
        assert result.auth_attempts == 2
        assert result.auth_succeeded is True
    
    @patch('apitest.tester.requests.request')
    def test_test_endpoint_all_auth_fail(self, mock_request, sample_schema):
        """Test endpoint test when all auth methods fail"""
        handler1 = AuthHandler()
        handler1.parse_auth_string('bearer=token1')
        handler2 = AuthHandler()
        handler2.parse_auth_string('bearer=token2')
        
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.content = b''
        mock_response.headers = {}
        mock_request.return_value = mock_response
        
        tester = APITester(
            schema=sample_schema,
            auth_handlers=[handler1, handler2]
        )
        operation = sample_schema['paths']['/users']['get']
        result = tester._test_endpoint('GET', '/users', operation)
        
        assert result.status == TestStatus.FAIL
        assert result.status_code == 401
        assert result.auth_attempts == 2
        assert result.auth_succeeded is False


class TestResponseValidation:
    """Test response validation"""
    
    def test_validate_response_schema_valid(self, sample_schema, empty_auth_handler):
        """Test validating valid response schema"""
        schema = sample_schema.copy()
        schema['paths']['/users']['get']['responses']['200'] = {
            'content': {
                'application/json': {
                    'schema': {
                        'type': 'object',
                        'properties': {
                            'id': {'type': 'integer'},
                            'name': {'type': 'string'}
                        }
                    }
                }
            }
        }
        schema['components'] = {'schemas': {}}
        
        tester = APITester(
            schema=schema,
            auth_handlers=[empty_auth_handler]
        )
        operation = schema['paths']['/users']['get']
        response_body = {'id': 1, 'name': 'Test'}
        errors = tester._validate_response_schema(
            response_body, 200, operation['responses']
        )
        assert len(errors) == 0
    
    def test_validate_response_schema_invalid(self, sample_schema, empty_auth_handler):
        """Test validating invalid response schema"""
        schema = sample_schema.copy()
        schema['paths']['/users']['get']['responses']['200'] = {
            'content': {
                'application/json': {
                    'schema': {
                        'type': 'object',
                        'properties': {
                            'id': {'type': 'integer'},
                            'name': {'type': 'string'}
                        },
                        'required': ['id', 'name']
                    }
                }
            }
        }
        schema['components'] = {'schemas': {}}
        
        tester = APITester(
            schema=schema,
            auth_handlers=[empty_auth_handler]
        )
        operation = schema['paths']['/users']['get']
        response_body = {'id': 1}  # Missing 'name'
        errors = tester._validate_response_schema(
            response_body, 200, operation['responses']
        )
        assert len(errors) > 0
    
    def test_validate_response_schema_no_schema_defined(self, sample_schema, empty_auth_handler):
        """Test validating response when no schema defined"""
        tester = APITester(
            schema=sample_schema,
            auth_handlers=[empty_auth_handler]
        )
        operation = sample_schema['paths']['/users']['get']
        response_body = {'id': 1}
        errors = tester._validate_response_schema(
            response_body, 200, operation['responses']
        )
        assert len(errors) == 0  # No schema means no validation
    
    def test_validate_response_schema_with_refs(self, sample_schema, empty_auth_handler):
        """Test validating response schema with $ref references"""
        schema = sample_schema.copy()
        schema['components'] = {
            'schemas': {
                'User': {
                    'type': 'object',
                    'properties': {
                        'id': {'type': 'integer'},
                        'name': {'type': 'string'}
                    }
                }
            }
        }
        schema['paths']['/users']['get']['responses']['200'] = {
            'content': {
                'application/json': {
                    'schema': {'$ref': '#/components/schemas/User'}
                }
            }
        }
        
        tester = APITester(
            schema=schema,
            auth_handlers=[empty_auth_handler]
        )
        operation = schema['paths']['/users']['get']
        response_body = {'id': 1, 'name': 'Test'}
        errors = tester._validate_response_schema(
            response_body, 200, operation['responses']
        )
        assert len(errors) == 0


class TestTestResults:
    """Test TestResults class"""
    
    def test_test_results_initialization(self):
        """Test TestResults initialization"""
        results = TestResults()
        assert len(results.results) == 0
        assert results.total_time_seconds == 0.0
    
    def test_add_result(self):
        """Test adding result to TestResults"""
        results = TestResults()
        result = TestResult(
            method='GET',
            path='/users',
            status_code=200,
            status=TestStatus.PASS
        )
        results.add_result(result)
        assert len(results.results) == 1
    
    def test_get_passed(self):
        """Test getting passed results"""
        results = TestResults()
        results.add_result(TestResult('GET', '/users', 200, status=TestStatus.PASS))
        results.add_result(TestResult('POST', '/users', 201, status=TestStatus.PASS))
        results.add_result(TestResult('GET', '/invalid', 404, status=TestStatus.FAIL))
        
        passed = results.get_passed()
        assert len(passed) == 2
    
    def test_get_failed(self):
        """Test getting failed results"""
        results = TestResults()
        results.add_result(TestResult('GET', '/users', 200, status=TestStatus.PASS))
        results.add_result(TestResult('GET', '/invalid', 404, status=TestStatus.FAIL))
        results.add_result(TestResult('GET', '/error', 500, status=TestStatus.ERROR))
        
        failed = results.get_failed()
        assert len(failed) == 1
    
    def test_get_errors(self):
        """Test getting error results"""
        results = TestResults()
        results.add_result(TestResult('GET', '/users', 200, status=TestStatus.PASS))
        results.add_result(TestResult('GET', '/error', 0, status=TestStatus.ERROR))
        
        errors = results.get_errors()
        assert len(errors) == 1
    
    def test_get_warnings(self):
        """Test getting warning results"""
        results = TestResults()
        results.add_result(TestResult('GET', '/users', 200, status=TestStatus.PASS))
        results.add_result(TestResult('GET', '/warn', 200, status=TestStatus.WARNING))
        
        warnings = results.get_warnings()
        assert len(warnings) == 1
    
    def test_has_failures(self):
        """Test checking if results have failures"""
        results = TestResults()
        results.add_result(TestResult('GET', '/users', 200, status=TestStatus.PASS))
        assert results.has_failures() is False
        
        results.add_result(TestResult('GET', '/error', 404, status=TestStatus.FAIL))
        assert results.has_failures() is True
    
    def test_get_success_rate(self):
        """Test calculating success rate"""
        results = TestResults()
        results.add_result(TestResult('GET', '/users', 200, status=TestStatus.PASS))
        results.add_result(TestResult('POST', '/users', 201, status=TestStatus.PASS))
        results.add_result(TestResult('GET', '/error', 404, status=TestStatus.FAIL))
        
        rate = results.get_success_rate()
        assert rate == pytest.approx(66.67, rel=0.01)
    
    def test_get_success_rate_empty(self):
        """Test calculating success rate with no results"""
        results = TestResults()
        rate = results.get_success_rate()
        assert rate == 0.0


class TestRunTests:
    """Test run_tests method"""
    
    @patch('apitest.tester.requests.request')
    def test_run_tests_sequential(self, mock_request, sample_schema, empty_auth_handler):
        """Test running tests sequentially"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{}'
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.json.return_value = {}
        mock_request.return_value = mock_response
        
        tester = APITester(
            schema=sample_schema,
            auth_handlers=[empty_auth_handler],
            parallel=False
        )
        results = tester.run_tests()
        
        assert len(results.results) > 0
        assert results.total_time_seconds > 0
    
    @patch('apitest.tester.requests.request')
    def test_run_tests_parallel(self, mock_request, sample_schema, empty_auth_handler):
        """Test running tests in parallel"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{}'
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.json.return_value = {}
        mock_request.return_value = mock_response
        
        tester = APITester(
            schema=sample_schema,
            auth_handlers=[empty_auth_handler],
            parallel=True
        )
        results = tester.run_tests()
        
        assert len(results.results) > 0
    
    @patch('apitest.tester.requests.request')
    def test_run_tests_empty_schema(self, mock_request, empty_auth_handler):
        """Test running tests with empty schema"""
        schema = {
            'openapi': '3.0.0',
            'info': {'title': 'Test'},
            'servers': [{'url': 'https://api.example.com'}],
            'paths': {}
        }
        tester = APITester(
            schema=schema,
            auth_handlers=[empty_auth_handler]
        )
        results = tester.run_tests()
        
        assert len(results.results) == 0


class TestEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_invalid_url_building(self, sample_schema, empty_auth_handler):
        """Test building URL with invalid base URL"""
        schema = sample_schema.copy()
        schema['servers'] = [{'url': 'not-a-url'}]
        tester = APITester(
            schema=schema,
            auth_handlers=[empty_auth_handler]
        )
        # Should fall back to default
        assert tester.base_url == 'http://localhost:8000'
    
    @patch('apitest.tester.requests.request')
    def test_non_json_response(self, mock_request, sample_schema, empty_auth_handler):
        """Test handling non-JSON response"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'<html>Not JSON</html>'
        mock_response.headers = {'Content-Type': 'text/html'}
        mock_response.text = '<html>Not JSON</html>'
        mock_request.return_value = mock_response
        
        tester = APITester(
            schema=sample_schema,
            auth_handlers=[empty_auth_handler]
        )
        operation = sample_schema['paths']['/users']['get']
        result = tester._test_endpoint('GET', '/users', operation)
        
        assert result.status_code == 200
        # Should handle gracefully
    
    @patch('apitest.tester.requests.request')
    def test_xml_response(self, mock_request, sample_schema, empty_auth_handler):
        """Test handling XML response"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'<root><item>test</item></root>'
        mock_response.headers = {'Content-Type': 'application/xml'}
        mock_response.text = '<root><item>test</item></root>'
        mock_request.return_value = mock_response
        
        tester = APITester(
            schema=sample_schema,
            auth_handlers=[empty_auth_handler]
        )
        operation = sample_schema['paths']['/users']['get']
        result = tester._test_endpoint('GET', '/users', operation)
        
        assert result.status_code == 200
        assert result.response_body is not None
    
    @patch('apitest.tester.requests.request')
    def test_empty_response_body(self, mock_request, sample_schema, empty_auth_handler):
        """Test handling empty response body"""
        mock_response = Mock()
        mock_response.status_code = 204
        mock_response.content = b''
        mock_response.headers = {}
        mock_request.return_value = mock_response
        
        tester = APITester(
            schema=sample_schema,
            auth_handlers=[empty_auth_handler]
        )
        operation = sample_schema['paths']['/users']['get']
        result = tester._test_endpoint('GET', '/users', operation)
        
        assert result.status_code == 204
        assert result.response_body is None or result.response_body == {}
    
    def test_resolve_schema_refs_nested(self, sample_schema, empty_auth_handler):
        """Test resolving nested schema references"""
        schema = sample_schema.copy()
        schema['components'] = {
            'schemas': {
                'User': {
                    'type': 'object',
                    'properties': {
                        'id': {'type': 'integer'},
                        'profile': {'$ref': '#/components/schemas/Profile'}
                    }
                },
                'Profile': {
                    'type': 'object',
                    'properties': {
                        'name': {'type': 'string'}
                    }
                }
            }
        }
        
        tester = APITester(
            schema=schema,
            auth_handlers=[empty_auth_handler]
        )
        resolved = tester._resolve_schema_refs({
            '$ref': '#/components/schemas/User'
        })
        assert 'properties' in resolved
        assert 'id' in resolved['properties']

