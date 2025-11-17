"""
Prompt builder for AI test generation

Builds prompts for AI models by loading templates from storage or using defaults,
and injecting context information.

Supports multiple formats:
- Schema format: JSON (default) or YAML (more readable)
- Prompt format: Markdown (default) or XML (better LLM alignment)
"""

import logging
from typing import Dict, Any, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)


class SchemaFormat(Enum):
    """Schema formatting options"""
    JSON = "json"
    YAML = "yaml"
    TOON = "toon"  # Compact tabular format for arrays/objects


class PromptFormat(Enum):
    """Prompt formatting options"""
    MARKDOWN = "markdown"
    XML = "xml"


# Default prompt templates (Markdown format)
DEFAULT_BASIC_PROMPT = """You are an expert API testing assistant. Generate comprehensive test cases for the following API endpoint.

## Endpoint Information
- Method: {method}
- Path: {path}
- Summary: {summary}
- Description: {description}

## Request Schema
{request_schema}

## Request Examples
{request_examples}

## Response Schemas
{response_schemas}

## Response Examples
{response_examples}

## Context
- Historical test count: {history_count}
- Success rate: {success_rate}
- Common status codes: {common_status_codes}

## Instructions
Generate 2-3 test cases for this endpoint. Each test case should include:
1. A clear test scenario description
2. A request body (if applicable) with realistic test data - **USE THE PROVIDED EXAMPLES AS REFERENCE** when available
3. **ALL REQUIRED QUERY PARAMETERS** - Pay special attention to query parameters marked as required
4. Expected response status code and key fields - **USE THE PROVIDED RESPONSE EXAMPLES** when available

**IMPORTANT**: 
- If request examples are provided, use them as a starting point for generating test data
- Always include required query parameters in your test cases
- For endpoints with path parameters (e.g., {{id}}), use realistic values based on the schema
- Pay attention to parameter descriptions - they often indicate when parameters are required for certain operations

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

# XML-structured prompt templates (better LLM alignment)
DEFAULT_BASIC_PROMPT_XML = """<task>
You are an expert API testing assistant. Generate comprehensive test cases for the following API endpoint.
</task>

<endpoint>
<method>{method}</method>
<path>{path}</path>
<summary>{summary}</summary>
<description>{description}</description>
</endpoint>

<request_schema>
{request_schema}
</request_schema>

<request_examples>
{request_examples}
</request_examples>

<response_schemas>
{response_schemas}
</response_schemas>

<response_examples>
{response_examples}
</response_examples>

<context>
<historical_test_count>{history_count}</historical_test_count>
<success_rate>{success_rate}</success_rate>
<common_status_codes>{common_status_codes}</common_status_codes>
</context>

<instructions>
Generate 2-3 test cases for this endpoint. Each test case should include:
1. A clear test scenario description
2. A request body (if applicable) with realistic test data - USE THE PROVIDED EXAMPLES AS REFERENCE when available
3. ALL REQUIRED QUERY PARAMETERS - Pay special attention to query parameters marked as required
4. Expected response status code and key fields - USE THE PROVIDED RESPONSE EXAMPLES when available

IMPORTANT: 
- If request examples are provided, use them as a starting point for generating test data
- Always include required query parameters in your test cases
- For endpoints with path parameters (e.g., {{id}}), use realistic values based on the schema
- Pay attention to parameter descriptions - they often indicate when parameters are required for certain operations
</instructions>

<output_format>
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
</output_format>
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

## Request Examples
{request_examples}

## Request Parameters
{parameters}

## Response Schemas
{response_schemas}

## Response Examples
{response_examples}

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
1. Happy path scenarios (normal successful operations) - **USE PROVIDED EXAMPLES** when available
2. Edge cases (boundary values, optional fields, empty values)
3. Error scenarios (invalid data, missing required fields, type mismatches)
4. Security scenarios (if applicable)

For each test case, provide:
- A clear test scenario description
- Request body/parameters with appropriate test data - **PREFER USING PROVIDED EXAMPLES** as templates
- **ALL REQUIRED QUERY PARAMETERS** - Check parameter descriptions carefully, some operations require specific query parameters even if not marked as required in the schema
- Expected response status code and structure - **USE PROVIDED RESPONSE EXAMPLES** when available
- Rationale for why this test case is important

**IMPORTANT**: 
- Request examples show the expected format and structure - use them as templates
- Response examples show what successful responses look like - use them to set expectations
- Query parameters may be required for certain operations even if not explicitly marked - check descriptions
- Path parameters need realistic values (UUIDs, IDs, etc.) based on the schema type

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

