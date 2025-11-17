"""
AI test generator

Generates test cases using AI by integrating context building, prompt generation,
AI API calls, and response parsing.
"""

import logging
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime

from apitest.ai.context_builder import ContextBuilder
from apitest.ai.prompt_builder import PromptBuilder, SchemaFormat, PromptFormat
from apitest.ai.groq_client import GroqClient, GroqAPIError, GroqRateLimitError, GroqAuthenticationError
from apitest.ai.response_parser import ResponseParser
from apitest.core.test_generator import TestCase

logger = logging.getLogger(__name__)


class AITestGenerator:
    """
    Generate test cases using AI
    
    Integrates context building, prompt generation, AI API calls, and response parsing
    to generate comprehensive test cases for API endpoints.
    """
    
    def __init__(self, ai_config, storage: Optional[Any] = None):
        """
        Initialize AI test generator
        
        Args:
            ai_config: AIConfig instance with provider, model, api_key, etc.
            storage: Optional Storage instance for accessing history/patterns
        """
        self.ai_config = ai_config
        self.storage = storage
        
        # Initialize components (always create, even without storage)
        self.context_builder = ContextBuilder(storage)
        
        # Get format options from config
        if ai_config.schema_format == 'yaml':
            schema_format = SchemaFormat.YAML
        elif ai_config.schema_format == 'toon':
            schema_format = SchemaFormat.TOON
        else:
            schema_format = SchemaFormat.JSON
        
        prompt_format = PromptFormat.XML if ai_config.prompt_format == 'xml' else PromptFormat.MARKDOWN
        
        self.prompt_builder = PromptBuilder(
            storage=storage,
            schema_format=schema_format,
            prompt_format=prompt_format
        )
        self.response_parser = ResponseParser()
        
        # Initialize AI client based on provider
        self.ai_client = self._create_ai_client()
    
    def _create_ai_client(self):
        """
        Create AI client based on provider configuration
        
        Returns:
            AI client instance (GroqClient, etc.)
        """
        provider = self.ai_config.provider.lower()
        
        if provider == 'groq':
            if not self.ai_config.api_key:
                raise ValueError("Groq API key is required. Set GROQ_API_KEY environment variable or provide in config.")
            
            return GroqClient(
                api_key=self.ai_config.api_key,
                model=self.ai_config.model,
                temperature=self.ai_config.temperature,
                max_tokens=self.ai_config.max_tokens
            )
        elif provider == 'openai':
            # TODO: Implement OpenAI client in future
            raise NotImplementedError("OpenAI provider not yet implemented")
        elif provider == 'anthropic':
            # TODO: Implement Anthropic client in future
            raise NotImplementedError("Anthropic provider not yet implemented")
        else:
            raise ValueError(f"Unsupported AI provider: {provider}")
    
    def generate_tests(self, schema: Dict[str, Any], schema_file: str, 
                      endpoints: List[Tuple[str, str, Dict[str, Any]]], 
                      batch_size: int = 8) -> List[TestCase]:
        """
        Generate test cases for endpoints using AI with batch processing
        
        Args:
            schema: OpenAPI schema dictionary
            schema_file: Path/identifier for schema file
            endpoints: List of (method, path, operation) tuples
            batch_size: Number of endpoints to process per API call (default: 8)
            
        Returns:
            List of TestCase objects with is_ai_generated=True
        """
        test_cases = []
        
        # Build shared context once for all endpoints
        shared_context = self.context_builder.build_shared_context(schema_file)
        
        # Process endpoints in batches
        for batch_start in range(0, len(endpoints), batch_size):
            batch_end = min(batch_start + batch_size, len(endpoints))
            batch_endpoints = endpoints[batch_start:batch_end]
            
            try:
                # Generate tests for this batch
                batch_test_cases = self._generate_batch_tests(
                    schema=schema,
                    schema_file=schema_file,
                    endpoints=batch_endpoints,
                    shared_context=shared_context
                )
                test_cases.extend(batch_test_cases)
                
                logger.info(f"Generated {len(batch_test_cases)} test cases for batch {batch_start//batch_size + 1} ({len(batch_endpoints)} endpoints)")
                
            except (GroqAPIError, GroqRateLimitError, GroqAuthenticationError) as e:
                logger.error(f"AI API error generating tests for batch {batch_start//batch_size + 1}: {e}")
                # Fall back to individual generation for this batch
                logger.info(f"Falling back to individual generation for batch {batch_start//batch_size + 1}")
                for method, path, operation in batch_endpoints:
                    try:
                        individual_cases = self._generate_single_endpoint_tests(
                            schema=schema,
                            schema_file=schema_file,
                            method=method,
                            path=path,
                            operation=operation
                        )
                        test_cases.extend(individual_cases)
                    except Exception as e2:
                        logger.error(f"Error generating tests for {method} {path}: {e2}")
                        continue
            except Exception as e:
                logger.error(f"Unexpected error generating batch tests: {e}", exc_info=True)
                # Fall back to individual generation
                for method, path, operation in batch_endpoints:
                    try:
                        individual_cases = self._generate_single_endpoint_tests(
                            schema=schema,
                            schema_file=schema_file,
                            method=method,
                            path=path,
                            operation=operation
                        )
                        test_cases.extend(individual_cases)
                    except Exception as e2:
                        logger.error(f"Error generating tests for {method} {path}: {e2}")
                        continue
        
        return test_cases
    
    def _generate_batch_tests(self, schema: Dict[str, Any], schema_file: str,
                              endpoints: List[Tuple[str, str, Dict[str, Any]]],
                              shared_context: Dict[str, Any]) -> List[TestCase]:
        """
        Generate test cases for a batch of endpoints in a single API call
        
        Args:
            schema: OpenAPI schema dictionary
            schema_file: Path/identifier for schema file
            endpoints: List of (method, path, operation) tuples for this batch
            shared_context: Shared context dictionary
            
        Returns:
            List of TestCase objects
        """
        # Build endpoint info for all endpoints in batch
        endpoints_info = []
        endpoint_mapping = {}  # Maps "METHOD /path" to (method, path)
        
        for method, path, operation in endpoints:
            # Build endpoint-specific context
            context = self.context_builder.build_context(
                schema=schema,
                schema_file=schema_file,
                method=method,
                path=path
            )
            
            endpoint_info = context.get('endpoint', {})
            
            # If endpoint_info is empty, build it from operation
            if not endpoint_info:
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
                    'request_schema': {},
                    'response_schemas': {}
                }
            
            endpoints_info.append(endpoint_info)
            
            # Create mapping for batch response parsing
            endpoint_key = f"{method.upper()} {path}"
            endpoint_mapping[endpoint_key] = (method, path)
        
        # Build batch prompt
        prompt = self.prompt_builder.build_batch_prompt(
            shared_context=shared_context,
            endpoints_info=endpoints_info
        )
        
        # Call AI API once for the batch
        logger.debug(f"Generating AI tests for batch of {len(endpoints)} endpoints")
        ai_response = self.ai_client.generate(prompt)
        
        # Parse batch response
        parsed_test_cases = self.response_parser.parse_test_cases(
            ai_response, 
            endpoint_mapping=endpoint_mapping
        )
        
        # Log if parsing failed
        if not parsed_test_cases and ai_response:
            logger.warning(f"Failed to parse batch AI response. Response length: {len(ai_response)} chars")
            preview = ai_response[:300] if len(ai_response) > 300 else ai_response
            logger.debug(f"AI response preview: {preview}")
        
        # Convert to TestCase objects
        test_cases = []
        for parsed_case in parsed_test_cases:
            # Extract method and path from parsed case (set by parser for batch responses)
            method = parsed_case.get('method')
            path = parsed_case.get('path')
            
            # If not in parsed case, try to extract from endpoint field
            if not method or not path:
                endpoint_key = parsed_case.get('endpoint', '')
                if endpoint_key in endpoint_mapping:
                    method, path = endpoint_mapping[endpoint_key]
            
            # Fallback: use first endpoint in batch (shouldn't happen)
            if not method or not path:
                method, path, _ = endpoints[0]
            
            test_case = self._create_test_case(
                parsed_case=parsed_case,
                method=method,
                path=path,
                schema_file=schema_file
            )
            test_cases.append(test_case)
        
        return test_cases
    
    def _generate_single_endpoint_tests(self, schema: Dict[str, Any], schema_file: str,
                                        method: str, path: str, operation: Dict[str, Any]) -> List[TestCase]:
        """
        Generate test cases for a single endpoint (fallback method)
        
        Args:
            schema: OpenAPI schema dictionary
            schema_file: Path/identifier for schema file
            method: HTTP method
            path: Endpoint path
            operation: Operation dictionary
            
        Returns:
            List of TestCase objects
        """
        # Build context for this endpoint
        context = self.context_builder.build_context(
            schema=schema,
            schema_file=schema_file,
            method=method,
            path=path
        )
        
        # Extract endpoint info from context
        endpoint_info = context.get('endpoint', {})
        
        # If endpoint_info is empty, build it from operation
        if not endpoint_info:
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
                'request_schema': {},
                'response_schemas': {}
            }
        
        # Determine template based on endpoint characteristics
        template_name = self._select_template(operation, context)
        
        # Build prompt
        prompt = self.prompt_builder.build_prompt(
            context=context,
            endpoint_info=endpoint_info,
            template_name=template_name
        )
        
        # Call AI API
        logger.debug(f"Generating AI tests for {method} {path}")
        ai_response = self.ai_client.generate(prompt)
        
        # Parse response
        parsed_test_cases = self.response_parser.parse_test_cases(ai_response)
        
        # Log if parsing failed
        if not parsed_test_cases and ai_response:
            logger.warning(f"Failed to parse AI response for {method} {path}. Response length: {len(ai_response)} chars")
            preview = ai_response[:300] if len(ai_response) > 300 else ai_response
            logger.debug(f"AI response preview: {preview}")
        
        # Convert to TestCase objects
        test_cases = []
        for parsed_case in parsed_test_cases:
            test_case = self._create_test_case(
                parsed_case=parsed_case,
                method=method,
                path=path,
                schema_file=schema_file
            )
            test_cases.append(test_case)
        
        logger.info(f"Generated {len(parsed_test_cases)} AI test cases for {method} {path}")
        
        return test_cases
    
    def _select_template(self, operation: Dict[str, Any], context: Dict[str, Any]) -> str:
        """
        Select appropriate prompt template based on endpoint characteristics
        
        Args:
            operation: OpenAPI operation dictionary
            context: Context dictionary from ContextBuilder
            
        Returns:
            Template name to use
        """
        # Default to basic template
        template = PromptBuilder.TEMPLATE_BASIC
        
        # Check if we have historical data suggesting edge cases are needed
        history = context.get('history', {})
        success_rate = history.get('success_rate')
        
        # If low success rate, might want edge cases
        if success_rate is not None and success_rate < 0.7:
            template = PromptBuilder.TEMPLATE_EDGE_CASES
        # If we have validated examples, use advanced template
        elif context.get('validated_examples'):
            template = PromptBuilder.TEMPLATE_ADVANCED
        # If we have patterns, use advanced template
        elif context.get('patterns'):
            template = PromptBuilder.TEMPLATE_ADVANCED
        
        return template
    
    def _create_test_case(self, parsed_case: Dict[str, Any], method: str, 
                         path: str, schema_file: str) -> TestCase:
        """
        Create TestCase object from parsed AI response
        
        Args:
            parsed_case: Parsed test case dictionary
            method: HTTP method
            path: Endpoint path
            schema_file: Schema file identifier
            
        Returns:
            TestCase object
        """
        # Extract expected response status code
        expected_response = parsed_case.get('expected_response', {})
        status_code = expected_response.get('status_code', 200)
        
        # Create AI metadata
        ai_metadata = {
            'model': self.ai_config.model,
            'provider': self.ai_config.provider,
            'prompt_version': 'default',  # TODO: Get from prompt builder
            'generation_timestamp': datetime.utcnow().isoformat(),
            'temperature': self.ai_config.temperature,
            'max_tokens': self.ai_config.max_tokens,
            'tokens_used': getattr(self.ai_client, 'tokens_used', None),
            'tokens_limit': getattr(self.ai_client, 'tokens_limit', None)
        }
        
        # Create TestCase
        test_case = TestCase(
            method=method,
            path=path,
            request_body=parsed_case.get('request_body'),
            expected_response=expected_response,
            test_scenario=parsed_case.get('test_scenario', f'AI-generated test for {method} {path}'),
            is_ai_generated=True,
            ai_metadata=ai_metadata
        )
        
        return test_case

