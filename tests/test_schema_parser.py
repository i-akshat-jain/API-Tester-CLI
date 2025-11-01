"""
Tests for schema parser
"""

import pytest
from pathlib import Path
from apitest.schema_parser import SchemaParser


def test_parse_yaml_schema(tmp_path):
    """Test parsing YAML schema file"""
    schema_content = """
openapi: 3.0.0
info:
  title: Test API
  version: 1.0.0
paths:
  /test:
    get:
      responses:
        '200':
          description: OK
"""
    schema_file = tmp_path / "test.yaml"
    schema_file.write_text(schema_content)
    
    parser = SchemaParser()
    schema = parser.parse(schema_file)
    
    assert schema['openapi'] == '3.0.0'
    assert schema['info']['title'] == 'Test API'
    assert '/test' in schema['paths']


def test_get_base_url_openapi3():
    """Test extracting base URL from OpenAPI 3.0 schema"""
    parser = SchemaParser()
    schema = {
        'openapi': '3.0.0',
        'servers': [{'url': 'https://api.example.com/v1'}],
        'paths': {}
    }
    
    base_url = parser.get_base_url(schema)
    assert base_url == 'https://api.example.com/v1'


def test_get_base_url_swagger2():
    """Test extracting base URL from Swagger 2.0 schema"""
    parser = SchemaParser()
    schema = {
        'swagger': '2.0',
        'host': 'api.example.com',
        'schemes': ['https'],
        'basePath': '/v1',
        'paths': {}
    }
    
    base_url = parser.get_base_url(schema)
    assert base_url == 'https://api.example.com/v1'