DEFAULT_ADVANCED_PROMPT_XML = """<task>
You are an expert API testing assistant. Generate advanced test cases for the following API endpoint, including edge cases and error scenarios.
</task>

<endpoint>
<method>{method}</method>
<path>{path}</path>
<summary>{summary}</summary>
<description>{description}</description>
<operation_id>{operation_id}</operation_id>
<tags>{tags}</tags>
</endpoint>

<request_schema>
{request_schema}
</request_schema>

<request_examples>
{request_examples}
</request_examples>

<request_parameters>
{parameters}
</request_parameters>

<response_schemas>
{response_schemas}
</response_schemas>

<response_examples>
{response_examples}
</response_examples>

<historical_context>
<total_test_runs>{history_count}</total_test_runs>
<success_rate>{success_rate}</success_rate>
<common_status_codes>{common_status_codes}</common_status_codes>
<recent_results>
{recent_results}
</recent_results>
</historical_context>

<validated_examples>
{validated_examples}
</validated_examples>

<learned_patterns>
{patterns}
</learned_patterns>

<instructions>
Generate 3-5 comprehensive test cases including:
1. Happy path scenarios (normal successful operations) - USE PROVIDED EXAMPLES when available
2. Edge cases (boundary values, optional fields, empty values)
3. Error scenarios (invalid data, missing required fields, type mismatches)
4. Security scenarios (if applicable)

For each test case, provide:
- A clear test scenario description
- Request body/parameters with appropriate test data - PREFER USING PROVIDED EXAMPLES as templates
- ALL REQUIRED QUERY PARAMETERS - Check parameter descriptions carefully, some operations require specific query parameters even if not marked as required in the schema
- Expected response status code and structure - USE PROVIDED RESPONSE EXAMPLES when available
- Rationale for why this test case is important

IMPORTANT: 
- Request examples show the expected format and structure - use them as templates
- Response examples show what successful responses look like - use them to set expectations
- Query parameters may be required for certain operations even if not explicitly marked - check descriptions
- Path parameters need realistic values (UUIDs, IDs, etc.) based on the schema type
</instructions>

<output_format>
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
</output_format>
"""

DEFAULT_EDGE_CASES_PROMPT = """You are an expert API testing assistant specializing in edge cases and error scenarios. Generate test cases that explore boundary conditions, error handling, and unusual inputs.

## Endpoint Information
- Method: {method}
- Path: {path}
- Summary: {summary}
- Description: {description}

## Request Schema
{request_schema}

## Request Examples
{request_examples}

## Request Parameters
{parameters}

## Response Schemas
{response_schemas}

## Response Examples
{response_examples}

## Historical Context
- Success rate: {success_rate}
- Common status codes: {common_status_codes}

## Instructions
Focus on generating edge case and error scenario test cases:
1. Boundary values (min, max, just above/below limits)
2. Invalid data types (string where number expected, etc.)
3. Missing required fields - **INCLUDING MISSING REQUIRED QUERY PARAMETERS**
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
- **ALL REQUIRED QUERY PARAMETERS** - Even for error cases, include required parameters unless testing their absence
- Expected response (error status code and error message structure) - **USE PROVIDED RESPONSE EXAMPLES** when available
- Why this edge case matters

**IMPORTANT**:
- Query parameters may be required even if not marked as required - check descriptions
- Use provided examples as reference for normal cases, then modify for edge cases

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

DEFAULT_EDGE_CASES_PROMPT_XML = """<task>
You are an expert API testing assistant specializing in edge cases and error scenarios. Generate test cases that explore boundary conditions, error handling, and unusual inputs.
</task>

<endpoint>
<method>{method}</method>
<path>{path}</path>
<summary>{summary}</summary>
<description>{description}</description>
</endpoint>

<request_schema>
{request_schema}
</request_schema>

<request_examples>
{request_examples}
</request_examples>

<request_parameters>
{parameters}
</request_parameters>

<response_schemas>
{response_schemas}
</response_schemas>

<response_examples>
{response_examples}
</response_examples>

<historical_context>
<success_rate>{success_rate}</success_rate>
<common_status_codes>{common_status_codes}</common_status_codes>
</historical_context>

<instructions>
Focus on generating edge case and error scenario test cases:
1. Boundary values (min, max, just above/below limits)
2. Invalid data types (string where number expected, etc.)
3. Missing required fields - **INCLUDING MISSING REQUIRED QUERY PARAMETERS**
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
- **ALL REQUIRED QUERY PARAMETERS** - Even for error cases, include required parameters unless testing their absence
- Expected response (error status code and error message structure) - **USE PROVIDED RESPONSE EXAMPLES** when available
- Why this edge case matters

