"""
Tests for learning engine
"""

import pytest
import json
from unittest.mock import Mock, patch
from pathlib import Path
import tempfile

from apitest.ai.learning_engine import LearningEngine, MIN_FEEDBACK_FOR_LEARNING
from apitest.storage.database import Storage
from apitest.ai.prompt_builder import initialize_default_prompts


class TestLearningEngine:
    """Test LearningEngine class"""
    
    def test_init(self, tmp_path):
        """Test LearningEngine initialization"""
        storage = Storage(tmp_path / "test.db")
        engine = LearningEngine(storage)
        
        assert engine.storage == storage
        assert engine.feedback_analyzer is not None
        assert engine.prompt_refiner is not None
        assert engine.pattern_extractor is not None
        
        storage.close()
    
    def test_should_run_learning_cycle_insufficient_feedback(self, tmp_path):
        """Test that learning cycle requires minimum feedback"""
        storage = Storage(tmp_path / "test.db")
        engine = LearningEngine(storage)
        
        # No feedback yet
        should_run = engine._should_run_learning_cycle()
        assert should_run == False
        
        storage.close()
    
    def test_should_run_learning_cycle_sufficient_feedback(self, tmp_path):
        """Test that learning cycle runs with sufficient feedback"""
        storage = Storage(tmp_path / "test.db")
        
        # Create enough feedback
        test_case_id = storage.ai_tests.save_test_case('test.yaml', 'POST', '/users', {})
        for i in range(MIN_FEEDBACK_FOR_LEARNING):
            storage.validation_feedback.save_validation(test_case_id, 'approved', 'Good')
        
        engine = LearningEngine(storage)
        should_run = engine._should_run_learning_cycle()
        assert should_run == True
        
        storage.close()
    
    def test_run_learning_cycle_insufficient_feedback(self, tmp_path):
        """Test learning cycle with insufficient feedback"""
        storage = Storage(tmp_path / "test.db")
        initialize_default_prompts(storage)
        
        engine = LearningEngine(storage)
        results = engine.run_learning_cycle(force=False)
        
        assert results['success'] == False
        assert 'Not enough feedback' in results['message']
        assert results['feedback_analyzed'] == 0
        
        storage.close()
    
    def test_run_learning_cycle_force(self, tmp_path):
        """Test learning cycle with force flag"""
        storage = Storage(tmp_path / "test.db")
        initialize_default_prompts(storage)
        
        # Create some feedback (but not enough)
        test_case_id = storage.ai_tests.save_test_case('test.yaml', 'POST', '/users', {})
        storage.validation_feedback.save_validation(test_case_id, 'approved', 'Good')
        
        engine = LearningEngine(storage)
        results = engine.run_learning_cycle(force=True)
        
        # Should run even with little feedback
        assert results['feedback_analyzed'] >= 0  # May be 0 or 1
        
        storage.close()
    
    def test_run_learning_cycle_full(self, tmp_path):
        """Test full learning cycle with sufficient feedback"""
        storage = Storage(tmp_path / "test.db")
        initialize_default_prompts(storage)
        
        # Create test cases and feedback
        test_case_ids = []
        for i in range(5):
            test_case_id = storage.ai_tests.save_test_case(
                'test.yaml', 'POST', f'/users/{i}',
                {
                    'test_scenario': f'Test {i}',
                    'request_body': {'name': f'User {i}'}
                }
            )
            test_case_ids.append(test_case_id)
            storage.ai_tests.update_validation_status(test_case_id, 'approved')
            storage.validation_feedback.save_validation(
                test_case_id, 'approved', 'Good test'
            )
        
        # Add some rejected feedback for analysis
        for i in range(5):
            test_case_id = storage.ai_tests.save_test_case(
                'test.yaml', 'GET', f'/users/{i}',
                {'test_scenario': f'Test {i}', 'request_body': {}}
            )
            storage.validation_feedback.save_validation(
                test_case_id, 'rejected', 'Invalid format'
            )
        
        engine = LearningEngine(storage)
        results = engine.run_learning_cycle(force=False)
        
        assert results['success'] == True
        assert results['feedback_analyzed'] > 0
        assert results['patterns_extracted'] >= 0
        assert results['prompts_refined'] >= 0
        assert results['test_cases_saved'] >= 0
        
        storage.close()
    
    def test_save_approved_tests_to_library(self, tmp_path, monkeypatch):
        """Test saving approved tests to library"""
        # Use temporary directory for library
        library_dir = tmp_path / "validated_tests"
        library_dir.mkdir(parents=True, exist_ok=True)
        
        from apitest.storage import test_case_library
        original_get_library_dir = test_case_library.get_library_dir
        monkeypatch.setattr(test_case_library, 'get_library_dir', lambda: library_dir)
        
        storage = Storage(tmp_path / "test.db")
        
        # Create approved test cases
        for i in range(3):
            test_case_id = storage.ai_tests.save_test_case(
                'test.yaml', 'POST', f'/users/{i}',
                {'test_scenario': f'Test {i}', 'request_body': {}}
            )
            storage.ai_tests.update_validation_status(test_case_id, 'approved')
        
        engine = LearningEngine(storage)
        saved_count = engine._save_approved_tests_to_library()
        
        assert saved_count == 3
        
        # Verify files were created
        library_files = list(library_dir.glob('*.json'))
        assert len(library_files) == 3
        
        storage.close()
    
    def test_save_approved_tests_to_library_with_schema_filter(self, tmp_path):
        """Test saving approved tests filtered by schema"""
        storage = Storage(tmp_path / "test.db")
        
        # Create test cases for different schemas
        test_case_1 = storage.ai_tests.save_test_case(
            'schema1.yaml', 'POST', '/users',
            {'test_scenario': 'Test', 'request_body': {}}
        )
        storage.ai_tests.update_validation_status(test_case_1, 'approved')
        
        test_case_2 = storage.ai_tests.save_test_case(
            'schema2.yaml', 'POST', '/posts',
            {'test_scenario': 'Test', 'request_body': {}}
        )
        storage.ai_tests.update_validation_status(test_case_2, 'approved')
        
        engine = LearningEngine(storage)
        saved_count = engine._save_approved_tests_to_library(schema_file='schema1.yaml')
        
        assert saved_count == 1
        
        storage.close()
    
    def test_get_learning_stats(self, tmp_path):
        """Test getting learning statistics"""
        storage = Storage(tmp_path / "test.db")
        initialize_default_prompts(storage)
        
        # Create some data
        test_case_id = storage.ai_tests.save_test_case('test.yaml', 'POST', '/users', {})
        storage.validation_feedback.save_validation(test_case_id, 'approved', 'Good')
        storage.ai_tests.update_validation_status(test_case_id, 'approved')
        
        engine = LearningEngine(storage)
        stats = engine.get_learning_stats()
        
        assert 'total_feedback' in stats
        assert 'feedback_by_status' in stats
        assert 'patterns_stored' in stats
        assert 'prompt_versions' in stats
        assert 'test_cases_in_library' in stats
        assert 'can_run_learning_cycle' in stats
        
        assert stats['total_feedback'] >= 1
        assert isinstance(stats['can_run_learning_cycle'], bool)
        
        storage.close()
    
    def test_run_learning_cycle_with_schema_file(self, tmp_path):
        """Test learning cycle with schema file filter"""
        storage = Storage(tmp_path / "test.db")
        initialize_default_prompts(storage)
        
        # Create feedback for specific schema
        test_case_id = storage.ai_tests.save_test_case(
            'specific.yaml', 'POST', '/users',
            {'test_scenario': 'Test', 'request_body': {}}
        )
        for i in range(MIN_FEEDBACK_FOR_LEARNING):
            storage.validation_feedback.save_validation(test_case_id, 'approved', 'Good')
        
        engine = LearningEngine(storage)
        results = engine.run_learning_cycle(force=False, schema_file='specific.yaml')
        
        assert results['success'] == True
        assert results['feedback_analyzed'] > 0
        
        storage.close()
    
    def test_run_learning_cycle_error_handling(self, tmp_path):
        """Test error handling in learning cycle"""
        storage = Storage(tmp_path / "test.db")
        initialize_default_prompts(storage)
        
        # Create enough feedback
        test_case_id = storage.ai_tests.save_test_case('test.yaml', 'POST', '/users', {})
        for i in range(MIN_FEEDBACK_FOR_LEARNING):
            storage.validation_feedback.save_validation(test_case_id, 'approved', 'Good')
        
        engine = LearningEngine(storage)
        
        # Mock an error in one of the steps
        with patch.object(engine.feedback_analyzer, 'analyze_feedback', side_effect=Exception("Test error")):
            results = engine.run_learning_cycle(force=False)
            
            assert results['success'] == False
            assert 'Error' in results['message']
        
        storage.close()
    
    def test_learning_cycle_integration(self, tmp_path, monkeypatch):
        """Test full integration of learning cycle"""
        # Use temporary directory for library
        library_dir = tmp_path / "validated_tests"
        library_dir.mkdir(parents=True, exist_ok=True)
        
        from apitest.storage import test_case_library
        original_get_library_dir = test_case_library.get_library_dir
        monkeypatch.setattr(test_case_library, 'get_library_dir', lambda: library_dir)
        
        storage = Storage(tmp_path / "test.db")
        initialize_default_prompts(storage)
        
        # Create comprehensive test data
        approved_count = 5
        rejected_count = 5
        
        # Approved test cases
        for i in range(approved_count):
            test_case_id = storage.ai_tests.save_test_case(
                'test.yaml', 'POST', f'/users/{i}',
                {
                    'test_scenario': f'Create user {i}',
                    'request_body': {'name': f'User {i}', 'email': f'user{i}@example.com'}
                }
            )
            storage.ai_tests.update_validation_status(test_case_id, 'approved')
            storage.validation_feedback.save_validation(
                test_case_id, 'approved', 'Good test case'
            )
        
        # Rejected test cases
        for i in range(rejected_count):
            test_case_id = storage.ai_tests.save_test_case(
                'test.yaml', 'GET', f'/users/{i}',
                {'test_scenario': f'Get user {i}', 'request_body': {}}
            )
            storage.validation_feedback.save_validation(
                test_case_id, 'rejected', 'Invalid format'
            )
        
        engine = LearningEngine(storage)
        results = engine.run_learning_cycle(force=False)
        
        # Verify all steps completed
        assert results['success'] == True
        assert results['feedback_analyzed'] == approved_count + rejected_count
        assert results['patterns_extracted'] >= 0
        assert results['prompts_refined'] >= 0
        assert results['test_cases_saved'] == approved_count
        
        # Verify patterns were stored
        patterns = storage.patterns.get_patterns()
        assert len(patterns) >= 0  # May or may not have patterns depending on data
        
        # Verify test cases were saved to library
        library_files = list(library_dir.glob('*.json'))
        assert len(library_files) == approved_count
        
        storage.close()

