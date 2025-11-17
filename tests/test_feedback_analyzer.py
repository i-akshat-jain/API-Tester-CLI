"""
Tests for feedback analyzer
"""

import pytest
import json
from unittest.mock import Mock, MagicMock
from pathlib import Path
import tempfile

from apitest.ai.feedback_analyzer import FeedbackAnalyzer
from apitest.storage.database import Storage


class TestFeedbackAnalyzer:
    """Test FeedbackAnalyzer class"""
    
    def test_init(self, tmp_path):
        """Test FeedbackAnalyzer initialization"""
        storage = Storage(tmp_path / "test.db")
        analyzer = FeedbackAnalyzer(storage)
        
        assert analyzer.storage == storage
        storage.close()
    
    def test_analyze_feedback_empty_corpus(self, tmp_path):
        """Test analyzing feedback with empty corpus"""
        storage = Storage(tmp_path / "test.db")
        analyzer = FeedbackAnalyzer(storage)
        
        result = analyzer.analyze_feedback(limit=100)
        
        assert result['success_rates'] == {}
        assert result['common_issues'] == []
        assert result['patterns'] == {}
        assert result['actionable_insights'] == []
        assert result['feedback_summary']['total'] == 0
        assert result['total_analyzed'] == 0
        
        storage.close()
    
    def test_analyze_feedback_with_data(self, tmp_path):
        """Test analyzing feedback with sample data"""
        storage = Storage(tmp_path / "test.db")
        
        # Create test cases with different prompt versions
        test_case_1 = storage.ai_tests.save_test_case(
            'test.yaml', 'POST', '/users',
            {
                'test_scenario': 'Create user',
                'request_body': {'name': 'Test'},
                'ai_metadata': {'prompt_version': 'v1', 'model': 'test'}
            }
        )
        
        test_case_2 = storage.ai_tests.save_test_case(
            'test.yaml', 'GET', '/users',
            {
                'test_scenario': 'Get users',
                'request_body': {},
                'ai_metadata': {'prompt_version': 'v1', 'model': 'test'}
            }
        )
        
        test_case_3 = storage.ai_tests.save_test_case(
            'test.yaml', 'POST', '/posts',
            {
                'test_scenario': 'Create post',
                'request_body': {'title': 'Test'},
                'ai_metadata': {'prompt_version': 'v2', 'model': 'test'}
            }
        )
        
        # Add feedback
        storage.validation_feedback.save_validation(test_case_1, 'approved', 'Good test')
        storage.validation_feedback.save_validation(test_case_2, 'rejected', 'Invalid format')
        storage.validation_feedback.save_validation(test_case_3, 'approved', 'Excellent')
        
        analyzer = FeedbackAnalyzer(storage)
        result = analyzer.analyze_feedback(limit=100)
        
        assert result['total_analyzed'] == 3
        assert 'success_rates' in result
        assert 'common_issues' in result
        assert 'patterns' in result
        assert 'actionable_insights' in result
        assert result['feedback_summary']['total'] == 3
        
        storage.close()
    
    def test_calculate_success_rates(self, tmp_path):
        """Test calculating success rates by prompt version"""
        storage = Storage(tmp_path / "test.db")
        
        # Create test cases with different prompt versions
        test_case_v1_1 = storage.ai_tests.save_test_case(
            'test.yaml', 'POST', '/users',
            {'ai_metadata': {'prompt_version': 'v1'}}
        )
        test_case_v1_2 = storage.ai_tests.save_test_case(
            'test.yaml', 'GET', '/users',
            {'ai_metadata': {'prompt_version': 'v1'}}
        )
        test_case_v2_1 = storage.ai_tests.save_test_case(
            'test.yaml', 'POST', '/posts',
            {'ai_metadata': {'prompt_version': 'v2'}}
        )
        
        # Add feedback: v1 has 1 approved, 1 rejected; v2 has 1 approved
        storage.validation_feedback.save_validation(test_case_v1_1, 'approved', 'Good')
        storage.validation_feedback.save_validation(test_case_v1_2, 'rejected', 'Bad')
        storage.validation_feedback.save_validation(test_case_v2_1, 'approved', 'Good')
        
        analyzer = FeedbackAnalyzer(storage)
        corpus = storage.validation_feedback.get_feedback_corpus(limit=100)
        success_rates = analyzer._calculate_success_rates(corpus)
        
        assert 'v1' in success_rates
        assert 'v2' in success_rates
        assert success_rates['v1']['total'] == 2
        assert success_rates['v1']['approved'] == 1
        assert success_rates['v1']['rejected'] == 1
        assert success_rates['v1']['approved_rate'] == 50.0
        assert success_rates['v2']['total'] == 1
        assert success_rates['v2']['approved'] == 1
        assert success_rates['v2']['approved_rate'] == 100.0
        
        storage.close()
    
    def test_extract_prompt_version(self, tmp_path):
        """Test extracting prompt version from feedback"""
        storage = Storage(tmp_path / "test.db")
        
        # Create test case with prompt version
        test_case_id = storage.ai_tests.save_test_case(
            'test.yaml', 'POST', '/users',
            {'ai_metadata': {'prompt_version': 'v1.5', 'model': 'test'}}
        )
        
        # Get feedback entry
        storage.validation_feedback.save_validation(test_case_id, 'approved', 'Good')
        corpus = storage.validation_feedback.get_feedback_corpus(limit=1)
        
        analyzer = FeedbackAnalyzer(storage)
        prompt_version = analyzer._extract_prompt_version(corpus[0])
        
        assert prompt_version == 'v1.5'
        
        storage.close()
    
    def test_extract_prompt_version_unknown(self, tmp_path):
        """Test extracting prompt version when not found"""
        storage = Storage(tmp_path / "test.db")
        
        # Create test case without prompt version
        test_case_id = storage.ai_tests.save_test_case(
            'test.yaml', 'POST', '/users',
            {'test_scenario': 'Test'}
        )
        
        storage.validation_feedback.save_validation(test_case_id, 'approved', 'Good')
        corpus = storage.validation_feedback.get_feedback_corpus(limit=1)
        
        analyzer = FeedbackAnalyzer(storage)
        prompt_version = analyzer._extract_prompt_version(corpus[0])
        
        assert prompt_version == 'unknown'
        
        storage.close()
    
    def test_identify_common_issues(self, tmp_path):
        """Test identifying common issues from feedback"""
        storage = Storage(tmp_path / "test.db")
        
        test_case_1 = storage.ai_tests.save_test_case('test.yaml', 'POST', '/users', {})
        test_case_2 = storage.ai_tests.save_test_case('test.yaml', 'GET', '/users', {})
        test_case_3 = storage.ai_tests.save_test_case('test.yaml', 'POST', '/posts', {})
        
        # Add feedback with common issues
        storage.validation_feedback.save_validation(
            test_case_1, 'rejected', 'Invalid format in request body'
        )
        storage.validation_feedback.save_validation(
            test_case_2, 'rejected', 'Missing required field in data'
        )
        storage.validation_feedback.save_validation(
            test_case_3, 'needs_improvement', 'Format issue with the structure'
        )
        
        analyzer = FeedbackAnalyzer(storage)
        corpus = storage.validation_feedback.get_feedback_corpus(limit=100)
        common_issues = analyzer._identify_common_issues(corpus)
        
        assert len(common_issues) > 0
        # Should identify 'format' and 'data' as common issues
        issue_types = [issue['issue_type'] for issue in common_issues]
        assert 'format' in issue_types or 'data' in issue_types
        
        storage.close()
    
    def test_extract_patterns(self, tmp_path):
        """Test extracting patterns from feedback"""
        storage = Storage(tmp_path / "test.db")
        
        test_case_1 = storage.ai_tests.save_test_case('test.yaml', 'POST', '/users', {})
        test_case_2 = storage.ai_tests.save_test_case('test.yaml', 'GET', '/users', {})
        test_case_3 = storage.ai_tests.save_test_case('test.yaml', 'POST', '/posts', {})
        
        storage.validation_feedback.save_validation(test_case_1, 'approved', 'Good')
        storage.validation_feedback.save_validation(test_case_2, 'rejected', 'Bad')
        storage.validation_feedback.save_validation(test_case_3, 'approved', 'Good')
        
        analyzer = FeedbackAnalyzer(storage)
        corpus = storage.validation_feedback.get_feedback_corpus(limit=100)
        patterns = analyzer._extract_patterns(corpus)
        
        assert 'by_status' in patterns
        assert 'by_endpoint' in patterns
        assert 'by_method' in patterns
        assert 'has_feedback_text' in patterns
        assert 'has_suggested_improvements' in patterns
        
        assert patterns['by_status']['approved'] == 2
        assert patterns['by_status']['rejected'] == 1
        
        # Check method patterns
        assert 'POST' in patterns['by_method']
        assert 'GET' in patterns['by_method']
        
        storage.close()
    
    def test_extract_actionable_insights(self, tmp_path):
        """Test extracting actionable insights"""
        storage = Storage(tmp_path / "test.db")
        
        # Create test cases with different prompt versions
        test_case_v1_1 = storage.ai_tests.save_test_case(
            'test.yaml', 'POST', '/users',
            {'ai_metadata': {'prompt_version': 'v1'}}
        )
        test_case_v1_2 = storage.ai_tests.save_test_case(
            'test.yaml', 'GET', '/users',
            {'ai_metadata': {'prompt_version': 'v1'}}
        )
        test_case_v2_1 = storage.ai_tests.save_test_case(
            'test.yaml', 'POST', '/posts',
            {'ai_metadata': {'prompt_version': 'v2'}}
        )
        
        # v1: 0 approved, 2 rejected (0% approval)
        # v2: 1 approved, 0 rejected (100% approval)
        storage.validation_feedback.save_validation(test_case_v1_1, 'rejected', 'Invalid format')
        storage.validation_feedback.save_validation(test_case_v1_2, 'rejected', 'Bad data')
        storage.validation_feedback.save_validation(test_case_v2_1, 'approved', 'Good')
        
        analyzer = FeedbackAnalyzer(storage)
        corpus = storage.validation_feedback.get_feedback_corpus(limit=100)
        success_rates = analyzer._calculate_success_rates(corpus)
        common_issues = analyzer._identify_common_issues(corpus)
        patterns = analyzer._extract_patterns(corpus)
        
        insights = analyzer._extract_actionable_insights(
            corpus, success_rates, common_issues, patterns
        )
        
        assert len(insights) > 0
        # Should have insight about prompt version performance
        insight_categories = [insight['category'] for insight in insights]
        assert 'prompt_version' in insight_categories or 'overall_performance' in insight_categories
        
        storage.close()
    
    def test_extract_actionable_insights_high_approval_rate(self, tmp_path):
        """Test insights when approval rate is high"""
        storage = Storage(tmp_path / "test.db")
        
        # Create test cases with high approval rate
        for i in range(5):
            test_case_id = storage.ai_tests.save_test_case(
                'test.yaml', 'POST', f'/users/{i}',
                {'ai_metadata': {'prompt_version': 'v1'}}
            )
            storage.validation_feedback.save_validation(test_case_id, 'approved', 'Good')
        
        analyzer = FeedbackAnalyzer(storage)
        corpus = storage.validation_feedback.get_feedback_corpus(limit=100)
        success_rates = analyzer._calculate_success_rates(corpus)
        common_issues = analyzer._identify_common_issues(corpus)
        patterns = analyzer._extract_patterns(corpus)
        
        insights = analyzer._extract_actionable_insights(
            corpus, success_rates, common_issues, patterns
        )
        
        # Should not have high-priority overall_performance insight (approval rate > 50%)
        high_priority_performance = [
            insight for insight in insights
            if insight['category'] == 'overall_performance' and insight['priority'] == 'high'
        ]
        assert len(high_priority_performance) == 0
        
        storage.close()
    
    def test_analyze_feedback_integration(self, tmp_path):
        """Test full integration of analyze_feedback"""
        storage = Storage(tmp_path / "test.db")
        
        # Create diverse test data
        test_cases = []
        for i in range(10):
            prompt_version = 'v1' if i < 5 else 'v2'
            method = 'POST' if i % 2 == 0 else 'GET'
            status = 'approved' if i < 7 else 'rejected'
            
            test_case_id = storage.ai_tests.save_test_case(
                'test.yaml', method, f'/endpoint/{i}',
                {'ai_metadata': {'prompt_version': prompt_version}}
            )
            test_cases.append(test_case_id)
            
            feedback_text = 'Good test' if status == 'approved' else 'Invalid format'
            storage.validation_feedback.save_validation(test_case_id, status, feedback_text)
        
        analyzer = FeedbackAnalyzer(storage)
        result = analyzer.analyze_feedback(limit=100)
        
        # Verify all components are present
        assert 'success_rates' in result
        assert 'common_issues' in result
        assert 'patterns' in result
        assert 'actionable_insights' in result
        assert 'feedback_summary' in result
        assert 'total_analyzed' in result
        
        # Verify success rates
        assert 'v1' in result['success_rates']
        assert 'v2' in result['success_rates']
        
        # Verify patterns
        assert result['patterns']['by_status']['approved'] == 7
        assert result['patterns']['by_status']['rejected'] == 3
        
        # Verify insights exist
        assert len(result['actionable_insights']) > 0
        
        storage.close()

