"""
Tests for pattern extractor AI enhancements
"""

import pytest
import json
from unittest.mock import Mock, patch
from pathlib import Path
import tempfile

from apitest.learning.pattern_extractor import PatternExtractor
from apitest.storage.database import Storage


class TestPatternExtractorAI:
    """Test PatternExtractor AI test pattern extraction"""
    
    def test_extract_patterns_from_ai_tests_empty(self, tmp_path):
        """Test extracting patterns with no validated tests"""
        storage = Storage(tmp_path / "test.db")
        extractor = PatternExtractor()
        
        result = extractor.extract_patterns_from_ai_tests(storage=storage)
        
        assert result['test_scenario_patterns'] == []
        assert result['data_quality_patterns'] == []
        assert result['edge_case_patterns'] == []
        assert result['structure_patterns'] == []
        assert result['patterns_saved'] == 0
        
        storage.close()
    
    def test_extract_patterns_from_ai_tests_basic(self, tmp_path):
        """Test extracting patterns from validated AI tests"""
        storage = Storage(tmp_path / "test.db")
        
        # Create validated test cases
        test_case_1 = storage.ai_tests.save_test_case(
            'test.yaml', 'POST', '/users',
            {
                'test_scenario': 'Create user with valid data',
                'request_body': {'name': 'John Doe', 'email': 'john@example.com'},
                'expected_response': {'status_code': 201}
            }
        )
        storage.ai_tests.update_validation_status(test_case_1, 'approved')
        
        test_case_2 = storage.ai_tests.save_test_case(
            'test.yaml', 'POST', '/users',
            {
                'test_scenario': 'Create user with valid data',
                'request_body': {'name': 'Jane Doe', 'email': 'jane@example.com'},
                'expected_response': {'status_code': 201}
            }
        )
        storage.ai_tests.update_validation_status(test_case_2, 'approved')
        
        extractor = PatternExtractor()
        result = extractor.extract_patterns_from_ai_tests(storage=storage)
        
        assert result['patterns_saved'] > 0
        assert len(result['test_scenario_patterns']) > 0
        assert len(result['data_quality_patterns']) > 0
        assert len(result['structure_patterns']) > 0
        
        storage.close()
    
    def test_extract_test_scenario_patterns(self, tmp_path):
        """Test extracting test scenario patterns"""
        storage = Storage(tmp_path / "test.db")
        
        # Create multiple test cases with similar scenarios
        for i in range(3):
            test_case_id = storage.ai_tests.save_test_case(
                'test.yaml', 'POST', f'/users/{i}',
                {
                    'test_scenario': 'Create user successfully',
                    'request_body': {'name': f'User {i}'}
                }
            )
            storage.ai_tests.update_validation_status(test_case_id, 'approved')
        
        extractor = PatternExtractor()
        validated_tests = storage.ai_tests.get_validated_test_cases(limit=100)
        patterns = extractor._extract_test_scenario_patterns(validated_tests)
        
        assert len(patterns) > 0
        # Should find the common scenario
        scenario_texts = [p.get('scenario_text', '').lower() for p in patterns if 'scenario_text' in p]
        assert any('create user' in text for text in scenario_texts)
        
        storage.close()
    
    def test_extract_data_quality_patterns(self, tmp_path):
        """Test extracting data quality patterns"""
        storage = Storage(tmp_path / "test.db")
        
        # Create test cases with consistent data patterns
        for i in range(3):
            test_case_id = storage.ai_tests.save_test_case(
                'test.yaml', 'POST', '/users',
                {
                    'test_scenario': 'Create user',
                    'request_body': {
                        'name': f'User {i}',
                        'email': f'user{i}@example.com',
                        'age': 25 + i
                    }
                }
            )
            storage.ai_tests.update_validation_status(test_case_id, 'approved')
        
        extractor = PatternExtractor()
        validated_tests = storage.ai_tests.get_validated_test_cases(limit=100)
        patterns = extractor._extract_data_quality_patterns(validated_tests)
        
        assert len(patterns) > 0
        # Should find patterns for common fields
        field_paths = [p.get('field_path', '') for p in patterns]
        assert 'name' in field_paths or 'email' in field_paths
        
        storage.close()
    
    def test_extract_edge_case_patterns(self, tmp_path):
        """Test extracting edge case patterns"""
        storage = Storage(tmp_path / "test.db")
        
        # Create edge case test
        test_case_id = storage.ai_tests.save_test_case(
            'test.yaml', 'POST', '/users',
            {
                'test_scenario': 'Create user with empty name boundary test',
                'request_body': {'name': '', 'email': 'test@example.com'}
            }
        )
        storage.ai_tests.update_validation_status(test_case_id, 'approved')
        
        # Create invalid test
        test_case_id2 = storage.ai_tests.save_test_case(
            'test.yaml', 'POST', '/users',
            {
                'test_scenario': 'Create user with invalid email format',
                'request_body': {'name': 'Test', 'email': 'invalid-email'}
            }
        )
        storage.ai_tests.update_validation_status(test_case_id2, 'approved')
        
        extractor = PatternExtractor()
        validated_tests = storage.ai_tests.get_validated_test_cases(limit=100)
        patterns = extractor._extract_edge_case_patterns(validated_tests)
        
        assert len(patterns) > 0
        # Should identify edge cases
        edge_types = [p.get('edge_type', '') for p in patterns]
        assert 'empty' in edge_types or 'invalid' in edge_types or 'boundary' in edge_types
        
        storage.close()
    
    def test_extract_structure_patterns(self, tmp_path):
        """Test extracting structure patterns"""
        storage = Storage(tmp_path / "test.db")
        
        # Create test cases with complete structure
        for i in range(5):
            test_case_id = storage.ai_tests.save_test_case(
                'test.yaml', 'POST', '/users',
                {
                    'test_scenario': f'Test {i}',
                    'request_body': {'name': f'User {i}'},
                    'expected_response': {'status_code': 201}
                }
            )
            storage.ai_tests.update_validation_status(test_case_id, 'approved')
        
        extractor = PatternExtractor()
        validated_tests = storage.ai_tests.get_validated_test_cases(limit=100)
        patterns = extractor._extract_structure_patterns(validated_tests)
        
        assert len(patterns) > 0
        structure_pattern = patterns[0]
        assert 'scenario_coverage' in structure_pattern
        assert 'request_body_coverage' in structure_pattern
        assert 'expected_response_coverage' in structure_pattern
        assert structure_pattern['scenario_coverage'] > 0
        assert structure_pattern['request_body_coverage'] > 0
        
        storage.close()
    
    def test_extract_scenario_keywords(self, tmp_path):
        """Test extracting keywords from scenarios"""
        storage = Storage(tmp_path / "test.db")
        extractor = PatternExtractor()
        
        keywords = extractor._extract_scenario_keywords("Create user successfully")
        assert 'create' in keywords
        
        keywords = extractor._extract_scenario_keywords("Test boundary conditions with min value")
        assert 'boundary' in keywords or 'min' in keywords
        
        storage.close()
    
    def test_find_common_keywords(self, tmp_path):
        """Test finding common keywords across scenarios"""
        storage = Storage(tmp_path / "test.db")
        extractor = PatternExtractor()
        
        scenarios = [
            "Create user successfully",
            "Create post successfully",
            "Create comment successfully"
        ]
        
        common = extractor._find_common_keywords(scenarios)
        assert 'create' in common
        
        storage.close()
    
    def test_analyze_data_structure(self, tmp_path):
        """Test analyzing data structure"""
        storage = Storage(tmp_path / "test.db")
        extractor = PatternExtractor()
        
        field_usage = {}
        data = {
            'name': 'John',
            'email': 'john@example.com',
            'address': {
                'street': '123 Main St',
                'city': 'New York'
            }
        }
        
        extractor._analyze_data_structure(data, field_usage, '')
        
        assert 'name' in field_usage
        assert 'email' in field_usage
        assert 'address.street' in field_usage
        assert 'address.city' in field_usage
        
        storage.close()
    
    def test_extract_edge_case_details(self, tmp_path):
        """Test extracting edge case details"""
        storage = Storage(tmp_path / "test.db")
        extractor = PatternExtractor()
        
        # Test boundary case
        request_body = {'min_value': 0, 'max_value': 1000}
        details = extractor._extract_edge_case_details(request_body, 'boundary')
        assert details is not None
        assert 'min_value' in details or 'max_value' in details
        
        # Test empty case
        request_body = {'name': '', 'email': None}
        details = extractor._extract_edge_case_details(request_body, 'empty')
        assert details is not None
        assert 'empty_fields' in details
        
        storage.close()
    
    def test_calculate_depth(self, tmp_path):
        """Test calculating data structure depth"""
        storage = Storage(tmp_path / "test.db")
        extractor = PatternExtractor()
        
        # Flat structure
        data = {'a': 1, 'b': 2}
        depth = extractor._calculate_depth(data)
        assert depth == 1
        
        # Nested structure
        data = {'a': {'b': {'c': 1}}}
        depth = extractor._calculate_depth(data)
        assert depth == 3
        
        # Empty structure
        data = {}
        depth = extractor._calculate_depth(data)
        assert depth == 0
        
        storage.close()
    
    def test_extract_patterns_stores_in_storage(self, tmp_path):
        """Test that extracted patterns are stored in storage"""
        storage = Storage(tmp_path / "test.db")
        
        # Create validated test cases
        for i in range(3):
            test_case_id = storage.ai_tests.save_test_case(
                'test.yaml', 'POST', '/users',
                {
                    'test_scenario': 'Create user',
                    'request_body': {'name': f'User {i}'}
                }
            )
            storage.ai_tests.update_validation_status(test_case_id, 'approved')
        
        extractor = PatternExtractor()
        result = extractor.extract_patterns_from_ai_tests(storage=storage)
        
        assert result['patterns_saved'] > 0
        
        # Verify patterns were stored
        stored_patterns = storage.patterns.get_patterns()
        assert len(stored_patterns) > 0
        
        # Check pattern types
        pattern_types = [p['pattern_type'] for p in stored_patterns]
        assert 'ai_test_scenario' in pattern_types or 'ai_data_quality' in pattern_types
        
        storage.close()
    
    def test_extract_patterns_filters_by_schema(self, tmp_path):
        """Test that pattern extraction can filter by schema file"""
        storage = Storage(tmp_path / "test.db")
        
        # Create test cases for different schemas
        test_case_1 = storage.ai_tests.save_test_case(
            'schema1.yaml', 'POST', '/users',
            {'test_scenario': 'Create user', 'request_body': {'name': 'User'}}
        )
        storage.ai_tests.update_validation_status(test_case_1, 'approved')
        
        test_case_2 = storage.ai_tests.save_test_case(
            'schema2.yaml', 'POST', '/posts',
            {'test_scenario': 'Create post', 'request_body': {'title': 'Post'}}
        )
        storage.ai_tests.update_validation_status(test_case_2, 'approved')
        
        extractor = PatternExtractor()
        
        # Extract patterns for schema1 only
        result1 = extractor.extract_patterns_from_ai_tests(schema_file='schema1.yaml', storage=storage)
        
        # Extract patterns for schema2 only
        result2 = extractor.extract_patterns_from_ai_tests(schema_file='schema2.yaml', storage=storage)
        
        # Both should have patterns
        assert result1['patterns_saved'] > 0
        assert result2['patterns_saved'] > 0
        
        storage.close()

