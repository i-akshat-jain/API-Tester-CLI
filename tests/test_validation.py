"""
Tests for validation interface
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile

from apitest.ai.validation import (
    ValidationUI, ValidationFeedback, ValidationStatus,
    VALIDATION_STATUS_PENDING, VALIDATION_STATUS_APPROVED,
    VALIDATION_STATUS_REJECTED, VALIDATION_STATUS_NEEDS_IMPROVEMENT
)


class TestValidationFeedback:
    """Test ValidationFeedback dataclass"""
    
    def test_validation_feedback_creation(self):
        """Test creating ValidationFeedback"""
        feedback = ValidationFeedback(
            test_case_id=1,
            status=VALIDATION_STATUS_APPROVED,
            feedback_text="Good test case",
            annotations={'note': 'test'},
            suggested_improvements=['Add more edge cases']
        )
        
        assert feedback.test_case_id == 1
        assert feedback.status == VALIDATION_STATUS_APPROVED
        assert feedback.feedback_text == "Good test case"
        assert feedback.annotations == {'note': 'test'}
        assert feedback.suggested_improvements == ['Add more edge cases']
    
    def test_validation_feedback_to_dict(self):
        """Test converting ValidationFeedback to dictionary"""
        feedback = ValidationFeedback(
            test_case_id=1,
            status=VALIDATION_STATUS_APPROVED,
            feedback_text="Good test"
        )
        
        data = feedback.to_dict()
        
        assert data['test_case_id'] == 1
        assert data['status'] == VALIDATION_STATUS_APPROVED
        assert data['feedback_text'] == "Good test"
        assert 'annotations' in data
        assert 'suggested_improvements' in data
    
    def test_validation_feedback_from_dict(self):
        """Test creating ValidationFeedback from dictionary"""
        data = {
            'test_case_id': 1,
            'status': VALIDATION_STATUS_REJECTED,
            'feedback_text': 'Bad test',
            'annotations': {'reason': 'invalid'},
            'suggested_improvements': ['Fix request body']
        }
        
        feedback = ValidationFeedback.from_dict(data)
        
        assert feedback.test_case_id == 1
        assert feedback.status == VALIDATION_STATUS_REJECTED
        assert feedback.feedback_text == 'Bad test'
        assert feedback.annotations == {'reason': 'invalid'}
        assert feedback.suggested_improvements == ['Fix request body']


class TestValidationUI:
    """Test ValidationUI class"""
    
    def test_init(self):
        """Test ValidationUI initialization"""
        storage = Mock()
        ui = ValidationUI(storage)
        
        assert ui.storage == storage
        assert ui.console is not None
    
    def test_get_test_cases_to_review_by_id(self):
        """Test getting test cases by ID"""
        storage = Mock()
        storage.ai_tests = Mock()
        storage.ai_tests.get_test_case = Mock(return_value={
            'id': 1,
            'method': 'POST',
            'path': '/api/test',
            'test_case_json': {}
        })
        
        ui = ValidationUI(storage)
        test_cases = ui._get_test_cases_to_review(
            test_results=None,
            test_case_ids=[1],
            schema_file=None
        )
        
        assert len(test_cases) == 1
        assert test_cases[0]['id'] == 1
        storage.ai_tests.get_test_case.assert_called_once_with(1)
    
    def test_get_test_cases_to_review_from_results(self):
        """Test getting test cases from test results"""
        storage = Mock()
        storage.ai_tests = Mock()
        storage.ai_tests.get_test_case = Mock(return_value={
            'id': 1,
            'method': 'POST',
            'path': '/api/test',
            'test_case_json': {}
        })
        
        ui = ValidationUI(storage)
        test_results = [
            {
                'is_ai_generated': True,
                'test_case_id': 1,
                'method': 'POST',
                'path': '/api/test'
            }
        ]
        
        test_cases = ui._get_test_cases_to_review(
            test_results=test_results,
            test_case_ids=None,
            schema_file=None
        )
        
        assert len(test_cases) == 1
        storage.ai_tests.get_test_case.assert_called_once_with(1)
    
    def test_get_test_cases_to_review_pending(self):
        """Test getting pending test cases"""
        storage = Mock()
        storage.ai_tests = Mock()
        storage.ai_tests.get_validated_test_cases = Mock(return_value=[
            {
                'id': 1,
                'validation_status': VALIDATION_STATUS_PENDING,
                'method': 'POST',
                'path': '/api/test'
            },
            {
                'id': 2,
                'validation_status': VALIDATION_STATUS_APPROVED,
                'method': 'GET',
                'path': '/api/test2'
            }
        ])
        
        ui = ValidationUI(storage)
        test_cases = ui._get_test_cases_to_review(
            test_results=None,
            test_case_ids=None,
            schema_file='test.yaml'
        )
        
        # Should only return pending ones
        assert len(test_cases) == 1
        assert test_cases[0]['id'] == 1
        assert test_cases[0]['validation_status'] == VALIDATION_STATUS_PENDING
    
    def test_export_to_json(self):
        """Test exporting test cases to JSON"""
        storage = Mock()
        ui = ValidationUI(storage)
        
        test_cases = [
            {
                'id': 1,
                'schema_file': 'test.yaml',
                'method': 'POST',
                'path': '/api/test',
                'test_case_json': {'test_scenario': 'Test'},
                'validation_status': 'pending',
                'created_at': '2024-01-01'
            }
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_path = Path(f.name)
        
        try:
            ui.export_to_json(test_cases, output_path)
            
            # Verify file was created and contains data
            assert output_path.exists()
            with open(output_path, 'r') as f:
                data = json.load(f)
            
            assert 'test_cases' in data
            assert len(data['test_cases']) == 1
            assert data['test_cases'][0]['id'] == 1
        finally:
            output_path.unlink()
    
    def test_import_from_json(self):
        """Test importing validation feedback from JSON"""
        storage = Mock()
        ui = ValidationUI(storage)
        
        feedback_data = {
            'validations': [
                {
                    'test_case_id': 1,
                    'status': VALIDATION_STATUS_APPROVED,
                    'feedback_text': 'Good test'
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(feedback_data, f)
            input_path = Path(f.name)
        
        try:
            feedback_list = ui.import_from_json(input_path)
            
            assert len(feedback_list) == 1
            assert feedback_list[0].test_case_id == 1
            assert feedback_list[0].status == VALIDATION_STATUS_APPROVED
        finally:
            input_path.unlink()
    
    def test_save_feedback(self):
        """Test saving validation feedback"""
        storage = Mock()
        storage.validation_feedback = Mock()
        storage.validation_feedback.save_validation = Mock(return_value=1)
        storage.ai_tests = Mock()
        storage.ai_tests.update_validation_status = Mock()
        
        ui = ValidationUI(storage)
        
        feedback_list = [
            ValidationFeedback(
                test_case_id=1,
                status=VALIDATION_STATUS_APPROVED,
                feedback_text="Good test"
            )
        ]
        
        ui.save_feedback(feedback_list)
        
        storage.validation_feedback.save_validation.assert_called_once()
        storage.ai_tests.update_validation_status.assert_called_once_with(1, VALIDATION_STATUS_APPROVED)
    
    @patch('apitest.ai.validation.Prompt')
    def test_review_single_test_case_approve(self, mock_prompt):
        """Test reviewing a single test case and approving"""
        storage = Mock()
        ui = ValidationUI(storage)
        
        mock_prompt.ask = Mock(return_value='a')  # Approve
        
        test_case = {
            'id': 1,
            'method': 'POST',
            'path': '/api/test',
            'test_case_json': {
                'test_scenario': 'Test scenario',
                'request_body': {'key': 'value'},
                'expected_response': {'status_code': 200}
            }
        }
        
        feedback = ui._review_single_test_case(test_case, 1, 1)
        
        assert feedback is not None
        assert feedback.test_case_id == 1
        assert feedback.status == VALIDATION_STATUS_APPROVED
    
    @patch('apitest.ai.validation.Prompt')
    def test_review_single_test_case_reject(self, mock_prompt):
        """Test reviewing a single test case and rejecting"""
        storage = Mock()
        ui = ValidationUI(storage)
        
        mock_prompt.ask = Mock(side_effect=['r', 'Bad test'])  # Reject with feedback
        
        test_case = {
            'id': 1,
            'method': 'POST',
            'path': '/api/test',
            'test_case_json': {
                'test_scenario': 'Test scenario'
            }
        }
        
        feedback = ui._review_single_test_case(test_case, 1, 1)
        
        assert feedback is not None
        assert feedback.status == VALIDATION_STATUS_REJECTED
        assert feedback.feedback_text == 'Bad test'
    
    @patch('apitest.ai.validation.Prompt')
    def test_review_single_test_case_skip(self, mock_prompt):
        """Test skipping a test case"""
        storage = Mock()
        ui = ValidationUI(storage)
        
        mock_prompt.ask = Mock(return_value='s')  # Skip
        
        test_case = {
            'id': 1,
            'method': 'POST',
            'path': '/api/test',
            'test_case_json': {}
        }
        
        feedback = ui._review_single_test_case(test_case, 1, 1)
        
        assert feedback is None
    
    @patch('apitest.ai.validation.Prompt')
    def test_review_single_test_case_needs_improvement(self, mock_prompt):
        """Test marking test case as needs improvement"""
        storage = Mock()
        ui = ValidationUI(storage)
        
        mock_prompt.ask = Mock(side_effect=['i', 'Add more validation', 'Improvement 1', ''])  # Needs improvement
        
        test_case = {
            'id': 1,
            'method': 'POST',
            'path': '/api/test',
            'test_case_json': {}
        }
        
        feedback = ui._review_single_test_case(test_case, 1, 1)
        
        assert feedback is not None
        assert feedback.status == VALIDATION_STATUS_NEEDS_IMPROVEMENT
        assert feedback.feedback_text == 'Add more validation'
        assert feedback.suggested_improvements == ['Improvement 1']

