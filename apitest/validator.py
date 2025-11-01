"""
Schema validation utilities
"""

from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of schema validation"""
    is_valid: bool
    errors: List[str]
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class SchemaValidator:
    """Validate OpenAPI schema structure"""
    
    def validate(self, schema: Dict[str, Any]) -> ValidationResult:
        """
        Validate OpenAPI schema structure
        
        Args:
            schema: Schema dictionary to validate
            
        Returns:
            ValidationResult object
        """
        errors = []
        warnings = []
        
        # Check for required fields
        if 'openapi' not in schema and 'swagger' not in schema:
            errors.append("Schema must specify 'openapi' (v3) or 'swagger' (v2) version")
        
        # Validate OpenAPI version
        openapi_version = schema.get('openapi') or schema.get('swagger', '')
        if openapi_version:
            if openapi_version.startswith('3.'):
                errors.extend(self._validate_openapi3(schema))
            elif openapi_version.startswith('2.'):
                errors.extend(self._validate_swagger2(schema))
            else:
                warnings.append(f"Unsupported OpenAPI version: {openapi_version}")
        
        # Check for paths
        if 'paths' not in schema:
            errors.append("Schema must contain 'paths' section")
        elif not schema['paths']:
            warnings.append("Schema has no endpoints defined in 'paths'")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def _validate_openapi3(self, schema: Dict[str, Any]) -> List[str]:
        """Validate OpenAPI 3.0 specific requirements"""
        errors = []
        
        # Check info section
        if 'info' not in schema:
            errors.append("OpenAPI 3.0 requires 'info' section")
        elif 'title' not in schema.get('info', {}):
            errors.append("'info' section must contain 'title'")
        
        # Validate paths structure
        paths = schema.get('paths', {})
        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                errors.append(f"Path '{path}' must be an object")
                continue
            
            # Check for HTTP methods
            methods = ['get', 'post', 'put', 'delete', 'patch', 'head', 'options']
            has_method = any(method in path_item for method in methods)
            
            if not has_method:
                errors.append(f"Path '{path}' must define at least one HTTP method")
        
        return errors
    
    def _validate_swagger2(self, schema: Dict[str, Any]) -> List[str]:
        """Validate Swagger 2.0 specific requirements"""
        errors = []
        
        # Check info section
        if 'info' not in schema:
            errors.append("Swagger 2.0 requires 'info' section")
        
        # Check host
        if 'host' not in schema:
            errors.append("Swagger 2.0 requires 'host' field")
        
        return errors

