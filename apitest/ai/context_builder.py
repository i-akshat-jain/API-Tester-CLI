"""
Context builder for AI test generation

Builds comprehensive context from schema, history, validated tests, and patterns
to help AI generate better test cases.
"""

import time
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ContextBuilder:
    """
    Build context for AI test generation
    
    Aggregates information from:
    - Schema endpoint details
    - Historical test results
    - Validated AI test cases
    - Learned patterns
    """
    
    def __init__(self, storage):
        """
        Initialize context builder
        
        Args:
            storage: Storage instance with namespaces (results, ai_tests, patterns)
        """
        self.storage = storage
        self._cache: Dict[str, tuple] = {}  # (context, timestamp) cache
        self._cache_ttl = 300  # 5 minutes cache TTL
        self._shared_context_cache: Dict[str, tuple] = {}  # Shared context cache per schema file
    
    def build_context(self, schema: Dict[str, Any], schema_file: str, 
                     method: str, path: str) -> Dict[str, Any]:
        """
        Build comprehensive context for AI test generation
        
        Args:
            schema: OpenAPI schema dictionary
            schema_file: Path/identifier for schema file
            method: HTTP method (GET, POST, etc.)
            path: Endpoint path
            
        Returns:
            Context dictionary with endpoint info, history, examples, and patterns
        """
        # Check cache first
        cache_key = f"{schema_file}:{method}:{path}"
        if cache_key in self._cache:
            cached_context, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                logger.debug(f"Using cached context for {method} {path}")
                return cached_context
        
        # Get shared context (patterns, general validated examples) - cached per schema file
        shared_context = self._get_shared_context(schema_file)
        
        # Build endpoint-specific context
        context = {
            'endpoint': self._extract_endpoint_info(schema, method, path),
            'history': self._get_historical_context(schema_file, method, path),
            'validated_examples': self._get_validated_test_examples(schema_file, method, path),
            'patterns': shared_context['patterns'],  # Use shared patterns
            'schema_file': schema_file
        }
        
        # Cache the result
        self._cache[cache_key] = (context, time.time())
        
        return context
    
    def build_shared_context(self, schema_file: str) -> Dict[str, Any]:
        """
        Build shared context that applies to all endpoints in a schema file
        
        This includes patterns and general validated examples that don't need
        to be fetched per endpoint, reducing token usage.
        
        Args:
            schema_file: Path/identifier for schema file
            
        Returns:
            Dictionary with shared context (patterns, general examples)
        """
        return self._get_shared_context(schema_file)
    
    def _get_shared_context(self, schema_file: str) -> Dict[str, Any]:
        """
        Get or build shared context for a schema file (cached)
        
        Args:
            schema_file: Schema file identifier
            
        Returns:
            Shared context dictionary
        """
        # Check shared context cache
        if schema_file in self._shared_context_cache:
            cached_context, timestamp = self._shared_context_cache[schema_file]
            if time.time() - timestamp < self._cache_ttl:
                logger.debug(f"Using cached shared context for {schema_file}")
                return cached_context
        
        # Build shared context
        shared_context = {
            'patterns': self._get_relevant_patterns(schema_file, None, None),
            'schema_file': schema_file
        }
        
        # Cache the result
        self._shared_context_cache[schema_file] = (shared_context, time.time())
        
        return shared_context
    
    def _extract_endpoint_info(self, schema: Dict[str, Any], method: str, 
                               path: str) -> Dict[str, Any]:
        """
        Extract endpoint details from schema with full schema resolution and examples
        
        Args:
            schema: OpenAPI schema dictionary
            method: HTTP method
            path: Endpoint path
            
        Returns:
            Dictionary with endpoint information including resolved schemas and examples
        """
        paths = schema.get('paths', {})
        path_item = paths.get(path, {})
        operation = path_item.get(method.lower(), {})
        
        endpoint_info = {
            'method': method.upper(),
            'path': path,
            'summary': operation.get('summary', ''),
            'description': operation.get('description', ''),
            'operation_id': operation.get('operationId', ''),
            'tags': operation.get('tags', []),
            'parameters': operation.get('parameters', []),
            'request_body': operation.get('requestBody', {}),
            'responses': operation.get('responses', {}),
            'security': operation.get('security', [])
        }
        
        # Extract and resolve request body schema with examples
        if endpoint_info['request_body']:
            content = endpoint_info['request_body'].get('content', {})
            if content:
                # Prefer application/json
                json_content = content.get('application/json', {})
                if not json_content:
                    # Get first content type
                    first_content_type = list(content.keys())[0]
                    json_content = content[first_content_type]
                
                schema_ref = json_content.get('schema', {})
                # Resolve $ref references
                resolved_schema = self._resolve_schema_refs(schema, schema_ref)
                endpoint_info['request_schema'] = resolved_schema
                
                # Extract examples from request body
                examples = json_content.get('examples', {})
                example = json_content.get('example')
                endpoint_info['request_examples'] = []
                
                if example:
                    endpoint_info['request_examples'].append({
                        'name': 'default',
                        'value': example
                    })
                
                if examples:
                    for name, ex in examples.items():
                        if isinstance(ex, dict) and 'value' in ex:
                            endpoint_info['request_examples'].append({
                                'name': name,
                                'value': ex['value'],
                                'summary': ex.get('summary', '')
                            })
                        else:
                            endpoint_info['request_examples'].append({
                                'name': name,
                                'value': ex
                            })
            else:
                endpoint_info['request_schema'] = {}
                endpoint_info['request_examples'] = []
        else:
            endpoint_info['request_schema'] = {}
            endpoint_info['request_examples'] = []
        
        # Extract and resolve response schemas with examples
        response_schemas = {}
        response_examples = {}
        for status_code, response in endpoint_info['responses'].items():
            content = response.get('content', {})
            if content:
                # Prefer application/json
                json_content = content.get('application/json', {})
                if not json_content:
                    # Get first content type
                    first_content_type = list(content.keys())[0]
                    json_content = content[first_content_type]
                
                schema_ref = json_content.get('schema', {})
                # Resolve $ref references
                resolved_schema = self._resolve_schema_refs(schema, schema_ref)
                response_schemas[status_code] = resolved_schema
                
                # Extract examples from response
                examples = json_content.get('examples', {})
                example = json_content.get('example')
                response_examples[status_code] = []
                
                if example:
                    response_examples[status_code].append({
                        'name': 'default',
                        'value': example
                    })
                
                if examples:
                    for name, ex in examples.items():
                        if isinstance(ex, dict) and 'value' in ex:
                            response_examples[status_code].append({
                                'name': name,
                                'value': ex['value'],
                                'summary': ex.get('summary', '')
                            })
                        else:
                            response_examples[status_code].append({
                                'name': name,
                                'value': ex
                            })
            else:
                response_schemas[status_code] = {}
                response_examples[status_code] = []
        
        endpoint_info['response_schemas'] = response_schemas
        endpoint_info['response_examples'] = response_examples
        
        # Enhance parameters with resolved schemas and better context
        enhanced_parameters = []
        for param in endpoint_info['parameters']:
            param_schema = param.get('schema', {})
            # Resolve $ref in parameter schema
            if param_schema:
                resolved_param_schema = self._resolve_schema_refs(schema, param_schema)
                enhanced_param = param.copy()
                enhanced_param['resolved_schema'] = resolved_param_schema
                # Extract example from parameter schema
                if 'example' in resolved_param_schema:
                    enhanced_param['example'] = resolved_param_schema['example']
                enhanced_parameters.append(enhanced_param)
            else:
                enhanced_parameters.append(param)
        
        endpoint_info['parameters'] = enhanced_parameters
        
        return endpoint_info
    
    def _resolve_schema_refs(self, schema: Dict[str, Any], schema_obj: Any) -> Dict[str, Any]:
        """
        Resolve $ref references in schema
        
        Args:
            schema: Full OpenAPI schema dictionary
            schema_obj: Schema object that may contain $ref
            
        Returns:
            Resolved schema dictionary
        """
        if not isinstance(schema_obj, dict):
            return schema_obj
        
        # Check for $ref
        if '$ref' in schema_obj:
            ref_path = schema_obj['$ref']
            # Handle different ref formats
            if ref_path.startswith('#/components/schemas/'):
                schema_name = ref_path.replace('#/components/schemas/', '')
                components = schema.get('components', {})
                schemas = components.get('schemas', {})
                if schema_name in schemas:
                    # Recursively resolve the referenced schema
                    return self._resolve_schema_refs(schema, schemas[schema_name])
            elif ref_path.startswith('#/components/parameters/'):
                param_name = ref_path.replace('#/components/parameters/', '')
                components = schema.get('components', {})
                parameters = components.get('parameters', {})
                if param_name in parameters:
                    return self._resolve_schema_refs(schema, parameters[param_name])
            elif ref_path.startswith('#/components/responses/'):
                response_name = ref_path.replace('#/components/responses/', '')
                components = schema.get('components', {})
                responses = components.get('responses', {})
                if response_name in responses:
                    return self._resolve_schema_refs(schema, responses[response_name])
            # If ref not found, return original
            return schema_obj
        
        # Recursively resolve nested references
        resolved = {}
        for key, value in schema_obj.items():
            if isinstance(value, dict):
                resolved[key] = self._resolve_schema_refs(schema, value)
            elif isinstance(value, list):
                resolved[key] = [
                    self._resolve_schema_refs(schema, item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                resolved[key] = value
        
        return resolved
    
    def _get_historical_context(self, schema_file: str, method: str, 
                                path: str) -> Dict[str, Any]:
        """
        Get historical test results for context
        
        Args:
            schema_file: Schema file identifier
            method: HTTP method
            path: Endpoint path
            
        Returns:
            Dictionary with historical context
        """
        try:
            history = self.storage.results.get_test_history(
                schema_file=schema_file,
                method=method,
                path=path,
                limit=10  # Last 10 test runs
            )
            
            if not history:
                return {
                    'count': 0,
                    'recent_results': [],
                    'success_rate': None,
                    'common_status_codes': []
                }
            
            # Calculate success rate
            total = len(history)
            successful = sum(1 for h in history if h.get('status') == 'success')
            success_rate = (successful / total) if total > 0 else 0.0
            
            # Get common status codes
            status_codes = [h.get('status_code') for h in history if h.get('status_code')]
            common_status_codes = {}
            for code in status_codes:
                common_status_codes[code] = common_status_codes.get(code, 0) + 1
            
            # Get recent results (simplified)
            recent_results = []
            for h in history[:5]:  # Last 5 results
                recent_results.append({
                    'status': h.get('status'),
                    'status_code': h.get('status_code'),
                    'timestamp': h.get('timestamp'),
                    'response_time_ms': h.get('response_time_ms')
                })
            
            return {
                'count': total,
                'recent_results': recent_results,
                'success_rate': success_rate,
                'common_status_codes': common_status_codes
            }
        except Exception as e:
            logger.warning(f"Error getting historical context: {e}")
            return {
                'count': 0,
                'recent_results': [],
                'success_rate': None,
                'common_status_codes': []
            }
    
    def _get_validated_test_examples(self, schema_file: str, method: str, 
                                     path: str) -> List[Dict[str, Any]]:
        """
        Get validated AI test cases as examples
        
        Args:
            schema_file: Schema file identifier
            method: HTTP method
            path: Endpoint path
            
        Returns:
            List of validated test case dictionaries
        """
        try:
            validated_tests = self.storage.ai_tests.get_validated_test_cases(
                schema_file=schema_file,
                limit=20  # Get more, then filter
            )
            
            # Filter by method and path
            filtered_tests = [
                test for test in validated_tests
                if test.get('method', '').upper() == method.upper() and test.get('path') == path
            ]
            
            # Simplify test cases for context
            examples = []
            for test in filtered_tests[:5]:  # Top 5 matching examples
                test_case = test.get('test_case_json', {})
                examples.append({
                    'test_scenario': test_case.get('test_scenario', ''),
                    'request_body': test_case.get('request_body'),
                    'expected_response': test_case.get('expected_response'),
                    'validation_status': test.get('validation_status'),
                    'created_at': test.get('created_at')
                })
            
            return examples
        except Exception as e:
            logger.warning(f"Error getting validated test examples: {e}")
            return []
    
    def _get_relevant_patterns(self, schema_file: str, method: Optional[str] = None, 
                               path: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get relevant learned patterns
        
        Args:
            schema_file: Schema file identifier
            method: HTTP method (optional, for future filtering)
            path: Endpoint path (optional, for future filtering)
            
        Returns:
            List of pattern dictionaries
        """
        try:
            # Get patterns with minimum effectiveness threshold
            patterns = self.storage.patterns.get_patterns(
                min_effectiveness=0.5  # Only get effective patterns
            )
            
            # Sort by effectiveness (already sorted by DB, but ensure)
            patterns.sort(
                key=lambda x: x.get('effectiveness_score', 0), 
                reverse=True
            )
            
            # Simplify patterns for context
            simplified = []
            for pattern in patterns[:5]:  # Top 5 patterns
                simplified.append({
                    'pattern_type': pattern.get('pattern_type', ''),
                    'pattern_data': pattern.get('pattern_data', {}),
                    'effectiveness': pattern.get('effectiveness_score', 0)
                })
            
            return simplified
        except Exception as e:
            logger.warning(f"Error getting relevant patterns: {e}")
            return []
    
    def clear_cache(self):
        """Clear the context cache"""
        self._cache.clear()
        self._shared_context_cache.clear()
        logger.debug("Context cache cleared")

