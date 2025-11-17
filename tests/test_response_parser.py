"""
Tests for response parser
"""

import pytest
import json
from apitest.ai.response_parser import ResponseParser


class TestResponseParser:
    """Test ResponseParser class"""
    
    def test_init(self):
        """Test ResponseParser initialization"""
        parser = ResponseParser()
        assert parser is not None
    
    def test_parse_test_cases_json_array_format(self):
        """Test parsing JSON with test_cases array"""
        parser = ResponseParser()
        
        response = json.dumps({
            "test_cases": [
                {
                    "test_scenario": "Create user with valid data",
                    "request_body": {"name": "John", "email": "john@example.com"},
                    "expected_response": {
                        "status_code": 201,
                        "body": {"id": 1, "name": "John"}
                    }
                },
                {
                    "test_scenario": "Create user with missing email",
                    "request_body": {"name": "John"},
                    "expected_response": {
                        "status_code": 400,
                        "body": {"error": "Email is required"}
                    }
                }
            ]
        })
        
        test_cases = parser.parse_test_cases(response)
        
        assert len(test_cases) == 2
        assert test_cases[0]['test_scenario'] == "Create user with valid data"
        assert test_cases[0]['request_body']['name'] == "John"
        assert test_cases[0]['expected_response']['status_code'] == 201
        assert test_cases[1]['expected_response']['status_code'] == 400
    
    def test_parse_test_cases_single_object_format(self):
        """Test parsing single test case object"""
        parser = ResponseParser()
        
        response = json.dumps({
            "test_scenario": "Get user by ID",
            "request_body": None,
            "expected_response": {
                "status_code": 200,
                "body": {"id": 1, "name": "John"}
            }
        })
        
        test_cases = parser.parse_test_cases(response)
        
        assert len(test_cases) == 1
        assert test_cases[0]['test_scenario'] == "Get user by ID"
        assert test_cases[0]['expected_response']['status_code'] == 200
    
    def test_parse_test_cases_array_format(self):
        """Test parsing array of test cases directly"""
        parser = ResponseParser()
        
        response = json.dumps([
            {
                "test_scenario": "Test 1",
                "request_body": {"key": "value"},
                "expected_response": {"status_code": 200}
            },
            {
                "test_scenario": "Test 2",
                "request_body": {"key2": "value2"},
                "expected_response": {"status_code": 201}
            }
        ])
        
        test_cases = parser.parse_test_cases(response)
        
        assert len(test_cases) == 2
        assert test_cases[0]['test_scenario'] == "Test 1"
        assert test_cases[1]['test_scenario'] == "Test 2"
    
    def test_parse_test_cases_markdown_code_block(self):
        """Test parsing JSON from markdown code block"""
        parser = ResponseParser()
        
        response = """Here are the test cases:

```json
{
  "test_cases": [
    {
      "test_scenario": "Create user",
      "request_body": {"name": "John"},
      "expected_response": {"status_code": 201}
    }
  ]
}
```

These test cases cover the main scenarios."""
        
        test_cases = parser.parse_test_cases(response)
        
        assert len(test_cases) == 1
        assert test_cases[0]['test_scenario'] == "Create user"
        assert test_cases[0]['expected_response']['status_code'] == 201
    
    def test_parse_test_cases_markdown_code_block_no_lang(self):
        """Test parsing JSON from markdown code block without language"""
        parser = ResponseParser()
        
        response = """```
{
  "test_cases": [
    {
      "test_scenario": "Test case",
      "request_body": {"key": "value"},
      "expected_response": {"status_code": 200}
    }
  ]
}
```"""
        
        test_cases = parser.parse_test_cases(response)
        
        assert len(test_cases) == 1
        assert test_cases[0]['test_scenario'] == "Test case"
    
    def test_parse_test_cases_json_in_text(self):
        """Test extracting JSON object from text"""
        parser = ResponseParser()
        
        response = """Here is the response with some text before and after.
{
  "test_cases": [
    {
      "test_scenario": "Extracted test",
      "request_body": {"data": "value"},
      "expected_response": {"status_code": 200}
    }
  ]
}
And some text after."""
        
        test_cases = parser.parse_test_cases(response)
        
        assert len(test_cases) == 1
        assert test_cases[0]['test_scenario'] == "Extracted test"
    
    def test_parse_test_cases_empty_response(self):
        """Test parsing empty response"""
        parser = ResponseParser()
        
        test_cases = parser.parse_test_cases("")
        assert test_cases == []
        
        test_cases = parser.parse_test_cases("   ")
        assert test_cases == []
    
    def test_parse_test_cases_invalid_json(self):
        """Test parsing invalid JSON"""
        parser = ResponseParser()
        
        response = "This is not valid JSON at all"
        test_cases = parser.parse_test_cases(response)
        
        assert test_cases == []
    
    def test_parse_test_cases_missing_required_fields(self):
        """Test parsing test case with missing required fields"""
        parser = ResponseParser()
        
        # Missing both test_scenario and request_body/expected_response
        response = json.dumps({
            "test_cases": [
                {
                    "some_field": "value"
                }
            ]
        })
        
        test_cases = parser.parse_test_cases(response)
        
        # Should filter out invalid test cases
        assert len(test_cases) == 0
    
    def test_parse_test_cases_missing_status_code(self):
        """Test parsing test case with missing status_code in expected_response"""
        parser = ResponseParser()
        
        response = json.dumps({
            "test_cases": [
                {
                    "test_scenario": "Test without status code",
                    "request_body": {"key": "value"},
                    "expected_response": {
                        "body": {"result": "ok"}
                    }
                }
            ]
        })
        
        test_cases = parser.parse_test_cases(response)
        
        # Should normalize and add default status_code
        assert len(test_cases) == 1
        assert test_cases[0]['expected_response']['status_code'] == 200
    
    def test_parse_test_cases_with_rationale(self):
        """Test parsing test case with rationale"""
        parser = ResponseParser()
        
        response = json.dumps({
            "test_cases": [
                {
                    "test_scenario": "Test with rationale",
                    "request_body": {"key": "value"},
                    "expected_response": {"status_code": 200},
                    "rationale": "This test validates the happy path"
                }
            ]
        })
        
        test_cases = parser.parse_test_cases(response)
        
        assert len(test_cases) == 1
        assert test_cases[0]['rationale'] == "This test validates the happy path"
    
    def test_normalize_test_case(self):
        """Test test case normalization"""
        parser = ResponseParser()
        
        test_case = {
            "test_scenario": "Test scenario",
            "request_body": {"name": "John"},
            "expected_response": {
                "status_code": 201,
                "body": {"id": 1}
            },
            "rationale": "Test rationale"
        }
        
        normalized = parser._normalize_test_case(test_case)
        
        assert normalized['test_scenario'] == "Test scenario"
        assert normalized['request_body']['name'] == "John"
        assert normalized['expected_response']['status_code'] == 201
        assert normalized['rationale'] == "Test rationale"
    
    def test_normalize_test_case_defaults(self):
        """Test test case normalization with defaults"""
        parser = ResponseParser()
        
        test_case = {
            "test_scenario": "Test"
        }
        
        normalized = parser._normalize_test_case(test_case)
        
        assert normalized['test_scenario'] == "Test"
        assert normalized['expected_response']['status_code'] == 200
    
    def test_validate_test_case_valid(self):
        """Test validating valid test case"""
        parser = ResponseParser()
        
        test_case = {
            "test_scenario": "Test",
            "request_body": {"key": "value"},
            "expected_response": {"status_code": 200}
        }
        
        assert parser._validate_test_case(test_case) is True
    
    def test_validate_test_case_without_scenario_but_with_request(self):
        """Test validating test case without scenario but with request"""
        parser = ResponseParser()
        
        test_case = {
            "request_body": {"key": "value"},
            "expected_response": {"status_code": 200}
        }
        
        assert parser._validate_test_case(test_case) is True
    
    def test_validate_test_case_invalid(self):
        """Test validating invalid test case"""
        parser = ResponseParser()
        
        # Missing all required fields
        test_case = {
            "some_field": "value"
        }
        
        assert parser._validate_test_case(test_case) is False
    
    def test_validate_test_case_not_dict(self):
        """Test validating non-dict test case"""
        parser = ResponseParser()
        
        assert parser._validate_test_case("not a dict") is False
        assert parser._validate_test_case([]) is False
        assert parser._validate_test_case(None) is False
    
    def test_extract_json_from_markdown(self):
        """Test extracting JSON from markdown"""
        parser = ResponseParser()
        
        text = """Some text
```json
{"key": "value"}
```
More text"""
        
        json_str = parser._extract_json_from_markdown(text)
        
        assert json_str == '{"key": "value"}'
        # Verify it's valid JSON
        data = json.loads(json_str)
        assert data['key'] == "value"
    
    def test_extract_json_from_text(self):
        """Test extracting JSON object from text"""
        parser = ResponseParser()
        
        text = """Before text
{"test": "value", "nested": {"key": "val"}}
After text"""
        
        json_str = parser._extract_json_from_text(text)
        
        assert json_str is not None
        data = json.loads(json_str)
        assert data['test'] == "value"
        assert data['nested']['key'] == "val"

