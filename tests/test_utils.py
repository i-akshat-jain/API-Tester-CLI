"""
Comprehensive tests for utility functions
"""

import pytest
import os
from apitest.utils import deep_get, format_duration, expand_env_vars


class TestDeepGet:
    """Test deep_get function"""
    
    def test_deep_get_simple_key(self):
        """Test getting simple key"""
        data = {'key': 'value'}
        assert deep_get(data, 'key') == 'value'
    
    def test_deep_get_nested_key(self):
        """Test getting nested key"""
        data = {
            'level1': {
                'level2': {
                    'level3': 'value'
                }
            }
        }
        assert deep_get(data, 'level1.level2.level3') == 'value'
    
    def test_deep_get_missing_key(self):
        """Test getting missing key"""
        data = {'key': 'value'}
        assert deep_get(data, 'missing') is None
    
    def test_deep_get_missing_key_with_default(self):
        """Test getting missing key with default"""
        data = {'key': 'value'}
        assert deep_get(data, 'missing', 'default') == 'default'
    
    def test_deep_get_partial_path(self):
        """Test getting partial path that doesn't exist"""
        data = {
            'level1': {
                'level2': 'value'
            }
        }
        assert deep_get(data, 'level1.level2.level3') is None
    
    def test_deep_get_empty_path(self):
        """Test getting with empty path"""
        data = {'key': 'value'}
        assert deep_get(data, '') is None
    
    def test_deep_get_none_data(self):
        """Test getting from None data"""
        assert deep_get(None, 'key') is None
    
    def test_deep_get_non_dict_intermediate(self):
        """Test getting when intermediate value is not a dict"""
        data = {
            'level1': 'not_a_dict'
        }
        assert deep_get(data, 'level1.level2') is None
    
    def test_deep_get_integer_value(self):
        """Test getting integer value"""
        data = {'count': 42}
        assert deep_get(data, 'count') == 42
    
    def test_deep_get_list_value(self):
        """Test getting list value"""
        data = {'items': [1, 2, 3]}
        assert deep_get(data, 'items') == [1, 2, 3]
    
    def test_deep_get_complex_nested(self):
        """Test getting from complex nested structure"""
        data = {
            'api': {
                'version': '1.0',
                'endpoints': {
                    'users': {
                        'path': '/users',
                        'methods': ['GET', 'POST']
                    }
                }
            }
        }
        assert deep_get(data, 'api.endpoints.users.path') == '/users'
        assert deep_get(data, 'api.endpoints.users.methods') == ['GET', 'POST']


class TestFormatDuration:
    """Test format_duration function"""
    
    def test_format_duration_seconds(self):
        """Test formatting duration in seconds"""
        assert format_duration(1.5) == "1.50s"
        assert format_duration(10.0) == "10.00s"
        assert format_duration(0.5) == "500ms"
    
    def test_format_duration_milliseconds(self):
        """Test formatting duration in milliseconds"""
        assert format_duration(0.1) == "100ms"
        assert format_duration(0.5) == "500ms"
        assert format_duration(0.001) == "1ms"
    
    def test_format_duration_zero(self):
        """Test formatting zero duration"""
        assert format_duration(0.0) == "0ms"
    
    def test_format_duration_very_small(self):
        """Test formatting very small duration"""
        assert format_duration(0.0001) == "0ms"
    
    def test_format_duration_large(self):
        """Test formatting large duration"""
        assert format_duration(3600.0) == "3600.00s"
        assert format_duration(120.5) == "120.50s"
    
    def test_format_duration_precision(self):
        """Test duration formatting precision"""
        result = format_duration(1.234567)
        assert result == "1.23s"  # Should round to 2 decimal places


