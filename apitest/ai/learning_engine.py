"""
Learning engine for orchestrating the AI test generation learning loop

Coordinates feedback analysis, pattern extraction, prompt refinement, and
test case library management to continuously improve AI test generation.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from apitest.ai.feedback_analyzer import FeedbackAnalyzer
from apitest.ai.prompt_refiner import PromptRefiner
from apitest.learning.pattern_extractor import PatternExtractor
from apitest.storage.test_case_library import save_test_case_to_library

logger = logging.getLogger(__name__)

# Minimum feedback required to run a learning cycle
MIN_FEEDBACK_FOR_LEARNING = 10


class LearningEngine:
    """
    Orchestrates the learning loop for AI test generation
    
    Coordinates:
    - Feedback analysis
    - Pattern extraction from validated tests
    - Prompt refinement
    - Test case library management
    """
    
    def __init__(self, storage: Any):
        """
        Initialize learning engine
        
        Args:
            storage: Storage instance with all namespaces
        """
        self.storage = storage
        self.feedback_analyzer = FeedbackAnalyzer(storage)
        self.prompt_refiner = PromptRefiner(storage)
        self.pattern_extractor = PatternExtractor()
    
    def run_learning_cycle(self, force: bool = False, 
                          schema_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Run a complete learning cycle
        
        Args:
            force: If True, run even if minimum feedback threshold not met
            schema_file: Optional schema file to focus learning on
            
        Returns:
            Dictionary with learning cycle results:
            {
                'feedback_analyzed': int,
                'patterns_extracted': int,
                'prompts_refined': int,
                'test_cases_saved': int,
                'success': bool,
                'message': str
            }
        """
        logger.info("Starting learning cycle" + (f" for {schema_file}" if schema_file else ""))
        
        # Check if we should run
        if not force and not self._should_run_learning_cycle():
            return {
                'feedback_analyzed': 0,
                'patterns_extracted': 0,
                'prompts_refined': 0,
                'test_cases_saved': 0,
                'success': False,
                'message': f'Not enough feedback to run learning cycle. Need at least {MIN_FEEDBACK_FOR_LEARNING} feedback entries.'
            }
        
        results = {
            'feedback_analyzed': 0,
            'patterns_extracted': 0,
            'prompts_refined': 0,
            'test_cases_saved': 0,
            'success': True,
            'message': 'Learning cycle completed successfully'
        }
        
        try:
            # Step 1: Analyze feedback
            logger.info("Step 1: Analyzing feedback...")
            feedback_analysis = self.feedback_analyzer.analyze_feedback(limit=1000)
            results['feedback_analyzed'] = feedback_analysis.get('total_analyzed', 0)
            
            if results['feedback_analyzed'] == 0:
                logger.warning("No feedback to analyze, skipping learning cycle")
                results['success'] = False
                results['message'] = 'No feedback found to analyze'
                return results
            
            logger.info(f"Analyzed {results['feedback_analyzed']} feedback entries")
            
            # Step 2: Extract patterns from validated AI tests
            logger.info("Step 2: Extracting patterns from validated tests...")
            pattern_results = self.pattern_extractor.extract_patterns_from_ai_tests(
                schema_file=schema_file,
                storage=self.storage
            )
            results['patterns_extracted'] = pattern_results.get('patterns_saved', 0)
            logger.info(f"Extracted and saved {results['patterns_extracted']} patterns")
            
            # Step 3: Refine prompts based on feedback
            logger.info("Step 3: Refining prompts...")
            prompt_updates = self.prompt_refiner.refine_prompts(feedback_analysis)
            results['prompts_refined'] = len(prompt_updates)
            
            if prompt_updates:
                logger.info(f"Generated {len(prompt_updates)} prompt refinements")
                
                # Save refined prompts (but don't activate them yet for A/B testing)
                for update in prompt_updates:
                    try:
                        self.prompt_refiner.save_refined_prompt(update, set_active=False)
                        logger.info(f"Saved refined prompt '{update.prompt_name}' v{update.new_version}")
                    except Exception as e:
                        logger.error(f"Error saving refined prompt '{update.prompt_name}': {e}")
            else:
                logger.info("No prompt refinements needed")
            
            # Step 4: Save good tests to test case library
            logger.info("Step 4: Saving approved tests to library...")
            test_cases_saved = self._save_approved_tests_to_library(schema_file=schema_file)
            results['test_cases_saved'] = test_cases_saved
            logger.info(f"Saved {test_cases_saved} approved test cases to library")
            
            logger.info("Learning cycle completed successfully")
            results['message'] = (
                f"Learning cycle completed: {results['feedback_analyzed']} feedback analyzed, "
                f"{results['patterns_extracted']} patterns extracted, "
                f"{results['prompts_refined']} prompts refined, "
                f"{results['test_cases_saved']} test cases saved to library"
            )
            
        except Exception as e:
            logger.error(f"Error during learning cycle: {e}", exc_info=True)
            results['success'] = False
            results['message'] = f'Error during learning cycle: {str(e)}'
        
        return results
    
    def _should_run_learning_cycle(self) -> bool:
        """
        Check if there's enough feedback to run a learning cycle
        
        Returns:
            True if enough feedback exists, False otherwise
        """
        feedback_stats = self.storage.validation_feedback.get_feedback_stats()
        total_feedback = feedback_stats.get('total', 0)
        
        return total_feedback >= MIN_FEEDBACK_FOR_LEARNING
    
    def _save_approved_tests_to_library(self, schema_file: Optional[str] = None) -> int:
        """
        Save approved test cases to the test case library
        
        Args:
            schema_file: Optional schema file to filter by
            
        Returns:
            Number of test cases saved
        """
        # Get all approved test cases
        approved_tests = self.storage.ai_tests.get_validated_test_cases(
            schema_file=schema_file,
            limit=1000
        )
        
        if not approved_tests:
            logger.debug("No approved test cases to save to library")
            return 0
        
        saved_count = 0
        
        for test_case in approved_tests:
            try:
                # Check if already saved to library (by checking if we have a record)
                # For now, we'll save all approved tests
                # In the future, we could track which ones are already saved
                
                # Prepare test case data for library
                library_test_case = {
                    'id': test_case.get('id'),
                    'schema_file': test_case.get('schema_file'),
                    'method': test_case.get('method'),
                    'path': test_case.get('path'),
                    'test_case_json': test_case.get('test_case_json'),
                    'validation_status': test_case.get('validation_status'),
                    'created_at': test_case.get('created_at'),
                    'version': test_case.get('version', 1)
                }
                
                # Save to library
                save_test_case_to_library(library_test_case)
                saved_count += 1
                
            except Exception as e:
                logger.warning(f"Error saving test case {test_case.get('id')} to library: {e}")
                continue
        
        return saved_count
    
    def get_learning_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the learning system
        
        Returns:
            Dictionary with learning statistics
        """
        feedback_stats = self.storage.validation_feedback.get_feedback_stats()
        pattern_count = len(self.storage.patterns.get_patterns())
        
        # Count prompt versions
        prompt_names = ['test_generation_basic', 'test_generation_advanced', 'test_generation_edge_cases']
        prompt_versions = {}
        for prompt_name in prompt_names:
            versions = self.storage.ai_prompts.list_prompt_versions(prompt_name)
            prompt_versions[prompt_name] = len(versions)
        
        # Count test cases in library
        from apitest.storage.test_case_library import list_test_cases_in_library
        library_test_count = len(list_test_cases_in_library())
        
        return {
            'total_feedback': feedback_stats.get('total', 0),
            'feedback_by_status': feedback_stats.get('by_status', {}),
            'patterns_stored': pattern_count,
            'prompt_versions': prompt_versions,
            'test_cases_in_library': library_test_count,
            'can_run_learning_cycle': self._should_run_learning_cycle()
        }