IMPORTANT:
- Query parameters may be required even if not marked as required - check descriptions
- Use provided examples as reference for normal cases, then modify for edge cases
</instructions>

<output_format>
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
</output_format>
"""

# Batch prompt template for generating tests for multiple endpoints at once
DEFAULT_BATCH_PROMPT_XML = """<task>
You are an expert API testing assistant. Generate comprehensive test cases for multiple API endpoints in a single batch.
</task>

<shared_context>
<learned_patterns>
{patterns}
</learned_patterns>
</shared_context>

<endpoints>
{endpoints_list}
</endpoints>

<instructions>
Generate 2-3 test cases for EACH endpoint listed above. For each endpoint, provide:
1. A clear test scenario description
2. Request body/parameters with realistic test data - USE PROVIDED EXAMPLES when available
3. ALL REQUIRED QUERY PARAMETERS - Check parameter descriptions carefully
4. Expected response status code and key fields - USE PROVIDED RESPONSE EXAMPLES when available

IMPORTANT:
- Request examples show the expected format - use them as templates
- Response examples show what successful responses look like
- Query parameters may be required even if not explicitly marked - check descriptions
- Path parameters need realistic values (UUIDs, IDs, etc.) based on schema type
</instructions>

<output_format>
Return your response as a JSON object with this structure:
{{
  "test_cases": [
    {{
      "endpoint": "METHOD /path",
      "test_scenario": "Description of what this test validates",
      "request_body": {{...}},
      "expected_response": {{
        "status_code": 200,
        "body": {{...}}
      }}
    }}
  ]
}}
Each test case MUST include the "endpoint" field with format "METHOD /path" to identify which endpoint it belongs to.
</output_format>
"""

DEFAULT_BATCH_PROMPT = """You are an expert API testing assistant. Generate comprehensive test cases for multiple API endpoints in a single batch.

## Shared Context
### Learned Patterns
{patterns}

## Endpoints
{endpoints_list}

## Instructions
Generate 2-3 test cases for EACH endpoint listed above. For each endpoint, provide:
1. A clear test scenario description
2. Request body/parameters with realistic test data - **USE PROVIDED EXAMPLES** when available
3. **ALL REQUIRED QUERY PARAMETERS** - Check parameter descriptions carefully
4. Expected response status code and key fields - **USE PROVIDED RESPONSE EXAMPLES** when available

**IMPORTANT**:
- Request examples show the expected format - use them as templates
- Response examples show what successful responses look like
- Query parameters may be required even if not explicitly marked - check descriptions
- Path parameters need realistic values (UUIDs, IDs, etc.) based on schema type

