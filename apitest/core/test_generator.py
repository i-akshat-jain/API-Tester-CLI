"""
Test data generator for API requests

This module provides functionality for generating test data based on OpenAPI schemas.
It will be extended to support intelligent data generation using learned patterns.
"""

from typing import Dict, Any, Optional


class TestGenerator:
    """Generate test data for API requests based on OpenAPI schemas"""
    
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

