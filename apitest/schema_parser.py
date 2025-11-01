"""
OpenAPI/Swagger schema parser
"""

import json
import yaml
from pathlib import Path
from typing import Dict, Any


class SchemaParser:
    """Parse OpenAPI/Swagger schema files"""
    
    def parse(self, schema_path: Path) -> Dict[str, Any]:
        """
        Parse an OpenAPI schema file (YAML or JSON)
        
        Args:
            schema_path: Path to the schema file
            
        Returns:
            Parsed schema dictionary
        """
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")
        
        content = schema_path.read_text(encoding='utf-8')
        
        # Determine format and parse
        if schema_path.suffix.lower() in ['.yaml', '.yml']:
            try:
                schema = yaml.safe_load(content)
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML format: {str(e)}")
        elif schema_path.suffix.lower() == '.json':
            try:
                schema = json.loads(content)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON format: {str(e)}")
        else:
            # Try YAML first, then JSON
            try:
                schema = yaml.safe_load(content)
            except yaml.YAMLError:
                try:
                    schema = json.loads(content)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Could not parse schema file: {str(e)}")
        
        if not isinstance(schema, dict):
            raise ValueError("Schema must be a dictionary/object")
        
        return schema
    
    def get_base_url(self, schema: Dict[str, Any]) -> str:
        """
        Extract base URL from schema
        
        Args:
            schema: Parsed schema dictionary
            
        Returns:
            Base URL string
        """
        # OpenAPI 3.0
        if 'servers' in schema and schema['servers']:
            server = schema['servers'][0]
            if isinstance(server, dict):
                return server.get('url', '')
            elif isinstance(server, str):
                return server
        
        # OpenAPI 2.0 / Swagger
        if 'host' in schema:
            protocol = schema.get('schemes', ['https'])[0]
            host = schema['host']
            base_path = schema.get('basePath', '')
            return f"{protocol}://{host}{base_path}"
        
        return ''
    
    def get_paths(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Extract paths from schema"""
        return schema.get('paths', {})
    
    def get_security_schemes(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Extract security schemes from schema"""
        components = schema.get('components', {})
        return components.get('securitySchemes', {})
    
    def get_security_requirements(self, schema: Dict[str, Any]) -> list:
        """Extract global security requirements from schema"""
        return schema.get('security', [])

