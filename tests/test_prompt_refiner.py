"""
Tests for prompt refiner
"""

import pytest
import json
from unittest.mock import Mock, patch
from pathlib import Path
import tempfile

from apitest.ai.prompt_refiner import PromptRefiner, PromptUpdate
from apitest.storage.database import Storage
from apitest.ai.prompt_builder import PromptBuilder


class TestPromptRefiner:
    """Test PromptRefiner class"""
    
    def test_init(self, tmp_path):
        """Test PromptRefiner initialization"""
        storage = Storage(tmp_path / "test.db")
        refiner = PromptRefiner(storage)
        
        assert refiner.storage == storage
        storage.close()
    
    def test_refine_prompts_no_issues(self, tmp_path):
        """Test refining prompts with no issues"""
        storage = Storage(tmp_path / "test.db")
        
        # Initialize default prompts
        PromptBuilder(storage)
        from apitest.ai.prompt_builder import initialize_default_prompts
        initialize_default_prompts(storage)
        
        refiner = PromptRefiner(storage)
        
        # Empty feedback analysis (no issues)
        feedback_analysis = {
            'success_rates': {},
            'common_issues': [],
            'actionable_insights': [],
            'patterns': {},
            'feedback_summary': {'total': 0}
        }
        
        updates = refiner.refine_prompts(feedback_analysis)
        
        assert len(updates) == 0
        
        storage.close()
    
    def test_refine_prompts_with_issues(self, tmp_path):
        """Test refining prompts with identified issues"""
        storage = Storage(tmp_path / "test.db")
        
        # Initialize default prompts
        from apitest.ai.prompt_builder import initialize_default_prompts
        initialize_default_prompts(storage)
        
        refiner = PromptRefiner(storage)
        
        # Feedback analysis with issues
        feedback_analysis = {
            'success_rates': {},
            'common_issues': [
                {
                    'issue_type': 'format',
                    'count': 10,
                    'percentage': 50.0,
                    'examples': ['Invalid format']
                }
            ],
            'actionable_insights': [
                {
                    'priority': 'high',
                    'category': 'common_issue',
                    'insight': 'Format issues',
                    'recommendation': 'Add format instructions',
                    'data': {'issue_type': 'format', 'percentage': 50.0}
                }
            ],
            'patterns': {},
            'feedback_summary': {'total': 20}
        }
        
        updates = refiner.refine_prompts(feedback_analysis)
        
        assert len(updates) > 0
        assert any(update.prompt_name == 'test_generation_basic' for update in updates)
        
        storage.close()
    
    def test_identify_prompt_issues(self, tmp_path):
        """Test identifying prompt issues from feedback"""
        storage = Storage(tmp_path / "test.db")
        refiner = PromptRefiner(storage)
        
        feedback_analysis = {
            'common_issues': [
                {
                    'issue_type': 'format',
                    'percentage': 40.0
                },
                {
                    'issue_type': 'missing',
                    'percentage': 25.0
                }
            ],
            'actionable_insights': [
                {
                    'priority': 'high',
                    'category': 'overall_performance',
                    'data': {'approval_rate': 45.0}
                }
            ]
        }
        
        issues = refiner._identify_prompt_issues(feedback_analysis)
        
        assert len(issues) > 0
        assert 'test_generation_basic' in issues
        assert len(issues['test_generation_basic']) > 0
        
        storage.close()
    
    def test_generate_improvements(self, tmp_path):
        """Test generating improvements from issues"""
        storage = Storage(tmp_path / "test.db")
        refiner = PromptRefiner(storage)
        
        issues = [
            "Address format issues in test generation",
            "High occurrence of missing issues (40%) - add clearer instructions"
        ]
        
        feedback_analysis = {
            'actionable_insights': []
        }
        
        improvements = refiner._generate_improvements(issues, feedback_analysis)
        
        assert len(improvements) > 0
        assert any('format' in imp.lower() for imp in improvements)
        assert any('required' in imp.lower() or 'missing' in imp.lower() for imp in improvements)
        
        storage.close()
    
    def test_apply_improvements(self, tmp_path):
        """Test applying improvements to template"""
        storage = Storage(tmp_path / "test.db")
        refiner = PromptRefiner(storage)
        
        template = """## Instructions
Generate test cases.
"""
        
        improvements = [
            "Add format instructions",
            "Emphasize required fields"
        ]
        
        issues = [
            "Address format issues",
            "Missing required fields"
        ]
        
        improved = refiner._apply_improvements(template, improvements, issues)
        
        assert len(improved) > len(template)
        assert "IMPROVEMENTS" in improved or "format" in improved.lower()
        
        storage.close()
    
    def test_refine_single_prompt(self, tmp_path):
        """Test refining a single prompt"""
        storage = Storage(tmp_path / "test.db")
        
        # Initialize default prompts
        from apitest.ai.prompt_builder import initialize_default_prompts
        initialize_default_prompts(storage)
        
        refiner = PromptRefiner(storage)
        
        issues = ["Address format issues"]
        feedback_analysis = {
            'actionable_insights': []
        }
        
        update = refiner._refine_single_prompt(
            'test_generation_basic',
            issues,
            feedback_analysis
        )
        
        assert update is not None
        assert update.prompt_name == 'test_generation_basic'
        assert update.new_version == 2  # Should be version 2
        assert len(update.improved_template) > 0
        assert len(update.improvements) > 0
        assert len(update.issues_addressed) > 0
        
        storage.close()
    
    def test_save_refined_prompt(self, tmp_path):
        """Test saving refined prompt"""
        storage = Storage(tmp_path / "test.db")
        
        # Initialize default prompts
        from apitest.ai.prompt_builder import initialize_default_prompts
        initialize_default_prompts(storage)
        
        refiner = PromptRefiner(storage)
        
        # Create a prompt update
        update = PromptUpdate(
            prompt_name='test_generation_basic',
            new_version=2,
            improved_template="Improved template",
            improvements=["Added format instructions"],
            issues_addressed=["Format issues"],
            metadata={'refined_from_version': 1}
        )
        
        prompt_id = refiner.save_refined_prompt(update, set_active=False)
        
        assert prompt_id > 0
        
        # Verify prompt was saved
        saved_prompt = storage.ai_prompts.get_prompt('test_generation_basic', 2)
        assert saved_prompt is not None
        assert saved_prompt['prompt_template'] == "Improved template"
        
        storage.close()
    
    def test_save_refined_prompt_set_active(self, tmp_path):
        """Test saving refined prompt and setting as active"""
        storage = Storage(tmp_path / "test.db")
        
        # Initialize default prompts
        from apitest.ai.prompt_builder import initialize_default_prompts
        initialize_default_prompts(storage)
        
        refiner = PromptRefiner(storage)
        
        update = PromptUpdate(
            prompt_name='test_generation_basic',
            new_version=2,
            improved_template="Improved template",
            improvements=["Added format instructions"],
            issues_addressed=["Format issues"],
            metadata={'refined_from_version': 1}
        )
        
        prompt_id = refiner.save_refined_prompt(update, set_active=True)
        
        assert prompt_id > 0
        
        # Verify prompt is active
        active_prompt = storage.ai_prompts.get_active_prompt('test_generation_basic')
        assert active_prompt is not None
        assert active_prompt['prompt_version'] == 2
        
        storage.close()
    
    def test_compare_prompt_versions(self, tmp_path):
        """Test comparing prompt versions"""
        storage = Storage(tmp_path / "test.db")
        
        # Initialize default prompts
        from apitest.ai.prompt_builder import initialize_default_prompts
        initialize_default_prompts(storage)
        
        # Create a second version
        storage.ai_prompts.save_prompt(
            'test_generation_basic',
            'Updated template',
            metadata={'description': 'Updated version'},
            version=2
        )
        
        refiner = PromptRefiner(storage)
        
        comparison = refiner.compare_prompt_versions('test_generation_basic', 1, 2)
        
        assert 'version1' in comparison
        assert 'version2' in comparison
        assert comparison['version1']['version'] == 1
        assert comparison['version2']['version'] == 2
        assert 'differences' in comparison
        
        storage.close()
    
    def test_refine_prompts_integration(self, tmp_path):
        """Test full integration of prompt refinement"""
        storage = Storage(tmp_path / "test.db")
        
        # Initialize default prompts
        from apitest.ai.prompt_builder import initialize_default_prompts
        initialize_default_prompts(storage)
        
        # Create some feedback data
        test_case_id = storage.ai_tests.save_test_case(
            'test.yaml', 'POST', '/users',
            {'test_scenario': 'Test', 'request_body': {}}
        )
        storage.validation_feedback.save_validation(
            test_case_id, 'rejected', 'Invalid format in request body'
        )
        
        # Analyze feedback
        from apitest.ai.feedback_analyzer import FeedbackAnalyzer
        analyzer = FeedbackAnalyzer(storage)
        feedback_analysis = analyzer.analyze_feedback(limit=100)
        
        # Refine prompts
        refiner = PromptRefiner(storage)
        updates = refiner.refine_prompts(feedback_analysis)
        
        # Should generate updates if there are issues
        if updates:
            # Save one update
            update = updates[0]
            prompt_id = refiner.save_refined_prompt(update, set_active=False)
            assert prompt_id > 0
            
            # Verify version was created
            versions = storage.ai_prompts.list_prompt_versions(update.prompt_name)
            assert len(versions) >= 2
        
        storage.close()

