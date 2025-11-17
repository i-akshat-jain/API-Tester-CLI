"""
Response parser for AI test generation

Parses AI model responses and extracts test cases, handling various formats
and validating the structure.
"""

import json
import re
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class ResponseParser:
    """
    Parse AI model responses and extract test cases
    
    Supports multiple response formats:
    - JSON with test_cases array
    - JSON with single test case object
    - Markdown code blocks with JSON
    """
    
    def __init__(self):
        """Initialize response parser"""
        pass
    
    def parse_test_cases(self, ai_response: str) -> List[Dict[str, Any]]:
        """
        Parse AI response and extract test cases
        
        Args:
            ai_response: Raw response string from AI model
            
        Returns:
            List of test case dictionaries
        """
        if not ai_response or not ai_response.strip():
            logger.warning("Empty AI response received")
            return []
        
        # Try different parsing strategies
        test_cases = []
        
        # Strategy 1: Try to extract JSON from markdown code blocks
        json_str = self._extract_json_from_markdown(ai_response)
        if json_str:
            test_cases = self._parse_json_response(json_str)
            if test_cases:
                return test_cases
        
        # Strategy 2: Try to parse entire response as JSON
        test_cases = self._parse_json_response(ai_response)
        if test_cases:
            return test_cases
        
        # Strategy 3: Try to find JSON object in text
        json_str = self._extract_json_from_text(ai_response)
        if json_str:
            test_cases = self._parse_json_response(json_str)
            if test_cases:
                return test_cases
        
        # If all strategies fail, log warning and return empty list
        logger.warning("Could not parse AI response as valid test cases")
        return []
    
    def _extract_json_from_markdown(self, text: str) -> Optional[str]:
        """
        Extract JSON from markdown code blocks
        
        Args:
            text: Text that may contain markdown code blocks
            
        Returns:
            Extracted JSON string or None
        """
        # Look for JSON code blocks: ```json ... ``` or ``` ... ```
        patterns = [
            r'```json\s*\n(.*?)\n```',
            r'```\s*\n(.*?)\n```',
            r'```json\s*(.*?)```',
            r'```\s*(.*?)```'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                # Try to parse as JSON to validate
                try:
                    json.loads(match.strip())
                    return match.strip()
                except json.JSONDecodeError:
                    continue
        
        return None
    
    def _extract_json_from_text(self, text: str) -> Optional[str]:
        """
        Extract JSON object from text by finding first { ... } block
        
        Args:
            text: Text that may contain JSON
            
        Returns:
            Extracted JSON string or None
        """
        # Find first { ... } block
        start_idx = text.find('{')
        if start_idx == -1:
            return None
        
        # Find matching closing brace
        brace_count = 0
        for i in range(start_idx, len(text)):
            if text[i] == '{':
                brace_count += 1
            elif text[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    json_str = text[start_idx:i+1]
                    # Try to parse to validate
                    try:
                        json.loads(json_str)
                        return json_str
                    except json.JSONDecodeError:
                        return None
        
        return None
    
    def _parse_json_response(self, json_str: str) -> List[Dict[str, Any]]:
        """
        Parse JSON string and extract test cases
        
        Args:
            json_str: JSON string to parse
            
        Returns:
            List of test case dictionaries
        """
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            return []
        
        # Handle different response formats
        test_cases = []
        
        # Format 1: { "test_cases": [...] }
        if isinstance(data, dict) and 'test_cases' in data:
            test_cases_list = data['test_cases']
            if isinstance(test_cases_list, list):
                for test_case in test_cases_list:
                    if self._validate_test_case(test_case):
                        normalized = self._normalize_test_case(test_case)
                        test_cases.append(normalized)
        
        # Format 2: Single test case object { "test_scenario": ..., "request_body": ..., ... }
        elif isinstance(data, dict) and self._validate_test_case(data):
            normalized = self._normalize_test_case(data)
            test_cases.append(normalized)
        
        # Format 3: Array of test cases [...]
        elif isinstance(data, list):
            for test_case in data:
                if isinstance(test_case, dict) and self._validate_test_case(test_case):
                    normalized = self._normalize_test_case(test_case)
                    test_cases.append(normalized)
        
        return test_cases
    
    def _validate_test_case(self, test_case: Dict[str, Any]) -> bool:
        """
        Validate that a test case has required fields
        
        Args:
            test_case: Test case dictionary to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(test_case, dict):
            return False
        
        # Must have test_scenario or at least request_body/expected_response
        has_scenario = 'test_scenario' in test_case
        has_request = 'request_body' in test_case
        has_response = 'expected_response' in test_case
        
        # At minimum, should have either scenario or both request and response
        if not has_scenario and not (has_request or has_response):
            logger.debug("Test case missing required fields: test_scenario or request_body/expected_response")
            return False
        
        # Validate expected_response structure if present
        # Note: status_code can be missing - it will be added during normalization
        if has_response:
            expected_response = test_case['expected_response']
            # Just check it's a dict or can be converted to one
            if not isinstance(expected_response, (dict, type(None))):
                logger.debug("Test case expected_response should be a dict or None")
                return False
        
        return True
    
    def _normalize_test_case(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize test case to standard format
        
        Args:
            test_case: Test case dictionary to normalize
            
        Returns:
            Normalized test case dictionary
        """
        normalized = {
            'test_scenario': test_case.get('test_scenario', 'Generated test case'),
            'request_body': test_case.get('request_body'),
            'expected_response': test_case.get('expected_response', {}),
            'rationale': test_case.get('rationale')
        }
        
        # Ensure expected_response has status_code
        if 'expected_response' in test_case:
            expected_response = test_case['expected_response']
            if isinstance(expected_response, dict):
                # If status_code is missing, try to infer from structure
                if 'status_code' not in expected_response:
                    # Default to 200 if not specified
                    normalized['expected_response']['status_code'] = 200
                else:
                    normalized['expected_response'] = expected_response
            else:
                # If expected_response is not a dict, create one
                normalized['expected_response'] = {
                    'status_code': 200,
                    'body': expected_response
                }
        else:
            # Default expected response
            normalized['expected_response'] = {
                'status_code': 200
            }
        
        # Clean up None values
        normalized = {k: v for k, v in normalized.items() if v is not None}
        
        return normalized

