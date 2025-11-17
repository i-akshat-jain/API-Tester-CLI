"""
Prompt builder for AI test generation

Builds prompts for AI models by loading templates from storage or using defaults,
and injecting context information.
"""

import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


# Default prompt templates
DEFAULT_BASIC_PROMPT = """You are an expert API testing assistant. Generate comprehensive test cases for the following API endpoint.

## Endpoint Information
- Method: {method}
- Path: {path}
- Summary: {summary}
- Description: {description}

## Request Schema
{request_schema}

## Response Schemas
{response_schemas}

## Context
- Historical test count: {history_count}
- Success rate: {success_rate}
- Common status codes: {common_status_codes}

## Instructions
Generate 2-3 test cases for this endpoint. Each test case should include:
1. A clear test scenario description
2. A request body (if applicable) with realistic test data
3. Expected response status code and key fields

Return your response as a JSON object with this structure:
{{
  "test_cases": [
    {{
      "test_scenario": "Description of what this test validates",
      "request_body": {{...}},
      "expected_response": {{
        "status_code": 200,
        "body": {{...}}
      }}
    }}
  ]
}}
"""

DEFAULT_ADVANCED_PROMPT = """You are an expert API testing assistant. Generate advanced test cases for the following API endpoint, including edge cases and error scenarios.

## Endpoint Information
- Method: {method}
- Path: {path}
- Summary: {summary}
- Description: {description}
- Operation ID: {operation_id}
- Tags: {tags}

## Request Schema
{request_schema}

## Request Parameters
{parameters}

## Response Schemas
{response_schemas}

## Historical Context
- Total test runs: {history_count}
- Success rate: {success_rate}
- Common status codes: {common_status_codes}
- Recent results: {recent_results}

## Validated Examples
{validated_examples}

## Learned Patterns
{patterns}

## Instructions
Generate 3-5 comprehensive test cases including:
1. Happy path scenarios (normal successful operations)
2. Edge cases (boundary values, optional fields, empty values)
3. Error scenarios (invalid data, missing required fields, type mismatches)
4. Security scenarios (if applicable)

For each test case, provide:
- A clear test scenario description
- Request body/parameters with appropriate test data
- Expected response status code and structure
- Rationale for why this test case is important

Return your response as a JSON object with this structure:
{{
  "test_cases": [
    {{
      "test_scenario": "Description of what this test validates",
      "request_body": {{...}},
      "expected_response": {{
        "status_code": 200,
        "body": {{...}}
      }},
      "rationale": "Why this test case is important"
    }}
  ]
}}
"""

DEFAULT_EDGE_CASES_PROMPT = """You are an expert API testing assistant specializing in edge cases and error scenarios. Generate test cases that explore boundary conditions, error handling, and unusual inputs.

## Endpoint Information
- Method: {method}
- Path: {path}
- Summary: {summary}
- Description: {description}

## Request Schema
{request_schema}

## Request Parameters
{parameters}

## Response Schemas
{response_schemas}

## Historical Context
- Success rate: {success_rate}
- Common status codes: {common_status_codes}

## Instructions
Focus on generating edge case and error scenario test cases:
1. Boundary values (min, max, just above/below limits)
2. Invalid data types (string where number expected, etc.)
3. Missing required fields
4. Empty/null values
5. Extremely long strings
6. Special characters and encoding issues
7. Negative numbers where not expected
8. Zero values
9. Duplicate values (if applicable)
10. Invalid enum values

For each test case, provide:
- Test scenario description explaining the edge case
- Request body/parameters with the edge case data
- Expected response (error status code and error message structure)
- Why this edge case matters

Return your response as a JSON object with this structure:
{{
  "test_cases": [
    {{
      "test_scenario": "Description of the edge case",
      "request_body": {{...}},
      "expected_response": {{
        "status_code": 400,
        "body": {{
          "error": "...",
          "message": "..."
        }}
      }},
      "rationale": "Why this edge case is important to test"
    }}
  ]
}}
"""