class TestExpandEnvVars:
    """Test expand_env_vars function"""
    
    def test_expand_env_vars_simple(self, monkeypatch):
        """Test expanding simple environment variable"""
        monkeypatch.setenv('TEST_VAR', 'test_value')
        assert expand_env_vars('$TEST_VAR') == 'test_value'
    
    def test_expand_env_vars_braces(self, monkeypatch):
        """Test expanding environment variable with braces"""
        monkeypatch.setenv('TEST_VAR', 'test_value')
        assert expand_env_vars('${TEST_VAR}') == 'test_value'
    
    def test_expand_env_vars_with_default(self, monkeypatch):
        """Test expanding environment variable with default"""
        monkeypatch.delenv('TEST_VAR', raising=False)
        assert expand_env_vars('${TEST_VAR:-default_value}') == 'default_value'
    
    def test_expand_env_vars_with_default_override(self, monkeypatch):
        """Test expanding environment variable that exists with default"""
        monkeypatch.setenv('TEST_VAR', 'actual_value')
        assert expand_env_vars('${TEST_VAR:-default_value}') == 'actual_value'
    
    def test_expand_env_vars_multiple(self, monkeypatch):
        """Test expanding multiple environment variables"""
        monkeypatch.setenv('VAR1', 'value1')
        monkeypatch.setenv('VAR2', 'value2')
        assert expand_env_vars('$VAR1 and $VAR2') == 'value1 and value2'
    
    def test_expand_env_vars_mixed_format(self, monkeypatch):
        """Test expanding mixed format environment variables"""
        monkeypatch.setenv('VAR1', 'value1')
        monkeypatch.setenv('VAR2', 'value2')
        assert expand_env_vars('$VAR1 and ${VAR2}') == 'value1 and value2'
    
    def test_expand_env_vars_not_found(self):
        """Test expanding non-existent environment variable"""
        result = expand_env_vars('$NONEXISTENT_VAR')
        assert result == '$NONEXISTENT_VAR'  # Should return original if not found
    
    def test_expand_env_vars_not_found_with_default(self):
        """Test expanding non-existent environment variable with default"""
        assert expand_env_vars('${NONEXISTENT_VAR:-default}') == 'default'
    
    def test_expand_env_vars_empty_string(self):
        """Test expanding empty string"""
        assert expand_env_vars('') == ''
    
    def test_expand_env_vars_no_vars(self):
        """Test string with no environment variables"""
        assert expand_env_vars('plain text') == 'plain text'
    
    def test_expand_env_vars_none(self):
        """Test expanding None value"""
        assert expand_env_vars(None) is None
    
    def test_expand_env_vars_non_string(self):
        """Test expanding non-string value"""
        assert expand_env_vars(123) == 123
        assert expand_env_vars(['list']) == ['list']
        assert expand_env_vars({'dict': 'value'}) == {'dict': 'value'}
    
    def test_expand_env_vars_special_characters(self, monkeypatch):
        """Test expanding environment variable with special characters"""
        monkeypatch.setenv('SPECIAL_VAR', 'value with spaces and !@#$%')
        assert expand_env_vars('$SPECIAL_VAR') == 'value with spaces and !@#$%'
    
    def test_expand_env_vars_in_middle(self, monkeypatch):
        """Test expanding environment variable in middle of string"""
        monkeypatch.setenv('VAR', 'middle')
        # Note: $VAR_ might be interpreted as $VAR_ (with underscore), so use braces or spaces
        assert expand_env_vars('prefix_${VAR}_suffix') == 'prefix_middle_suffix'
        # Also test with spaces
        assert expand_env_vars('prefix $VAR suffix') == 'prefix middle suffix'
    
    def test_expand_env_vars_empty_default(self):
        """Test expanding with empty default"""
        assert expand_env_vars('${NONEXISTENT_VAR:-}') == ''
    
    def test_expand_env_vars_multiple_defaults(self, monkeypatch):
        """Test expanding multiple variables with defaults"""
        monkeypatch.setenv('VAR1', 'value1')
        monkeypatch.delenv('VAR2', raising=False)
        result = expand_env_vars('${VAR1:-default1} and ${VAR2:-default2}')
        assert result == 'value1 and default2'
    
    def test_expand_env_vars_underscore_name(self, monkeypatch):
        """Test expanding environment variable with underscore"""
        monkeypatch.setenv('TEST_VAR_NAME', 'value')
        assert expand_env_vars('$TEST_VAR_NAME') == 'value'
    
    def test_expand_env_vars_numeric_name(self, monkeypatch):
        """Test expanding environment variable with numeric characters"""
        monkeypatch.setenv('VAR123', 'value')
        assert expand_env_vars('$VAR123') == 'value'
    
    def test_expand_env_vars_complex_string(self, monkeypatch):
        """Test expanding in complex string"""
        monkeypatch.setenv('HOST', 'api.example.com')
        monkeypatch.setenv('PORT', '8080')
        result = expand_env_vars('http://${HOST}:${PORT:-3000}/api')
        assert result == 'http://api.example.com:8080/api'
    
    def test_expand_env_vars_nested_braces(self):
        """Test expanding with nested braces (edge case)"""
        # This should not match nested braces
        result = expand_env_vars('${VAR${NESTED}}')
        # Should return original or handle gracefully
        assert isinstance(result, str)
    
    def test_expand_env_vars_unicode(self, monkeypatch):
        """Test expanding with unicode characters"""
        monkeypatch.setenv('UNICODE_VAR', '测试值')
        assert expand_env_vars('$UNICODE_VAR') == '测试值'
    
    def test_expand_env_vars_newlines(self, monkeypatch):
        """Test expanding with newlines"""
        monkeypatch.setenv('MULTILINE_VAR', 'line1\nline2')
        result = expand_env_vars('$MULTILINE_VAR')
        assert 'line1' in result
        assert 'line2' in result
    
    def test_expand_env_vars_dollar_sign_escape(self):
        """Test handling dollar signs that aren't variables"""
        result = expand_env_vars('Price: $100')
        # Should not try to expand $100 as a variable
        assert '$100' in result or result == 'Price: $100'


class TestEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_deep_get_empty_dict(self):
        """Test deep_get with empty dictionary"""
        assert deep_get({}, 'key') is None
        assert deep_get({}, 'key', 'default') == 'default'
    
    def test_deep_get_empty_string_key(self):
        """Test deep_get with empty string key"""
        data = {'': 'empty_key_value'}
        assert deep_get(data, '') == 'empty_key_value'
    
    def test_format_duration_negative(self):
        """Test formatting negative duration"""
        # Should handle gracefully
        result = format_duration(-1.0)
        assert isinstance(result, str)
    
    def test_expand_env_vars_malformed_braces(self):
        """Test expanding with malformed braces"""
        result = expand_env_vars('${VAR')
        # Should handle gracefully
        assert isinstance(result, str)
    
    def test_expand_env_vars_only_dollar(self):
        """Test expanding string with only dollar sign"""
        assert expand_env_vars('$') == '$'
    
    def test_expand_env_vars_double_dollar(self):
        """Test expanding with double dollar sign"""
        result = expand_env_vars('$$VAR')
        # Should handle gracefully
        assert isinstance(result, str)

