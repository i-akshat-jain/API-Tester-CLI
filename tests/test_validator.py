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