class PromptBuilder:
    """
    Build prompts for AI test generation
    
    Loads prompt templates from storage or uses defaults,
    and injects context information.
    """
    
    # Template name constants
    TEMPLATE_BASIC = 'test_generation_basic'
    TEMPLATE_ADVANCED = 'test_generation_advanced'
    TEMPLATE_EDGE_CASES = 'test_generation_edge_cases'
    
    def __init__(self, storage: Optional[Any] = None):
        """
        Initialize prompt builder
        
        Args:
            storage: Optional Storage instance for loading templates
        """
        self.storage = storage
        self._default_templates = {
            self.TEMPLATE_BASIC: DEFAULT_BASIC_PROMPT,
            self.TEMPLATE_ADVANCED: DEFAULT_ADVANCED_PROMPT,
            self.TEMPLATE_EDGE_CASES: DEFAULT_EDGE_CASES_PROMPT
        }
    
    def build_prompt(self, context: Dict[str, Any], endpoint_info: Dict[str, Any],
                    template_name: str = TEMPLATE_BASIC) -> str:
        """
        Build a prompt by loading template and injecting context
        
        Args:
            context: Context dictionary from ContextBuilder
            endpoint_info: Endpoint information dictionary
            template_name: Name of template to use (default: 'test_generation_basic')
            
        Returns:
            Formatted prompt string ready for AI model
        """
        # Load template
        template = self._load_template(template_name)
        
        # Prepare template variables
        template_vars = self._prepare_template_variables(context, endpoint_info)
        
        # Render template
        return self._render_template(template, template_vars)
    
    def _load_template(self, template_name: str) -> str:
        """
        Load prompt template from storage or use default
        
        Args:
            template_name: Name of template to load
            
        Returns:
            Template string
        """
        # Try to load from storage first
        if self.storage:
            try:
                prompt_data = self.storage.ai_prompts.get_active_prompt(template_name)
                if prompt_data:
                    logger.debug(f"Loaded template '{template_name}' from storage")
                    return prompt_data.get('prompt_template', '')
                
                # Try latest version if no active prompt
                prompt_data = self.storage.ai_prompts.get_latest_prompt(template_name)
                if prompt_data:
                    logger.debug(f"Loaded latest version of template '{template_name}' from storage")
                    return prompt_data.get('prompt_template', '')
            except Exception as e:
                logger.warning(f"Error loading template from storage: {e}. Using default.")
        
        # Fall back to default template
        if template_name in self._default_templates:
            logger.debug(f"Using default template '{template_name}'")
            return self._default_templates[template_name]
        
        # If template not found, use basic as fallback
        logger.warning(f"Template '{template_name}' not found, using basic template")
        return self._default_templates[self.TEMPLATE_BASIC]
    
    def _prepare_template_variables(self, context: Dict[str, Any], 
                                   endpoint_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare template variables from context and endpoint info
        
        Args:
            context: Context dictionary
            endpoint_info: Endpoint information dictionary
            
        Returns:
            Dictionary of template variables
        """
        # Extract endpoint info
        method = endpoint_info.get('method', 'GET')
        path = endpoint_info.get('path', '')
        summary = endpoint_info.get('summary', '')
        description = endpoint_info.get('description', '')
        operation_id = endpoint_info.get('operation_id', '')
        tags = ', '.join(endpoint_info.get('tags', []))
        
        # Format request schema
        request_schema = endpoint_info.get('request_schema', {})
        request_schema_str = self._format_schema(request_schema)
        
        # Format response schemas
        response_schemas = endpoint_info.get('response_schemas', {})
        response_schemas_str = self._format_response_schemas(response_schemas)
        
        # Format parameters
        parameters = endpoint_info.get('parameters', [])
        parameters_str = self._format_parameters(parameters)
        
        # Extract history info
        history = context.get('history', {})
        history_count = history.get('count', 0)
        success_rate = history.get('success_rate')
        success_rate_str = f"{success_rate:.1%}" if success_rate is not None else "N/A"
        common_status_codes = history.get('common_status_codes', {})
        common_status_codes_str = ', '.join(
            f"{code}({count})" for code, count in sorted(common_status_codes.items(), 
                                                         key=lambda x: x[1], reverse=True)[:5]
        ) or "N/A"
        recent_results = history.get('recent_results', [])
        recent_results_str = self._format_recent_results(recent_results)
        
        # Extract validated examples
        validated_examples = context.get('validated_examples', [])
        validated_examples_str = self._format_validated_examples(validated_examples)
        
        # Extract patterns
        patterns = context.get('patterns', [])
        patterns_str = self._format_patterns(patterns)
        
        return {
            'method': method,
            'path': path,
            'summary': summary or 'N/A',
            'description': description or 'N/A',
            'operation_id': operation_id or 'N/A',
            'tags': tags or 'N/A',
            'request_schema': request_schema_str,
            'response_schemas': response_schemas_str,
            'parameters': parameters_str,
            'history_count': history_count,
            'success_rate': success_rate_str,
            'common_status_codes': common_status_codes_str,
            'recent_results': recent_results_str,
            'validated_examples': validated_examples_str,
            'patterns': patterns_str
        }
    
    def _format_schema(self, schema: Dict[str, Any]) -> str:
        """Format schema dictionary as readable string"""
        if not schema:
            return "No request body schema defined"
        
        try:
            import json
            return json.dumps(schema, indent=2)
        except Exception:
            return str(schema)
    
    def _format_response_schemas(self, response_schemas: Dict[str, Any]) -> str:
        """Format response schemas as readable string"""
        if not response_schemas:
            return "No response schemas defined"
        
        lines = []
        for status_code, schema in response_schemas.items():
            lines.append(f"Status {status_code}:")
            try:
                import json
                lines.append(json.dumps(schema, indent=2))
            except Exception:
                lines.append(str(schema))
            lines.append("")
        
        return "\n".join(lines).strip()
    
    def _format_parameters(self, parameters: List[Dict[str, Any]]) -> str:
        """Format parameters list as readable string"""
        if not parameters:
            return "No parameters defined"
        
        lines = []
        for param in parameters:
            param_name = param.get('name', 'unknown')
            param_in = param.get('in', 'unknown')
            param_type = param.get('schema', {}).get('type', 'unknown')
            required = param.get('required', False)
            required_str = "required" if required else "optional"
            lines.append(f"- {param_name} ({param_in}, {param_type}, {required_str})")
        
        return "\n".join(lines)
    
    def _format_recent_results(self, recent_results: List[Dict[str, Any]]) -> str:
        """Format recent test results as readable string"""
        if not recent_results:
            return "No recent test results"
        
        lines = []
        for result in recent_results[:5]:
            status = result.get('status', 'unknown')
            status_code = result.get('status_code', 'N/A')
            response_time = result.get('response_time_ms', 'N/A')
            lines.append(f"- {status} (status: {status_code}, time: {response_time}ms)")
        
        return "\n".join(lines)
    
    def _format_validated_examples(self, examples: List[Dict[str, Any]]) -> str:
        """Format validated test examples as readable string"""
        if not examples:
            return "No validated examples available"
        
        lines = []
        for i, example in enumerate(examples[:3], 1):  # Show top 3 examples
            scenario = example.get('test_scenario', 'N/A')
            status = example.get('validation_status', 'N/A')
            lines.append(f"Example {i}: {scenario} (status: {status})")
            request_body = example.get('request_body')
            if request_body:
                try:
                    import json
                    lines.append(f"  Request: {json.dumps(request_body, indent=2)}")
                except Exception:
                    lines.append(f"  Request: {str(request_body)}")
        
        return "\n".join(lines)
    
    def _format_patterns(self, patterns: List[Dict[str, Any]]) -> str:
        """Format learned patterns as readable string"""
        if not patterns:
            return "No learned patterns available"
        
        lines = []
        for pattern in patterns[:3]:  # Show top 3 patterns
            pattern_type = pattern.get('pattern_type', 'unknown')
            effectiveness = pattern.get('effectiveness', 0)
            pattern_data = pattern.get('pattern_data', {})
            lines.append(f"- {pattern_type} (effectiveness: {effectiveness:.2f})")
            if pattern_data:
                try:
                    import json
                    lines.append(f"  Data: {json.dumps(pattern_data, indent=2)}")
                except Exception:
                    lines.append(f"  Data: {str(pattern_data)}")
        
        return "\n".join(lines)
    
    def _render_template(self, template: str, variables: Dict[str, Any]) -> str:
        """
        Render template with variables using string formatting
        
        Args:
            template: Template string with {variable} placeholders
            variables: Dictionary of variables to inject
            
        Returns:
            Rendered prompt string
        """
        try:
            return template.format(**variables)
        except KeyError as e:
            logger.warning(f"Missing template variable: {e}. Using 'N/A' as default.")
            # Extract all variable names from template
            import re
            required_vars = set(re.findall(r'\{(\w+)\}', template))
            
            # Fill missing variables with 'N/A'
            safe_variables = {}
            for var_name in required_vars:
                safe_variables[var_name] = variables.get(var_name, 'N/A')
            
            # Try again with safe variables
            return template.format(**safe_variables)
        except Exception as e:
            logger.error(f"Error rendering template: {e}")
            raise


def initialize_default_prompts(storage: Any) -> None:
    """
    Initialize default prompt templates in storage
    
    This should be called on first run to populate storage with default templates.
    
    Args:
        storage: Storage instance with ai_prompts namespace
    """
    if not storage:
        logger.warning("No storage provided, cannot initialize default prompts")
        return
    
    builder = PromptBuilder(storage)
    
    templates = {
        PromptBuilder.TEMPLATE_BASIC: DEFAULT_BASIC_PROMPT,
        PromptBuilder.TEMPLATE_ADVANCED: DEFAULT_ADVANCED_PROMPT,
        PromptBuilder.TEMPLATE_EDGE_CASES: DEFAULT_EDGE_CASES_PROMPT
    }
    
    for template_name, template_content in templates.items():
        try:
            # Check if template already exists
            existing = storage.ai_prompts.get_latest_prompt(template_name)
            if existing:
                logger.debug(f"Template '{template_name}' already exists, skipping initialization")
                continue
            
            # Save default template as version 1
            prompt_id = storage.ai_prompts.save_prompt(
                prompt_name=template_name,
                prompt_template=template_content,
                metadata={
                    'description': f'Default {template_name} template',
                    'is_default': True
                },
                version=1
            )
            
            # Set as active
            storage.ai_prompts.set_active_prompt(template_name, 1)
            logger.info(f"Initialized default template '{template_name}' (ID: {prompt_id})")
        except Exception as e:
            logger.error(f"Error initializing template '{template_name}': {e}")

