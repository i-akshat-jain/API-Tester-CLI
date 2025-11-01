"""
API endpoint tester
"""

import time
import requests
import jsonschema
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed

from apitest.schema_parser import SchemaParser
from apitest.auth import AuthHandler
from rich.console import Console


class TestStatus(Enum):
    """Test result status"""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class TestResult:
    """Result of a single endpoint test"""
    method: str
    path: str
    status_code: int
    expected_status: Optional[int] = None
    response_time_ms: float = 0.0
    status: TestStatus = TestStatus.PASS
    error_message: Optional[str] = None
    schema_mismatch: bool = False
    schema_errors: List[str] = field(default_factory=list)
    response_body: Optional[Dict[str, Any]] = None
    response_size_bytes: int = 0


@dataclass
class TestResults:
    """Collection of test results"""
    results: List[TestResult] = field(default_factory=list)
    total_time_seconds: float = 0.0
    
    def add_result(self, result: TestResult):
        """Add a test result"""
        self.results.append(result)
    
    def get_passed(self) -> List[TestResult]:
        """Get all passed tests"""
        return [r for r in self.results if r.status == TestStatus.PASS]
    
    def get_failed(self) -> List[TestResult]:
        """Get all failed tests"""
        return [r for r in self.results if r.status == TestStatus.FAIL]
    
    def get_warnings(self) -> List[TestResult]:
        """Get all warnings"""
        return [r for r in self.results if r.status == TestStatus.WARNING]
    
    def get_errors(self) -> List[TestResult]:
        """Get all errors"""
        return [r for r in self.results if r.status == TestStatus.ERROR]
    
    def has_failures(self) -> bool:
        """Check if there are any failures"""
        return len(self.get_failed()) > 0 or len(self.get_errors()) > 0
    
    def get_success_rate(self) -> float:
        """Calculate success rate as percentage"""
        if not self.results:
            return 0.0
        passed = len(self.get_passed())
        return (passed / len(self.results)) * 100


