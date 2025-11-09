"""
Smart test data generator using learned patterns

This module generates intelligent test data by leveraging patterns
extracted from successful test runs.
"""

import random
from typing import Dict, Any, Optional
import logging

from apitest.core.test_generator import TestGenerator
from apitest.learning.pattern_extractor import PatternExtractor

logger = logging.getLogger(__name__)


class SmartDataGenerator:
    """Generate smart test data using learned patterns"""
    
    def __init__(self, schema_file: str, method: Optional[str] = None, 
                 path: Optional[str] = None):
        """
        Initialize smart data generator
        
        Args:
            schema_file: Schema file identifier
            method: Optional HTTP method filter
            path: Optional endpoint path filter
        """
        self.schema_file = schema_file
        self.method = method
        self.path = path
        self.pattern_extractor = PatternExtractor()
        self._patterns_cache: Optional[Dict[str, Any]] = None
        self._relationships_cache: Optional[Dict[str, Any]] = None
        self._context_data: Dict[str, Any] = {}  # Store context from previous requests
    
    def generate_smart_test_data(self, request_body: Dict[str, Any], 
                                 context_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate smart test data using learned patterns
        
        Checks for learned patterns first, then falls back to schema-based generation.
        Respects constraints (min/max, patterns, enums).
        Uses context from previous successful requests and related endpoint responses.
        
        Args:
            request_body: OpenAPI request body definition
            context_data: Optional context data from previous requests (e.g., user_id from GET /users)
            
        Returns:
            Dictionary of smart test data
        """
        # Update context with provided data
        if context_data:
            self._context_data.update(context_data)
        
        # Get learned patterns (cached)
        patterns = self._get_patterns()
        
        # Get relationships for context awareness
        relationships = self._get_relationships()
        
        # Extract schema from request body
        content = request_body.get('content', {})
        json_content = content.get('application/json', {})
        schema = json_content.get('schema', {})
        
        # Check for example or examples in content (highest priority)
        if 'example' in json_content:
            return json_content['example']
        if 'examples' in json_content and json_content['examples']:
            first_example = list(json_content['examples'].values())[0]
            if isinstance(first_example, dict) and 'value' in first_example:
                return first_example['value']
            return first_example
        
        # Generate data using smart patterns
        data = {}
        properties = schema.get('properties', {})
        required = schema.get('required', [])
        
        for prop_name, prop_schema in properties.items():
            # Priority 1: Use context data (values from previous successful requests)
            if prop_name in self._context_data:
                data[prop_name] = self._context_data[prop_name]
                continue
            
            # Priority 2: Use related endpoint responses (e.g., GET /users → user_id)
            related_value = self._get_related_value(prop_name, relationships)
            if related_value is not None:
                data[prop_name] = related_value
                continue
            
            # Priority 3: Try to use learned pattern for this field
            smart_value = self._generate_field_value(prop_name, prop_schema, patterns)
            
            if smart_value is not None:
                data[prop_name] = smart_value
            else:
                # Priority 4: Fall back to schema-based generation
                data[prop_name] = self._generate_from_schema(prop_schema)
        
        return data
    
    def _get_patterns(self) -> Dict[str, Any]:
        """Get learned patterns (with caching)"""
        if self._patterns_cache is None:
            try:
                self._patterns_cache = self.pattern_extractor.extract_common_values(
                    schema_file=self.schema_file,
                    method=self.method,
                    path=self.path,
                    min_occurrences=2
                )
                logger.debug(f"Loaded {len(self._patterns_cache)} learned patterns")
            except Exception as e:
                logger.warning(f"Failed to load learned patterns: {e}")
                self._patterns_cache = {}
        
        return self._patterns_cache
    
    def _get_relationships(self) -> Dict[str, Any]:
        """Get learned relationships (with caching)"""
        if self._relationships_cache is None:
            try:
                self._relationships_cache = self.pattern_extractor.learn_data_relationships(
                    schema_file=self.schema_file
                )
                logger.debug(f"Loaded {len(self._relationships_cache.get('field_relationships', {}))} field relationships")
            except Exception as e:
                logger.warning(f"Failed to load relationships: {e}")
                self._relationships_cache = {}
        
        return self._relationships_cache
    
    def _get_related_value(self, field_name: str, relationships: Dict[str, Any]) -> Optional[Any]:
        """
        Get value from related endpoint responses
        
        Example: If field is 'user_id', check if GET /users/{id} response has an 'id' field
        and use that value.
        
        Args:
            field_name: Name of the field
            relationships: Relationships dictionary
            
        Returns:
            Related value or None if not found
        """
        field_relationships = relationships.get('field_relationships', {})
        
        if field_name in field_relationships:
            relationship = field_relationships[field_name]
            related_data = relationship.get('related_data', {})
            target_field = relationship.get('target_field', 'id')
            
            # Extract value from related data
            if isinstance(related_data, dict):
                # Try direct field access
                if target_field in related_data:
                    return related_data[target_field]
                
                # Try nested access (e.g., 'user.id')
                if '.' in target_field:
                    parts = target_field.split('.')
                    value = related_data
                    for part in parts:
                        if isinstance(value, dict) and part in value:
                            value = value[part]
                        else:
                            return None
                    return value
        
        return None
    
    def _generate_field_value(self, field_name: str, prop_schema: Dict[str, Any],
                              patterns: Dict[str, Any]) -> Optional[Any]:
        """
        Generate value for a field using learned patterns
        
        Args:
            field_name: Name of the field
            prop_schema: Property schema definition
            patterns: Learned patterns dictionary
            
        Returns:
            Generated value or None if no pattern available
        """
        # Check if we have patterns for this field
        if field_name not in patterns:
            return None
        
        field_patterns = patterns[field_name]
        
        # Priority 1: Use common values if available
        if 'common_values' in field_patterns and field_patterns['common_values']:
            # Use most common value
            most_common = field_patterns['common_values'][0]
            value_str = most_common[0]
            
            # Convert to appropriate type based on schema
            return self._convert_to_type(value_str, prop_schema)
        
        # Priority 2: Use pattern constraints
        if 'patterns' in field_patterns:
            pattern_info = field_patterns['patterns']
            return self._generate_from_patterns(pattern_info, prop_schema)
        
        return None
    
    def _generate_from_patterns(self, pattern_info: Dict[str, Any],
                                prop_schema: Dict[str, Any]) -> Any:
        """
        Generate value from pattern information
        
        Args:
            pattern_info: Pattern information dictionary
            prop_schema: Property schema definition
            
        Returns:
            Generated value
        """
        prop_type = prop_schema.get('type', 'string')
        detected_type = pattern_info.get('type', prop_type)
        
        # Respect schema type first, but use pattern info for constraints
        if prop_type == 'string' or detected_type == 'str':
            # Use format if detected
            if 'format' in pattern_info:
                formats = pattern_info['format'].split('|')
                format_type = formats[0]  # Use first format
                return self._generate_formatted_string(format_type)
            
            # Use length constraints
            if 'min_length' in pattern_info and 'max_length' in pattern_info:
                min_len = int(pattern_info['min_length'])
                max_len = int(pattern_info['max_length'])
                avg_len = int(pattern_info.get('avg_length', (min_len + max_len) // 2))
                # Generate string of average length
                return 'x' * max(1, avg_len)
            elif 'min_length' in pattern_info:
                return 'x' * max(1, int(pattern_info['min_length']))
            elif 'max_length' in pattern_info:
                return 'x' * max(1, min(int(pattern_info['max_length']), 50))
            
            return 'test'
        
        elif prop_type == 'integer' or detected_type == 'int':
            # Use numeric constraints
            if 'min_value' in pattern_info and 'max_value' in pattern_info:
                min_val = int(pattern_info['min_value'])
                max_val = int(pattern_info['max_value'])
                avg_val = int(pattern_info.get('avg_value', (min_val + max_val) // 2))
                # Use average value, but respect schema minimum if set
                schema_min = prop_schema.get('minimum')
                if schema_min is not None:
                    return max(schema_min, avg_val)
                return avg_val
            elif 'min_value' in pattern_info:
                return int(pattern_info['min_value'])
            elif 'max_value' in pattern_info:
                return int(pattern_info['max_value'])
            
            # Fall back to schema minimum or default
            return prop_schema.get('minimum', 1) if 'minimum' in prop_schema else 1
        
        elif prop_type == 'number' or detected_type == 'float':
            # Use numeric constraints
            if 'min_value' in pattern_info and 'max_value' in pattern_info:
                min_val = float(pattern_info['min_value'])
                max_val = float(pattern_info['max_value'])
                avg_val = float(pattern_info.get('avg_value', (min_val + max_val) / 2))
                # Use average value, but respect schema minimum if set
                schema_min = prop_schema.get('minimum')
                if schema_min is not None:
                    return max(schema_min, avg_val)
                return avg_val
            elif 'min_value' in pattern_info:
                return float(pattern_info['min_value'])
            elif 'max_value' in pattern_info:
                return float(pattern_info['max_value'])
            
            # Fall back to schema minimum or default
            return float(prop_schema.get('minimum', 1.0)) if 'minimum' in prop_schema else 1.0
        
        elif prop_type == 'boolean' or detected_type == 'bool':
            return True
        
        return None
    
    def _generate_from_schema(self, prop_schema: Dict[str, Any]) -> Any:
        """
        Generate value from schema (fallback method)
        
        Args:
            prop_schema: Property schema definition
            
        Returns:
            Generated value
        """
        # Use example from property schema if available
        if 'example' in prop_schema:
            return prop_schema['example']
        
        # Use enum first value if available
        if 'enum' in prop_schema and prop_schema['enum']:
            return prop_schema['enum'][0]
        
        prop_type = prop_schema.get('type', 'string')
        prop_format = prop_schema.get('format', '')
        
        # Generate test values based on type and format
        if prop_type == 'string':
            if prop_format == 'email':
                return 'test@example.com'
            elif prop_format == 'date':
                return '2024-01-01'
            elif prop_format == 'date-time':
                return '2024-01-01T00:00:00Z'
            elif prop_format == 'uri':
                return 'https://example.com'
            elif prop_format == 'uuid':
                return '123e4567-e89b-12d3-a456-426614174000'
            else:
                return 'test'
        elif prop_type == 'integer':
            return prop_schema.get('minimum', 1) if 'minimum' in prop_schema else 1
        elif prop_type == 'number':
            return float(prop_schema.get('minimum', 1.0)) if 'minimum' in prop_schema else 1.0
        elif prop_type == 'boolean':
            return True
        elif prop_type == 'array':
            items_schema = prop_schema.get('items', {})
            if items_schema:
                item_type = items_schema.get('type', 'string')
                if item_type == 'string':
                    return ['test']
                elif item_type == 'integer':
                    return [1]
                else:
                    return []
            else:
                return []
        elif prop_type == 'object':
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
                return nested_data
            else:
                return {}
        
        return None
    
    def _convert_to_type(self, value_str: str, prop_schema: Dict[str, Any]) -> Any:
        """
        Convert string value to appropriate type based on schema
        
        Args:
            value_str: String value to convert
            prop_schema: Property schema definition
            
        Returns:
            Converted value
        """
        prop_type = prop_schema.get('type', 'string')
        
        if prop_type == 'integer':
            try:
                return int(value_str)
            except (ValueError, TypeError):
                return 1
        elif prop_type == 'number':
            try:
                return float(value_str)
            except (ValueError, TypeError):
                return 1.0
        elif prop_type == 'boolean':
            if value_str.lower() in ('true', '1', 'yes', 'on'):
                return True
            elif value_str.lower() in ('false', '0', 'no', 'off'):
                return False
            return True
        else:
            return value_str
    
    def _generate_formatted_string(self, format_type: str) -> str:
        """
        Generate formatted string based on format type
        
        Args:
            format_type: Format type (email, uuid, date, etc.)
            
        Returns:
            Formatted string
        """
        if format_type == 'email':
            return 'test@example.com'
        elif format_type == 'uuid':
            return '123e4567-e89b-12d3-a456-426614174000'
        elif format_type == 'date':
            return '2024-01-01'
        elif format_type == 'date-time':
            return '2024-01-01T00:00:00Z'
        elif format_type == 'uri':
            return 'https://example.com'
        else:
            return 'test'

