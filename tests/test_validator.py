"""
Tests for schema validator
"""

import pytest
from apitest.validator import SchemaValidator, ValidationResult


def test_validate_valid_openapi3():
    """Test validating a valid OpenAPI 3.0 schema"""
    validator = SchemaValidator()
    schema = {
        'openapi': '3.0.0',
        'info': {
            'title': 'Test API',
            'version': '1.0.0'
        },
        'paths': {
            '/test': {
                'get': {
                    'responses': {'200': {'description': 'OK'}}
                }
            }
        }
    }
    
    result = validator.validate(schema)
    assert result.is_valid is True
    assert len(result.errors) == 0


def test_validate_missing_openapi_version():
    """Test validation fails when OpenAPI version is missing"""
    validator = SchemaValidator()
    schema = {
        'info': {'title': 'Test'},
        'paths': {}
    }
    
    result = validator.validate(schema)
    assert result.is_valid is False
    assert len(result.errors) > 0


def test_validate_missing_paths():
    """Test validation fails when paths are missing"""
    validator = SchemaValidator()
    schema = {
        'openapi': '3.0.0',
        'info': {'title': 'Test'}
    }
    
    result = validator.validate(schema)
    assert result.is_valid is False
    assert any('paths' in error.lower() for error in result.errors)


# Edge case tests for robustness

def test_validate_empty_schema():
    """Test validation of empty schema"""
    validator = SchemaValidator()
    schema = {}
    
    result = validator.validate(schema)
    assert result.is_valid is False
    assert len(result.errors) > 0


def test_validate_invalid_openapi_version():
    """Test validation with invalid OpenAPI version"""
    validator = SchemaValidator()
    schema = {
        'openapi': '4.0.0',  # Invalid version
        'info': {'title': 'Test'},
        'paths': {}
    }
    
    result = validator.validate(schema)
    # Should have warnings about unsupported version
    assert len(result.warnings) > 0 or not result.is_valid


def test_validate_invalid_swagger_version():
    """Test validation with invalid Swagger version"""
    validator = SchemaValidator()
    schema = {
        'swagger': '3.0',  # Invalid Swagger version
        'info': {'title': 'Test'},
        'paths': {}
    }
    
    result = validator.validate(schema)
    # Should have warnings about unsupported version
    assert len(result.warnings) > 0 or not result.is_valid


def test_validate_openapi3_missing_info():
    """Test OpenAPI 3.0 validation with missing info section"""
    validator = SchemaValidator()
    schema = {
        'openapi': '3.0.0',
        'paths': {}
    }
    
    result = validator.validate(schema)
    assert result.is_valid is False
    assert any('info' in error.lower() for error in result.errors)


def test_validate_openapi3_info_missing_title():
    """Test OpenAPI 3.0 validation with info missing title"""
    validator = SchemaValidator()
    schema = {
        'openapi': '3.0.0',
        'info': {},
        'paths': {}
    }
    
    result = validator.validate(schema)
    assert result.is_valid is False
    assert any('title' in error.lower() for error in result.errors)


def test_validate_openapi3_empty_paths():
    """Test OpenAPI 3.0 validation with empty paths"""
    validator = SchemaValidator()
    schema = {
        'openapi': '3.0.0',
        'info': {'title': 'Test'},
        'paths': {}
    }
    
    result = validator.validate(schema)
    # Should be valid but with warning
    assert len(result.warnings) > 0


def test_validate_openapi3_path_not_object():
    """Test OpenAPI 3.0 validation with path that's not an object"""
    validator = SchemaValidator()
    schema = {
        'openapi': '3.0.0',
        'info': {'title': 'Test'},
        'paths': {
            '/test': 'invalid'  # Should be object
        }
    }
    
    result = validator.validate(schema)
    assert result.is_valid is False
    assert any('object' in error.lower() for error in result.errors)


def test_validate_openapi3_path_no_methods():
    """Test OpenAPI 3.0 validation with path having no HTTP methods"""
    validator = SchemaValidator()
    schema = {
        'openapi': '3.0.0',
        'info': {'title': 'Test'},
        'paths': {
            '/test': {}  # No methods defined
        }
    }
    
    result = validator.validate(schema)
    assert result.is_valid is False
    assert any('method' in error.lower() for error in result.errors)


def test_validate_swagger2_missing_info():
    """Test Swagger 2.0 validation with missing info"""
    validator = SchemaValidator()
    schema = {
        'swagger': '2.0',
        'paths': {}
    }
    
    result = validator.validate(schema)
    assert result.is_valid is False
    assert any('info' in error.lower() for error in result.errors)


def test_validate_swagger2_missing_host():
    """Test Swagger 2.0 validation with missing host"""
    validator = SchemaValidator()
    schema = {
        'swagger': '2.0',
        'info': {'title': 'Test'},
        'paths': {}
    }
    
    result = validator.validate(schema)
    assert result.is_valid is False
    assert any('host' in error.lower() for error in result.errors)


def test_validate_openapi3_with_valid_path():
    """Test OpenAPI 3.0 validation with valid path and method"""
    validator = SchemaValidator()
    schema = {
        'openapi': '3.0.0',
        'info': {'title': 'Test API'},
        'paths': {
            '/test': {
                'get': {
                    'responses': {'200': {'description': 'OK'}}
                }
            }
        }
    }
    
    result = validator.validate(schema)
    assert result.is_valid is True
    assert len(result.errors) == 0


def test_validate_swagger2_with_valid_path():
    """Test Swagger 2.0 validation with valid path and method"""
    validator = SchemaValidator()
    schema = {
        'swagger': '2.0',
        'info': {'title': 'Test API'},
        'host': 'api.example.com',
        'schemes': ['https'],
        'paths': {
            '/test': {
                'get': {
                    'responses': {'200': {'description': 'OK'}}
                }
            }
        }
    }
    
    result = validator.validate(schema)
    assert result.is_valid is True
    assert len(result.errors) == 0


def test_validate_openapi3_multiple_paths():
    """Test OpenAPI 3.0 validation with multiple paths"""
    validator = SchemaValidator()
    schema = {
        'openapi': '3.0.0',
        'info': {'title': 'Test API'},
        'paths': {
            '/test1': {
                'get': {'responses': {'200': {'description': 'OK'}}}
            },
            '/test2': {
                'post': {'responses': {'201': {'description': 'Created'}}}
            }
        }
    }
    
    result = validator.validate(schema)
    assert result.is_valid is True