class APITester:
    """Test API endpoints from OpenAPI schema"""
    
    def __init__(self, schema: Dict[str, Any], auth_handler: AuthHandler, 
                 timeout: int = 30, parallel: bool = False, verbose: bool = False,
                 path_params: Optional[Dict[str, str]] = None):
        self.schema = schema
        self.auth_handler = auth_handler
        self.timeout = timeout
        self.parallel = parallel
        self.verbose = verbose
        self.parser = SchemaParser()
        self.base_url = self.parser.get_base_url(schema)
        # Ensure we always have a valid base URL
        if not self.base_url or not self.base_url.strip():
            self.base_url = 'http://localhost:8000'
            # Update schema to reflect this
            if 'servers' not in schema or not schema.get('servers'):
                schema['servers'] = [{'url': self.base_url}]
            elif schema.get('servers') and isinstance(schema['servers'][0], dict):
                schema['servers'][0]['url'] = self.base_url
        self.path_params = path_params or {}
        self.default_path_param_warnings = []
        self.console = Console()
    
    def run_tests(self, progress=None, task=None) -> TestResults:
        """
        Run tests for all endpoints in the schema
        
        Args:
            progress: Optional Rich Progress object for progress indication
            task: Optional Rich task ID for progress updates
        
        Returns:
            TestResults object with all test results
        """
        start_time = time.time()
        test_results = TestResults()
        paths = self.parser.get_paths(self.schema)
        
        # Collect all test cases
        test_cases = []
        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            
            methods = ['get', 'post', 'put', 'delete', 'patch', 'head', 'options']
            for method in methods:
                if method in path_item:
                    test_cases.append((method.upper(), path, path_item[method]))
        
        if not test_cases:
            return test_results
        
        # Run tests (parallel or sequential)
        if self.parallel:
            test_results = self._run_tests_parallel(test_cases)
        else:
            for method, path, operation in test_cases:
                result = self._test_endpoint(method, path, operation)
                test_results.add_result(result)
                if progress and task is not None:
                    progress.update(task, advance=1)
        
        test_results.total_time_seconds = time.time() - start_time
        return test_results
    
    def _run_tests_parallel(self, test_cases: List[tuple]) -> TestResults:
        """Run tests in parallel"""
        test_results = TestResults()
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(self._test_endpoint, method, path, operation): (method, path)
                for method, path, operation in test_cases
            }
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    test_results.add_result(result)
                except Exception as e:
                    method, path = futures[future]
                    error_result = TestResult(
                        method=method,
                        path=path,
                        status_code=0,
                        status=TestStatus.ERROR,
                        error_message=f"Test execution error: {str(e)}"
                    )
                    test_results.add_result(error_result)
        
        return test_results
    
    def _test_endpoint(self, method: str, path: str, operation: Dict[str, Any]) -> TestResult:
        """
        Test a single endpoint
        
        Args:
            method: HTTP method
            path: API path
            operation: OpenAPI operation object
            
        Returns:
            TestResult object
        """
        # Build URL
        url = self._build_url(path, operation)
        
        # Get expected status code
        expected_status = self._get_expected_status_code(operation)
        
        # Build request
        headers = self.auth_handler.get_headers()
        params = self.auth_handler.get_query_params()
        
        # Add content-type if needed
        if method in ['POST', 'PUT', 'PATCH']:
            headers.setdefault('Content-Type', 'application/json')
        
        # Build request body if needed
        data = None
        json_data = None
        if method in ['POST', 'PUT', 'PATCH']:
            # Try to get request body from schema
            request_body = operation.get('requestBody', {})
            if request_body:
                # Generate minimal test data
                json_data = self._generate_test_data(request_body)
        
        # Execute request
        start_time = time.time()
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data,
                data=data,
                timeout=self.timeout,
                allow_redirects=False
            )
            response_time_ms = (time.time() - start_time) * 1000
            response_size = len(response.content)
            
            # Parse response based on Content-Type
            response_body = None
            content_type = response.headers.get('Content-Type', '').lower()
            
            if response.content:
                try:
                    if 'application/json' in content_type or 'application/vnd.api+json' in content_type:
                        response_body = response.json()
                    elif 'application/xml' in content_type or 'text/xml' in content_type:
                        # XML response - can't validate with JSON schema, but store as string
                        response_body = {'_xml_content': response.text}
                    elif 'text/' in content_type:
                        # Text response - store as string
                        response_body = {'_text_content': response.text}
                    else:
                        # Try JSON anyway (some APIs don't set Content-Type correctly)
                        try:
                            response_body = response.json()
                        except:
                            response_body = {'_raw_content': response.text[:500]}  # Truncate long responses
                except Exception as e:
                    if self.verbose:
                        self.console.print(f"[dim]Warning: Could not parse response: {e}[/dim]")
                    response_body = None
            
            # Validate response
            status = TestStatus.PASS
            error_message = None
            schema_mismatch = False
            schema_errors = []
            
            # Check status code
            if expected_status and response.status_code != expected_status:
                status = TestStatus.FAIL
                error_message = f"Expected {expected_status}, got {response.status_code}"
            
            # Check response schema (only for JSON responses)
            if response.status_code < 400 and operation.get('responses'):
                content_type = response.headers.get('Content-Type', '').lower()
                if 'application/json' in content_type or 'application/vnd.api+json' in content_type:
                    schema_errors = self._validate_response_schema(
                        response_body, response.status_code, operation.get('responses', {})
                    )
                    if schema_errors:
                        schema_mismatch = True
                        status = TestStatus.WARNING if status == TestStatus.PASS else status
                elif content_type and 'json' not in content_type:
                    # Non-JSON response - can't validate schema, but that's OK
                    if self.verbose:
                        self.console.print(f"[dim]Skipping schema validation for Content-Type: {content_type}[/dim]")
            
            result = TestResult(
                method=method,
                path=path,
                status_code=response.status_code,
                expected_status=expected_status,
                response_time_ms=response_time_ms,
                status=status,
                error_message=error_message,
                schema_mismatch=schema_mismatch,
                schema_errors=schema_errors,
                response_body=response_body,
                response_size_bytes=response_size
            )
            
        except requests.exceptions.Timeout:
            result = TestResult(
                method=method,
                path=path,
                status_code=0,
                status=TestStatus.ERROR,
                error_message=f"Request timeout after {self.timeout}s (try increasing with --timeout)"
            )
        except requests.exceptions.ConnectionError as e:
            error_msg = str(e)
            if "Failed to resolve" in error_msg or "Name or service not known" in error_msg:
                error_msg = f"Cannot connect to {url}. Check if the server is running and the base URL is correct."
            result = TestResult(
                method=method,
                path=path,
                status_code=0,
                status=TestStatus.ERROR,
                error_message=f"Connection error: {error_msg}"
            )
        except Exception as e:
            result = TestResult(
                method=method,
                path=path,
                status_code=0,
                status=TestStatus.ERROR,
                error_message=f"Unexpected error: {str(e)}. Run with --verbose for details."
            )
        
        return result
    
    def _build_url(self, path: str, operation: Optional[Dict[str, Any]] = None) -> str:
        """
        Build full URL from base URL and path
        
        Args:
            path: API path with potential parameters
            operation: OpenAPI operation object (for parameter schema)
        """
        base = self.base_url.rstrip('/')
        path = path.lstrip('/')
        
        # Replace path parameters with test values based on schema
        import re
        
        # Find all path parameters
        param_matches = re.finditer(r'\{([^}]+)\}', path)
        
        for match in param_matches:
            param_name = match.group(1)
            
            # Check if custom value provided
            if param_name in self.path_params:
                test_value = self.path_params[param_name]
            else:
                # Generate default value and warn
                test_value = self._generate_path_param_value(param_name, operation)
                warning_msg = f"⚠ Using default path parameter: {param_name}={test_value}"
                if warning_msg not in self.default_path_param_warnings:
                    self.default_path_param_warnings.append(warning_msg)
                    if self.verbose:
                        self.console.print(f"[yellow]{warning_msg}[/yellow] (for path: {path})")
            
            path = path.replace(f'{{{param_name}}}', str(test_value))
        
        return f"{base}/{path}"
    
    def _generate_path_param_value(self, param_name: str, operation: Optional[Dict[str, Any]]) -> Any:
        """
        Generate test value for path parameter based on schema
        
        Args:
            param_name: Parameter name
            operation: OpenAPI operation object
            
        Returns:
            Test value for the parameter
        """
        if operation:
            parameters = operation.get('parameters', [])
            for param in parameters:
                if param.get('in') == 'path' and param.get('name') == param_name:
                    schema = param.get('schema', {})
                    param_type = schema.get('type', 'string')
                    param_format = schema.get('format', '')
                    
                    # Generate based on type and format
                    if param_type == 'integer':
                        return 1
                    elif param_type == 'number':
                        return 1.0
                    elif param_format == 'uuid':
                        return '123e4567-e89b-12d3-a456-426614174000'
                    elif param_format == 'date':
                        return '2024-01-01'
                    elif param_format == 'date-time':
                        return '2024-01-01T00:00:00Z'
                    else:
                        return 'test'
        
        # Default fallback
        return 1
    
    def _get_expected_status_code(self, operation: Dict[str, Any]) -> Optional[int]:
        """Get expected status code from operation"""
        responses = operation.get('responses', {})
        
        # Look for 2xx status codes first
        for status_code in ['200', '201', '202', '204']:
            if status_code in responses:
                return int(status_code)
        
        # Return first available status code
        if responses:
            first_status = list(responses.keys())[0]
            if first_status.isdigit():
                return int(first_status)
        
        return None
    
    def _generate_test_data(self, request_body: Dict[str, Any]) -> Dict[str, Any]:
        """Generate test data for request body, using examples if available"""
        content = request_body.get('content', {})
        
        # Try to find JSON schema
        json_content = content.get('application/json', {})
        schema = json_content.get('schema', {})
        
        # Check for example or examples in content
        if 'example' in json_content:
            return json_content['example']
        if 'examples' in json_content and json_content['examples']:
            # Use first example
            first_example = list(json_content['examples'].values())[0]
            if isinstance(first_example, dict) and 'value' in first_example:
                return first_example['value']
            return first_example
        
        # Generate data based on schema
        data = {}
        properties = schema.get('properties', {})
        required = schema.get('required', [])
        
        for prop_name, prop_schema in properties.items():
            # Use example from property schema if available
            if 'example' in prop_schema:
                data[prop_name] = prop_schema['example']
                continue
            
            # Use enum first value if available
            if 'enum' in prop_schema and prop_schema['enum']:
                data[prop_name] = prop_schema['enum'][0]
                continue
            
            prop_type = prop_schema.get('type', 'string')
            prop_format = prop_schema.get('format', '')
            
            # Generate test values based on type and format
            if prop_type == 'string':
                if prop_format == 'email':
                    data[prop_name] = 'test@example.com'
                elif prop_format == 'date':
                    data[prop_name] = '2024-01-01'
                elif prop_format == 'date-time':
                    data[prop_name] = '2024-01-01T00:00:00Z'
                elif prop_format == 'uri':
                    data[prop_name] = 'https://example.com'
                elif prop_format == 'uuid':
                    data[prop_name] = '123e4567-e89b-12d3-a456-426614174000'
                else:
                    data[prop_name] = 'test'
            elif prop_type == 'integer':
                data[prop_name] = prop_schema.get('minimum', 1) if 'minimum' in prop_schema else 1
            elif prop_type == 'number':
                data[prop_name] = float(prop_schema.get('minimum', 1.0)) if 'minimum' in prop_schema else 1.0
            elif prop_type == 'boolean':
                data[prop_name] = True
            elif prop_type == 'array':
                items_schema = prop_schema.get('items', {})
                if items_schema:
                    # Generate one item for array
                    item_type = items_schema.get('type', 'string')
                    if item_type == 'string':
                        data[prop_name] = ['test']
                    elif item_type == 'integer':
                        data[prop_name] = [1]
                    else:
                        data[prop_name] = []
                else:
                    data[prop_name] = []
            elif prop_type == 'object':
                # Recursively generate nested object
                nested_props = prop_schema.get('properties', {})
                if nested_props:
                    nested_data = {}
                    for nested_name, nested_schema in nested_props.items():
                        nested_type = nested_schema.get('type', 'string')
                        if nested_type == 'string':
                            nested_data[nested_name] = 'test'
                        elif nested_type == 'integer':
                            nested_data[nested_name] = 1
                        else:
                            nested_data[nested_name] = None
                    data[prop_name] = nested_data
                else:
                    data[prop_name] = {}
        
        return data
    
    def _validate_response_schema(self, response_body: Any, status_code: int, 
                                  responses: Dict[str, Any]) -> List[str]:
        """Validate response schema using jsonschema"""
        errors = []
        
        # Find response definition for this status code
        status_key = str(status_code)
        if status_key not in responses:
            # Check for default or wildcard
            status_key = 'default' if 'default' in responses else None
        
        if not status_key:
            return errors
        
        response_def = responses[status_key]
        content = response_def.get('content', {})
        
        # Try to find JSON schema
        json_content = content.get('application/json') or content.get('application/vnd.api+json')
        
        if not json_content:
            # No JSON schema defined, skip validation
            return errors
        
        schema = json_content.get('schema')
        if not schema:
            return errors
        
        # Resolve $ref references if present
        resolved_schema = self._resolve_schema_refs(schema)
        
        # Validate response against schema
        try:
            jsonschema.validate(instance=response_body, schema=resolved_schema)
        except jsonschema.ValidationError as e:
            errors.append(f"Schema validation failed: {e.message}")
            if e.path:
                errors.append(f"  Path: {'/'.join(str(p) for p in e.path)}")
        except jsonschema.SchemaError as e:
            errors.append(f"Invalid schema definition: {e.message}")
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
        
        return errors
    
    def _resolve_schema_refs(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve $ref references in schema
        Basic implementation - resolves components/schemas references
        """
        if not isinstance(schema, dict):
            return schema
        
        # Check for $ref
        if '$ref' in schema:
            ref_path = schema['$ref']
            if ref_path.startswith('#/components/schemas/'):
                schema_name = ref_path.replace('#/components/schemas/', '')
                components = self.schema.get('components', {})
                schemas = components.get('schemas', {})
                if schema_name in schemas:
                    return self._resolve_schema_refs(schemas[schema_name])
        
        # Recursively resolve nested references
        resolved = {}
        for key, value in schema.items():
            if isinstance(value, dict):
                resolved[key] = self._resolve_schema_refs(value)
            elif isinstance(value, list):
                resolved[key] = [self._resolve_schema_refs(item) if isinstance(item, dict) else item for item in value]
            else:
                resolved[key] = value
        
        return resolved

