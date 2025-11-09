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


# Edge case tests for robustness

def test_parse_nonexistent_file():
    """Test parsing a file that doesn't exist"""
    parser = SchemaParser()
    with pytest.raises(FileNotFoundError):
        parser.parse(Path('/nonexistent/file.yaml'))


def test_parse_empty_file(tmp_path):
    """Test parsing an empty file"""
    schema_file = tmp_path / "empty.yaml"
    schema_file.write_text("")
    
    parser = SchemaParser()
    with pytest.raises(ValueError):
        parser.parse(schema_file)


def test_parse_invalid_yaml(tmp_path):
    """Test parsing invalid YAML"""
    schema_file = tmp_path / "invalid.yaml"
    schema_file.write_text("invalid: [unclosed")
    
    parser = SchemaParser()
    with pytest.raises(ValueError):
        parser.parse(schema_file)


def test_parse_invalid_json(tmp_path):
    """Test parsing invalid JSON"""
    schema_file = tmp_path / "invalid.json"
    schema_file.write_text("{invalid json}")
    
    parser = SchemaParser()
    with pytest.raises(ValueError):
        parser.parse(schema_file)


def test_parse_non_dict_yaml(tmp_path):
    """Test parsing YAML that's not a dictionary"""
    schema_file = tmp_path / "not_dict.yaml"
    schema_file.write_text("- item1\n- item2")
    
    parser = SchemaParser()
    with pytest.raises(ValueError):
        parser.parse(schema_file)


def test_get_base_url_no_servers():
    """Test getting base URL when servers are missing"""
    parser = SchemaParser()
    schema = {
        'openapi': '3.0.0',
        'paths': {}
    }
    
    base_url = parser.get_base_url(schema)
    assert base_url == ''


def test_get_base_url_empty_servers():
    """Test getting base URL when servers list is empty"""
    parser = SchemaParser()
    schema = {
        'openapi': '3.0.0',
        'servers': [],
        'paths': {}
    }
    
    base_url = parser.get_base_url(schema)
    assert base_url == ''


def test_get_base_url_relative_path():
    """Test getting base URL with relative path (should be rejected)"""
    parser = SchemaParser()
    schema = {
        'openapi': '3.0.0',
        'servers': [{'url': '/api/v1'}],  # Relative path
        'paths': {}
    }
    
    base_url = parser.get_base_url(schema)
    # Should return empty string for relative paths
    assert base_url == ''


def test_get_base_url_invalid_url():
    """Test getting base URL with invalid URL format"""
    parser = SchemaParser()
    schema = {
        'openapi': '3.0.0',
        'servers': [{'url': 'not-a-url'}],
        'paths': {}
    }
    
    base_url = parser.get_base_url(schema)
    # Should return empty string for invalid URLs
    assert base_url == ''


def test_get_base_url_string_server():
    """Test getting base URL when server is a string"""
    parser = SchemaParser()
    schema = {
        'openapi': '3.0.0',
        'servers': ['https://api.example.com'],
        'paths': {}
    }
    
    base_url = parser.get_base_url(schema)
    assert base_url == 'https://api.example.com'


def test_get_base_url_string_server_relative():
    """Test getting base URL when server string is relative"""
    parser = SchemaParser()
    schema = {
        'openapi': '3.0.0',
        'servers': ['/api/v1'],  # Relative
        'paths': {}
    }
    
    base_url = parser.get_base_url(schema)
    # Should return empty for relative paths
    assert base_url == ''


def test_get_base_url_swagger2_no_host():
    """Test getting base URL from Swagger 2.0 without host"""
    parser = SchemaParser()
    schema = {
        'swagger': '2.0',
        'schemes': ['https'],
        'basePath': '/v1',
        'paths': {}
    }
    
    base_url = parser.get_base_url(schema)
    assert base_url == ''


def test_get_base_url_swagger2_empty_host():
    """Test getting base URL from Swagger 2.0 with empty host"""
    parser = SchemaParser()
    schema = {
        'swagger': '2.0',
        'host': '',
        'schemes': ['https'],
        'basePath': '/v1',
        'paths': {}
    }
    
    base_url = parser.get_base_url(schema)
    assert base_url == ''


def test_get_paths_empty_schema():
    """Test getting paths from empty schema"""
    parser = SchemaParser()
    schema = {}
    
    paths = parser.get_paths(schema)
    assert paths == {}


def test_get_paths_no_paths_key():
    """Test getting paths when paths key is missing"""
    parser = SchemaParser()
    schema = {'openapi': '3.0.0'}
    
    paths = parser.get_paths(schema)
    assert paths == {}


def test_get_security_schemes_no_components():
    """Test getting security schemes when components are missing"""
    parser = SchemaParser()
    schema = {'openapi': '3.0.0'}
    
    schemes = parser.get_security_schemes(schema)
    assert schemes == {}


def test_get_security_requirements_no_security():
    """Test getting security requirements when security is missing"""
    parser = SchemaParser()
    schema = {'openapi': '3.0.0'}
    
    requirements = parser.get_security_requirements(schema)
    assert requirements == []


def test_parse_json_file(tmp_path):
    """Test parsing a JSON schema file"""
    schema_file = tmp_path / "schema.json"
    schema_file.write_text('{"openapi": "3.0.0", "paths": {}}')
    
    parser = SchemaParser()
    schema = parser.parse(schema_file)
    assert schema['openapi'] == '3.0.0'


def test_parse_file_no_extension(tmp_path):
    """Test parsing a file with no extension (should try YAML then JSON)"""
    schema_file = tmp_path / "schema"
    schema_file.write_text('openapi: 3.0.0\npaths: {}')
    
    parser = SchemaParser()
    schema = parser.parse(schema_file)
    assert schema['openapi'] == '3.0.0'