Return your response as a JSON object with this structure:
{{
  "test_cases": [
    {{
      "endpoint": "METHOD /path",
      "test_scenario": "Description of what this test validates",
      "request_body": {{...}},
      "expected_response": {{
        "status_code": 200,
        "body": {{...}}
      }}
    }}
  ]
}}
Each test case MUST include the "endpoint" field with format "METHOD /path" to identify which endpoint it belongs to.
"""


class PromptBuilder:
    """
    Build prompts for AI test generation
    
    Loads prompt templates from storage or uses defaults,
    and injects context information.
    
    Supports multiple formats:
    - Schema format: JSON (default) or YAML (more readable)
    - Prompt format: Markdown (default) or XML (better LLM alignment)
    """
    
    # Template name constants
    TEMPLATE_BASIC = 'test_generation_basic'
    TEMPLATE_ADVANCED = 'test_generation_advanced'
    TEMPLATE_EDGE_CASES = 'test_generation_edge_cases'
    TEMPLATE_BATCH = 'test_generation_batch'
    
    def __init__(self, storage: Optional[Any] = None, 
                 schema_format: SchemaFormat = SchemaFormat.YAML,
                 prompt_format: PromptFormat = PromptFormat.XML):
        """
        Initialize prompt builder
        
        Args:
            storage: Optional Storage instance for loading templates
            schema_format: Format for schemas (JSON or YAML, default: YAML)
            prompt_format: Format for prompts (Markdown or XML, default: XML)
        """
        self.storage = storage
        self.schema_format = schema_format
        self.prompt_format = prompt_format
        
        # Default templates (Markdown)
        self._default_templates_md = {
            self.TEMPLATE_BASIC: DEFAULT_BASIC_PROMPT,
            self.TEMPLATE_ADVANCED: DEFAULT_ADVANCED_PROMPT,
            self.TEMPLATE_EDGE_CASES: DEFAULT_EDGE_CASES_PROMPT,
            self.TEMPLATE_BATCH: DEFAULT_BATCH_PROMPT
        }
        
        # XML templates (better LLM alignment)
        self._default_templates_xml = {
                self.TEMPLATE_BASIC: DEFAULT_BASIC_PROMPT_XML,
                self.TEMPLATE_ADVANCED: DEFAULT_ADVANCED_PROMPT_XML,
                self.TEMPLATE_EDGE_CASES: DEFAULT_EDGE_CASES_PROMPT_XML,
                self.TEMPLATE_BATCH: DEFAULT_BATCH_PROMPT_XML
            }
        
        # Select templates based on format
        self._default_templates = (
            self._default_templates_xml if prompt_format == PromptFormat.XML 
            else self._default_templates_md
        )
    
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
    
    def build_batch_prompt(self, shared_context: Dict[str, Any], 
                          endpoints_info: List[Dict[str, Any]]) -> str:
        """
        Build a batch prompt for multiple endpoints
        
        Args:
            shared_context: Shared context dictionary (patterns, etc.)
            endpoints_info: List of endpoint information dictionaries
            
        Returns:
            Formatted prompt string ready for AI model
        """
        # Load batch template
        template = self._load_template(self.TEMPLATE_BATCH)
        
        # Format patterns
        patterns = shared_context.get('patterns', [])
        patterns_str = self._format_patterns(patterns)
        
        # Format endpoints list
        endpoints_list = self._format_endpoints_list(endpoints_info)
        
        # Render template
        return template.format(
            patterns=patterns_str,
            endpoints_list=endpoints_list
        )
    
    def _format_endpoints_list(self, endpoints_info: List[Dict[str, Any]]) -> str:
        """
        Format list of endpoints for batch prompt
        
        Args:
            endpoints_info: List of endpoint information dictionaries
            
        Returns:
            Formatted string with endpoint details
        """
        if self.prompt_format == PromptFormat.XML:
            lines = []
            for i, endpoint in enumerate(endpoints_info, 1):
                method = endpoint.get('method', 'GET')
                path = endpoint.get('path', '')
                summary = endpoint.get('summary', '')
                description = endpoint.get('description', '')
                
                lines.append(f"<endpoint_{i}>")
                lines.append(f"<method>{method}</method>")
                lines.append(f"<path>{path}</path>")
                if summary:
                    lines.append(f"<summary>{summary}</summary>")
                if description:
                    lines.append(f"<description>{description}</description>")
                
                # Request schema (compact)
                request_schema = endpoint.get('request_schema', {})
                if request_schema:
                    request_schema_str = self._format_schema(request_schema)
                    lines.append(f"<request_schema>{request_schema_str}</request_schema>")
                
                # Request examples (top 1 only for batch)
                request_examples = endpoint.get('request_examples', [])
                if request_examples:
                    example_str = self._format_examples(request_examples[:1], "Request Example")
                    lines.append(f"<request_example>{example_str}</request_example>")
                
                # Response schemas (compact)
                response_schemas = endpoint.get('response_schemas', {})
                if response_schemas:
                    # Only include 200/201/400/404 status codes for batch
                    key_statuses = ['200', '201', '400', '404']
                    filtered_schemas = {k: v for k, v in response_schemas.items() if k in key_statuses}
                    if filtered_schemas:
                        response_schemas_str = self._format_response_schemas(filtered_schemas)
                        lines.append(f"<response_schemas>{response_schemas_str}</response_schemas>")
                
                # Response examples (top 1 per status for batch)
                response_examples = endpoint.get('response_examples', {})
                if response_examples:
                    filtered_examples = {k: v[:1] for k, v in response_examples.items() if k in key_statuses}
                    if filtered_examples:
                        response_examples_str = self._format_response_examples(filtered_examples)
                        lines.append(f"<response_examples>{response_examples_str}</response_examples>")
                
                # Parameters (compact)
                parameters = endpoint.get('parameters', [])
                if parameters:
                    parameters_str = self._format_parameters(parameters)
                    lines.append(f"<parameters>{parameters_str}</parameters>")
                
                lines.append(f"</endpoint_{i}>")
                lines.append("")
            
            return "\n".join(lines).strip()
        else:
            # Markdown format
            lines = []
            for i, endpoint in enumerate(endpoints_info, 1):
                method = endpoint.get('method', 'GET')
                path = endpoint.get('path', '')
                summary = endpoint.get('summary', '')
                description = endpoint.get('description', '')
                
                lines.append(f"### Endpoint {i}: {method} {path}")
                if summary:
                    lines.append(f"**Summary**: {summary}")
                if description:
                    lines.append(f"**Description**: {description}")
                
                # Request schema (compact)
                request_schema = endpoint.get('request_schema', {})
                if request_schema:
                    request_schema_str = self._format_schema(request_schema)
                    lines.append(f"**Request Schema**:\n{request_schema_str}")
                
                # Request examples (top 1 only)
                request_examples = endpoint.get('request_examples', [])
                if request_examples:
                    example_str = self._format_examples(request_examples[:1], "Request Example")
                    lines.append(example_str)
                
                # Response schemas (compact, key statuses only)
                response_schemas = endpoint.get('response_schemas', {})
                if response_schemas:
                    key_statuses = ['200', '201', '400', '404']
                    filtered_schemas = {k: v for k, v in response_schemas.items() if k in key_statuses}
                    if filtered_schemas:
                        response_schemas_str = self._format_response_schemas(filtered_schemas)
                        lines.append(f"**Response Schemas**:\n{response_schemas_str}")
                
                # Response examples (top 1 per status)
                response_examples = endpoint.get('response_examples', {})
                if response_examples:
                    filtered_examples = {k: v[:1] for k, v in response_examples.items() if k in key_statuses}
                    if filtered_examples:
                        response_examples_str = self._format_response_examples(filtered_examples)
                        lines.append(response_examples_str)
                
                # Parameters
                parameters = endpoint.get('parameters', [])
                if parameters:
                    parameters_str = self._format_parameters(parameters)
                    lines.append(f"**Parameters**:\n{parameters_str}")
                
                lines.append("")
            
            return "\n".join(lines).strip()
    
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
        
        # Format request examples
        request_examples = endpoint_info.get('request_examples', [])
        request_examples_str = self._format_examples(request_examples, "Request Examples")
        
        # Format response schemas
        response_schemas = endpoint_info.get('response_schemas', {})
        response_schemas_str = self._format_response_schemas(response_schemas)
        
        # Format response examples
        response_examples = endpoint_info.get('response_examples', {})
        response_examples_str = self._format_response_examples(response_examples)
        
        # Format parameters with better context
        parameters = endpoint_info.get('parameters', [])
        parameters_str = self._format_parameters(parameters)
        
        # Extract history info
        history = context.get('history', {})
        history_count = history.get('count', 0)
        success_rate = history.get('success_rate')
        success_rate_str = f"{success_rate:.1%}" if success_rate is not None else "N/A"
        common_status_codes = history.get('common_status_codes', {})
        # Handle both dict and list formats
        if isinstance(common_status_codes, dict):
            common_status_codes_str = ', '.join(
                f"{code}({count})" for code, count in sorted(common_status_codes.items(), 
                                                             key=lambda x: x[1], reverse=True)[:5]
            ) or "N/A"
        elif isinstance(common_status_codes, list):
            # If it's a list, just join the codes
            common_status_codes_str = ', '.join(str(code) for code in common_status_codes[:5]) or "N/A"
        else:
            common_status_codes_str = "N/A"
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
            'request_examples': request_examples_str,
            'response_schemas': response_schemas_str,
            'response_examples': response_examples_str,
            'parameters': parameters_str,
            'history_count': history_count,
            'success_rate': success_rate_str,
            'common_status_codes': common_status_codes_str,
            'recent_results': recent_results_str,
            'validated_examples': validated_examples_str,
            'patterns': patterns_str
        }
    
    def _format_schema(self, schema: Dict[str, Any]) -> str:
        """Format schema dictionary as readable string (JSON or YAML)"""
        if not schema:
            return "No request body schema defined"
        
        try:
            if self.schema_format == SchemaFormat.YAML:
                import yaml
                return yaml.dump(schema, default_flow_style=False, sort_keys=False, allow_unicode=True)
            else:
                import json
                return json.dumps(schema, indent=2)
        except Exception as e:
            logger.warning(f"Error formatting schema: {e}, falling back to string")
            return str(schema)
    
    def _format_response_schemas(self, response_schemas: Dict[str, Any]) -> str:
        """Format response schemas as readable string (JSON, YAML, or TOON)"""
        if not response_schemas:
            return "No response schemas defined"
        
        if self.schema_format == SchemaFormat.TOON:
            # TOON format: compact tabular representation
            lines = []
            lines.append(f"response_schemas[{len(response_schemas)}]{{status_code,schema}}:")
            for status_code, schema in response_schemas.items():
                # Convert schema to compact string representation
                schema_str = str(schema).replace(',', ';').replace('\n', ' ')[:100]
                lines.append(f"  {status_code},{schema_str}")
            return "\n".join(lines)
        
        lines = []
        for status_code, schema in response_schemas.items():
            lines.append(f"Status {status_code}:")
            try:
                if self.schema_format == SchemaFormat.YAML:
                    import yaml
                    lines.append(yaml.dump(schema, default_flow_style=False, sort_keys=False, allow_unicode=True))
                else:
                    import json
                    lines.append(json.dumps(schema, indent=2))
            except Exception as e:
                logger.warning(f"Error formatting response schema for {status_code}: {e}")
                lines.append(str(schema))
            lines.append("")
        
        return "\n".join(lines).strip()
    
    def _format_parameters(self, parameters: List[Dict[str, Any]]) -> str:
        """Format parameters list as readable string (improved contextual formatting)"""
        if not parameters:
            return "No parameters defined"
        
        if self.prompt_format == PromptFormat.XML:
            # XML format for better structure
            lines = []
            for param in parameters:
                param_name = param.get('name', 'unknown')
                param_in = param.get('in', 'unknown')
                required = param.get('required', False)
                
                # Get type from resolved schema if available
                resolved_schema = param.get('resolved_schema', {})
                param_schema = param.get('schema', {})
                schema_to_use = resolved_schema if resolved_schema else param_schema
                
                param_type = schema_to_use.get('type', 'unknown')
                param_format = schema_to_use.get('format', '')
                if param_format:
                    param_type = f"{param_type} ({param_format})"
                
                description = param.get('description', '').replace("'", "&apos;").replace('"', '&quot;')
                example = param.get('example') or schema_to_use.get('example')
                enum_values = schema_to_use.get('enum', [])
                
                # Build parameter XML with all details
                param_xml = f"<parameter name='{param_name}' location='{param_in}' type='{param_type}' required='{str(required).lower()}'"
                if description:
                    param_xml += f" description='{description}'"
                if example is not None:
                    param_xml += f" example='{example}'"
                if enum_values:
                    param_xml += f" enum='{','.join(str(v) for v in enum_values)}'"
                param_xml += " />"
                lines.append(param_xml)
            return "\n".join(lines)
        else:
            # Markdown format
            lines = []
            for param in parameters:
                param_name = param.get('name', 'unknown')
                param_in = param.get('in', 'unknown')
                required = param.get('required', False)
                
                # Get type from resolved schema if available
                resolved_schema = param.get('resolved_schema', {})
                param_schema = param.get('schema', {})
                schema_to_use = resolved_schema if resolved_schema else param_schema
                
                param_type = schema_to_use.get('type', 'unknown')
                param_format = schema_to_use.get('format', '')
                if param_format:
                    param_type = f"{param_type} ({param_format})"
                
                required_str = "**REQUIRED**" if required else "optional"
                description = param.get('description', '')
                example = param.get('example') or schema_to_use.get('example')
                enum_values = schema_to_use.get('enum', [])
                
                line = f"- **{param_name}** ({param_in}, {param_type}, {required_str})"
                if description:
                    line += f": {description}"
                if example is not None:
                    line += f" (example: {example})"
                if enum_values:
                    line += f" [enum: {', '.join(str(v) for v in enum_values)}]"
                lines.append(line)
            return "\n".join(lines)
    
    def _format_examples(self, examples: List[Dict[str, Any]], title: str = "Examples") -> str:
        """Format examples list as readable string"""
        if not examples:
            return f"No {title.lower()} available"
        
        lines = []
        for i, example in enumerate(examples[:3], 1):  # Show top 3 examples
            name = example.get('name', f'Example {i}')
            value = example.get('value', {})
            summary = example.get('summary', '')
            
            try:
                if self.schema_format == SchemaFormat.YAML:
                    import yaml
                    value_str = yaml.dump(value, default_flow_style=False, sort_keys=False, allow_unicode=True)
                else:
                    import json
                    value_str = json.dumps(value, indent=2)
                
                if summary:
                    lines.append(f"{name} ({summary}):")
                else:
                    lines.append(f"{name}:")
                lines.append(value_str)
                lines.append("")
            except Exception as e:
                logger.warning(f"Error formatting example: {e}")
                lines.append(f"{name}: {str(value)[:200]}")
        
        return "\n".join(lines).strip()
    
    def _format_response_examples(self, response_examples: Dict[str, List[Dict[str, Any]]]) -> str:
        """Format response examples by status code"""
        if not response_examples:
            return "No response examples available"
        
        lines = []
        for status_code, examples in sorted(response_examples.items()):
            if not examples:
                continue
            
            lines.append(f"Status {status_code} Examples:")
            for i, example in enumerate(examples[:2], 1):  # Show top 2 per status
                name = example.get('name', f'Example {i}')
                value = example.get('value', {})
                summary = example.get('summary', '')
                
                try:
                    if self.schema_format == SchemaFormat.YAML:
                        import yaml
                        value_str = yaml.dump(value, default_flow_style=False, sort_keys=False, allow_unicode=True)
                    else:
                        import json
                        value_str = json.dumps(value, indent=2)
                    
                    if summary:
                        lines.append(f"  {name} ({summary}):")
                    else:
                        lines.append(f"  {name}:")
                    # Indent the value
                    indented_value = "\n".join("    " + line for line in value_str.split("\n"))
                    lines.append(indented_value)
                    lines.append("")
                except Exception as e:
                    logger.warning(f"Error formatting response example: {e}")
                    lines.append(f"  {name}: {str(value)[:200]}")
        
        return "\n".join(lines).strip() if lines else "No response examples available"
    
    def _format_recent_results(self, recent_results: List[Dict[str, Any]]) -> str:
        """Format recent test results as readable string (improved contextual formatting)"""
        if not recent_results:
            return "No recent test results"
        
        if self.prompt_format == PromptFormat.XML:
            # XML format for better structure
            lines = []
            for result in recent_results[:5]:
                status = result.get('status', 'unknown')
                status_code = result.get('status_code', 'N/A')
                response_time = result.get('response_time_ms', 'N/A')
                timestamp = result.get('timestamp', 'N/A')
                lines.append(f"<result status='{status}' status_code='{status_code}' response_time_ms='{response_time}' timestamp='{timestamp}' />")
            return "\n".join(lines)
        else:
            # Markdown format
            lines = []
            for result in recent_results[:5]:
                status = result.get('status', 'unknown')
                status_code = result.get('status_code', 'N/A')
                response_time = result.get('response_time_ms', 'N/A')
                lines.append(f"- {status} (status: {status_code}, time: {response_time}ms)")
            return "\n".join(lines)
    
    def _format_validated_examples(self, examples: List[Dict[str, Any]]) -> str:
        """Format validated test examples as readable string (JSON, YAML, or TOON)"""
        if not examples:
            return "No validated examples available"
        
        if self.schema_format == SchemaFormat.TOON:
            # TOON format: compact tabular representation
            return self._format_examples_toon(examples)
        
        # JSON or YAML format
        lines = []
        for i, example in enumerate(examples[:3], 1):  # Show top 3 examples
            scenario = example.get('test_scenario', 'N/A')
            status = example.get('validation_status', 'N/A')
            lines.append(f"Example {i}: {scenario} (status: {status})")
            request_body = example.get('request_body')
            if request_body:
                try:
                    if self.schema_format == SchemaFormat.YAML:
                        import yaml
                        lines.append(f"  Request:\n{yaml.dump(request_body, default_flow_style=False, sort_keys=False, allow_unicode=True, indent=2)}")
                    else:
                        import json
                        lines.append(f"  Request: {json.dumps(request_body, indent=2)}")
                except Exception as e:
                    logger.warning(f"Error formatting example request body: {e}")
                    lines.append(f"  Request: {str(request_body)}")
        
        return "\n".join(lines)
    
    def _format_examples_toon(self, examples: List[Dict[str, Any]]) -> str:
        """Format examples in TOON format (compact tabular)"""
        if not examples:
            return "No validated examples available"
        
        # Extract common fields from all examples
        all_keys = set()
        for example in examples[:3]:
            all_keys.update(example.keys())
        
        # Key fields to include in TOON format
        key_fields = ['test_scenario', 'validation_status', 'request_body', 'expected_response']
        # Filter to only include fields that exist in examples
        key_fields = [f for f in key_fields if f in all_keys]
        
        lines = []
        lines.append(f"validated_examples[{len(examples[:3])}]{{{','.join(key_fields)}}}:")
        
        for example in examples[:3]:
            row_values = []
            for field in key_fields:
                value = example.get(field, 'N/A')
                # Convert complex objects to string representation
                if isinstance(value, (dict, list)):
                    # For TOON, we'll use a compact representation
                    if isinstance(value, dict):
                        # Show key-value pairs in compact form
                        compact = ','.join(f"{k}:{v}" for k, v in value.items() if not isinstance(v, (dict, list)))
                        row_values.append(compact if compact else str(value)[:50])
                    else:
                        row_values.append(str(value)[:50])
                else:
                    # Escape commas in string values
                    str_value = str(value).replace(',', ';')
                    row_values.append(str_value)
            lines.append("  " + ",".join(row_values))
        
        return "\n".join(lines)
    
    def _format_patterns(self, patterns: List[Dict[str, Any]]) -> str:
        """Format learned patterns as readable string (JSON, YAML, or TOON)"""
        if not patterns:
            return "No learned patterns available"
        
        if self.schema_format == SchemaFormat.TOON:
            # TOON format: compact tabular representation
            return self._format_patterns_toon(patterns)
        
        # JSON or YAML format
        lines = []
        for pattern in patterns[:3]:  # Show top 3 patterns
            pattern_type = pattern.get('pattern_type', 'unknown')
            effectiveness = pattern.get('effectiveness', 0)
            pattern_data = pattern.get('pattern_data', {})
            lines.append(f"- {pattern_type} (effectiveness: {effectiveness:.2f})")
            if pattern_data:
                try:
                    if self.schema_format == SchemaFormat.YAML:
                        import yaml
                        lines.append(f"  Data:\n{yaml.dump(pattern_data, default_flow_style=False, sort_keys=False, allow_unicode=True, indent=2)}")
                    else:
                        import json
                        lines.append(f"  Data: {json.dumps(pattern_data, indent=2)}")
                except Exception as e:
                    logger.warning(f"Error formatting pattern data: {e}")
                    lines.append(f"  Data: {str(pattern_data)}")
        
        return "\n".join(lines)
    
    def _format_patterns_toon(self, patterns: List[Dict[str, Any]]) -> str:
        """Format patterns in TOON format (compact tabular)"""
        if not patterns:
            return "No learned patterns available"
        
        lines = []
        lines.append(f"patterns[{len(patterns[:3])}]{{pattern_type,effectiveness,pattern_data}}:")
        
        for pattern in patterns[:3]:
            pattern_type = pattern.get('pattern_type', 'unknown')
            effectiveness = pattern.get('effectiveness', 0)
            pattern_data = pattern.get('pattern_data', {})
            
            # Format pattern_data as compact string
            if isinstance(pattern_data, dict):
                data_str = ','.join(f"{k}:{v}" for k, v in pattern_data.items() if not isinstance(v, (dict, list)))
                if not data_str:
                    data_str = str(pattern_data)[:50]
            else:
                data_str = str(pattern_data)[:50]
            
            # Escape commas
            data_str = data_str.replace(',', ';')
            lines.append(f"  {pattern_type},{effectiveness:.2f},{data_str}")
        
        return "\n".join(lines)
    
    def _convert_to_toon(self, data: Any, name: str = "data") -> str:
        """
        Convert data structure to TOON format
        
        Args:
            data: Data to convert (dict, list, or primitive)
            name: Name for the data structure
            
        Returns:
            TOON formatted string
        """
        if isinstance(data, list):
            if not data:
                return f"{name}[0]{{}}:"
            
            # Check if all items are dicts with same keys
            if all(isinstance(item, dict) for item in data):
                # Get all unique keys
                all_keys = set()
                for item in data:
                    all_keys.update(item.keys())
                keys = sorted(list(all_keys))
                
                lines = [f"{name}[{len(data)}]{{{','.join(keys)}}}:"]
                for item in data:
                    values = []
                    for key in keys:
                        value = item.get(key, '')
                        # Convert to string and escape commas
                        str_value = str(value).replace(',', ';').replace('\n', ' ')
                        # Truncate long values
                        if len(str_value) > 100:
                            str_value = str_value[:97] + "..."
                        values.append(str_value)
                    lines.append("  " + ",".join(values))
                return "\n".join(lines)
            else:
                # Simple list of primitives
                values = [str(item).replace(',', ';') for item in data]
                return f"{name}[{len(data)}]:\n  " + "\n  ".join(values)
        
        elif isinstance(data, dict):
            # Single object - convert to key:value pairs
            pairs = [f"{k}:{v}" for k, v in data.items() if not isinstance(v, (dict, list))]
            return f"{name}{{{','.join(pairs)}}}"
        
        else:
            # Primitive value
            return f"{name}: {data}"
    
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

