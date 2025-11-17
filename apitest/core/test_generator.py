"""
Test data generator for API requests

This module provides functionality for generating test data based on OpenAPI schemas.
It will be extended to support intelligent data generation using learned patterns.
"""

from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass


@dataclass
class TestCase:
    """Represents a test case for an API endpoint"""
    method: str
    path: str
    request_body: Optional[Dict[str, Any]] = None
    expected_response: Optional[Dict[str, Any]] = None
    test_scenario: Optional[str] = None
    is_ai_generated: bool = False
    ai_metadata: Optional[Dict[str, Any]] = None


class TestGenerator:
    """
    Generate test data for API requests based on OpenAPI schemas.
    
    Supports multiple generation modes:
    - schema: Traditional schema-based generation (fast, deterministic)
    - ai: AI-powered test generation (creative, exploratory)
    - hybrid: Both strategies combined
    """
    
    def __init__(self, mode: str = 'schema', ai_config: Optional[Any] = None, storage: Optional[Any] = None):
        """
        Initialize test generator
        
        Args:
            mode: Generation mode ('schema', 'ai', or 'hybrid')
            ai_config: Optional AIConfig instance for AI generation
            storage: Optional Storage instance for accessing history/patterns
        """
        self.mode = mode
        self.ai_config = ai_config
        self.storage = storage
    
    def generate_tests(self, schema: Dict[str, Any], endpoints: List[Tuple[str, str, Dict[str, Any]]]) -> List[TestCase]:
        """
        Generate tests for endpoints based on mode
        
        Args:
            schema: OpenAPI schema dictionary
            endpoints: List of (method, path, operation) tuples
            
        Returns:
            List of TestCase objects
        """
        if self.mode == 'schema':
            return self._generate_schema_tests(schema, endpoints)
        elif self.mode == 'ai':
            return self._generate_ai_tests(schema, endpoints)
        elif self.mode == 'hybrid':
            schema_tests = self._generate_schema_tests(schema, endpoints)
            ai_tests = self._generate_ai_tests(schema, endpoints)
            return self._combine_tests(schema_tests, ai_tests)
        else:
            # Default to schema mode
            return self._generate_schema_tests(schema, endpoints)
    
    def _generate_schema_tests(self, schema: Dict[str, Any], endpoints: List[Tuple[str, str, Dict[str, Any]]]) -> List[TestCase]:
        """
        Generate tests using schema-based generation
        
        Args:
            schema: OpenAPI schema dictionary
            endpoints: List of (method, path, operation) tuples
            
        Returns:
            List of TestCase objects
        """
        test_cases = []
        
        for method, path, operation in endpoints:
            # Generate request body if needed
            request_body_data = None
            if method in ['POST', 'PUT', 'PATCH']:
                request_body = operation.get('requestBody', {})
                if request_body:
                    # Use smart generation if storage is available
                    use_smart = self.storage is not None
                    schema_file = getattr(self, 'schema_file', None) if hasattr(self, 'schema_file') else None
                    
                    request_body_data = self.generate_test_data(
                        request_body,
                        schema_file=schema_file,
                        method=method,
                        path=path,
                        use_smart_generation=use_smart
                    )
            
            # Extract expected response from schema
            expected_response = None
            responses = operation.get('responses', {})
            if '200' in responses:
                expected_response = responses['200']
            elif '201' in responses:
                expected_response = responses['201']
            
            test_case = TestCase(
                method=method,
                path=path,
                request_body=request_body_data,
                expected_response=expected_response,
                test_scenario=f"Schema-based test for {method} {path}",
                is_ai_generated=False
            )
            test_cases.append(test_case)
        
        return test_cases
    
    def _generate_ai_tests(self, schema: Dict[str, Any], endpoints: List[Tuple[str, str, Dict[str, Any]]]) -> List[TestCase]:
        """
        Generate tests using AI (placeholder for now)
        
        Args:
            schema: OpenAPI schema dictionary
            endpoints: List of (method, path, operation) tuples
            
        Returns:
            List of TestCase objects (empty for now, will be implemented in Phase 2)
        """
        # TODO: Implement AI test generation in Phase 2
        # For now, return empty list
        return []
    
    def _combine_tests(self, schema_tests: List[TestCase], ai_tests: List[TestCase]) -> List[TestCase]:
        """
        Combine tests from schema and AI generators, deduplicating similar tests
        
        Args:
            schema_tests: Tests from schema generator
            ai_tests: Tests from AI generator
            
        Returns:
            Combined and deduplicated list of TestCase objects
        """
        combined = list(schema_tests)
        
        # Add AI tests, checking for duplicates
        for ai_test in ai_tests:
            # Check if similar test already exists
            is_duplicate = False
            for existing_test in combined:
                if (existing_test.method == ai_test.method and
                    existing_test.path == ai_test.path and
                    self._are_similar_requests(existing_test.request_body, ai_test.request_body)):
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                combined.append(ai_test)
        
        return combined
    
    def _are_similar_requests(self, req1: Optional[Dict[str, Any]], req2: Optional[Dict[str, Any]]) -> bool:
        """
        Check if two request bodies are similar (simple comparison for now)
        
        Args:
            req1: First request body
            req2: Second request body
            
        Returns:
            True if requests are similar, False otherwise
        """
        if req1 is None and req2 is None:
            return True
        if req1 is None or req2 is None:
            return False
        
        # Simple comparison: check if keys match
        return set(req1.keys()) == set(req2.keys())
    
    @staticmethod
    def generate_test_data(request_body: Dict[str, Any], 
                          schema_file: Optional[str] = None,
                          method: Optional[str] = None,
                          path: Optional[str] = None,
                          use_smart_generation: bool = False) -> Dict[str, Any]:
        """
        Generate test data for request body, using examples if available
        
        Args:
            request_body: OpenAPI request body definition
            schema_file: Optional schema file identifier (for smart generation)
            method: Optional HTTP method (for smart generation)
            path: Optional endpoint path (for smart generation)
            use_smart_generation: Whether to use learned patterns for generation
            
        Returns:
            Dictionary of test data
        """
        # Use smart generation if enabled and schema_file is provided
        if use_smart_generation and schema_file:
            try:
                from apitest.learning.data_generator import SmartDataGenerator
                smart_generator = SmartDataGenerator(
                    schema_file=schema_file,
                    method=method,
                    path=path
                )
                return smart_generator.generate_smart_test_data(request_body)
            except Exception as e:
                # Fall back to regular generation if smart generation fails
                import logging
                logger = logging.getLogger(__name__)
                logger.debug(f"Smart generation failed, using fallback: {e}")
        
        # Regular schema-based generation
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

