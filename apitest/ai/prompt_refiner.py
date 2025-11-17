"""
Prompt refiner for AI test generation

Analyzes feedback to identify prompt issues and generates improved prompt templates.
Supports version control and A/B testing of prompt versions.
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class PromptUpdate:
    """Represents a prompt update/improvement"""
    prompt_name: str
    new_version: int
    improved_template: str
    improvements: List[str]
    issues_addressed: List[str]
    metadata: Dict[str, Any]


class PromptRefiner:
    """
    Refines prompt templates based on feedback analysis
    
    Analyzes feedback to identify prompt issues, generates improvements,
    and creates new prompt versions for A/B testing.
    """
    
    def __init__(self, storage: Any):
        """
        Initialize prompt refiner
        
        Args:
            storage: Storage instance with ai_prompts and validation_feedback namespaces
        """
        self.storage = storage
    
    def refine_prompts(self, feedback_analysis: Dict[str, Any]) -> List[PromptUpdate]:
        """
        Refine prompts based on feedback analysis
        
        Args:
            feedback_analysis: Dictionary from FeedbackAnalyzer.analyze_feedback()
                containing success_rates, common_issues, actionable_insights, etc.
            
        Returns:
            List of PromptUpdate objects with improved prompt templates
        """
        logger.info("Starting prompt refinement based on feedback analysis")
        
        # Identify prompt issues from feedback
        prompt_issues = self._identify_prompt_issues(feedback_analysis)
        
        if not prompt_issues:
            logger.info("No prompt issues identified, no refinements needed")
            return []
        
        # Generate improvements for each prompt
        prompt_updates = []
        
        for prompt_name, issues in prompt_issues.items():
            try:
                update = self._refine_single_prompt(prompt_name, issues, feedback_analysis)
                if update:
                    prompt_updates.append(update)
            except Exception as e:
                logger.error(f"Error refining prompt '{prompt_name}': {e}")
        
        logger.info(f"Generated {len(prompt_updates)} prompt refinements")
        return prompt_updates
    
    def _identify_prompt_issues(self, feedback_analysis: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Identify prompt issues from feedback analysis
        
        Args:
            feedback_analysis: Feedback analysis dictionary
            
        Returns:
            Dictionary mapping prompt names to lists of issues
        """
        prompt_issues = defaultdict(list)
        
        # Analyze actionable insights
        insights = feedback_analysis.get('actionable_insights', [])
        for insight in insights:
            if insight['category'] == 'common_issue':
                # Common issues suggest prompt improvements needed
                issue_type = insight.get('data', {}).get('issue_type', '')
                if issue_type:
                    # Map issue types to prompt names
                    # For now, apply to all prompts, but could be more specific
                    for prompt_name in ['test_generation_basic', 'test_generation_advanced']:
                        prompt_issues[prompt_name].append(f"Address {issue_type} issues in test generation")
            
            elif insight['category'] == 'overall_performance':
                # Low approval rate suggests prompt quality issues
                approval_rate = insight.get('data', {}).get('approval_rate', 100)
                if approval_rate < 50:
                    for prompt_name in ['test_generation_basic', 'test_generation_advanced']:
                        prompt_issues[prompt_name].append(
                            f"Low approval rate ({approval_rate}%) - improve prompt clarity and examples"
                        )
            
            elif insight['category'] == 'method_pattern':
                # Method-specific issues
                method = insight.get('data', {}).get('method', '')
                if method:
                    for prompt_name in ['test_generation_basic', 'test_generation_advanced']:
                        prompt_issues[prompt_name].append(
                            f"Improve test generation for {method} requests"
                        )
        
        # Analyze common issues
        common_issues = feedback_analysis.get('common_issues', [])
        for issue in common_issues:
            issue_type = issue.get('issue_type', '')
            percentage = issue.get('percentage', 0)
            
            if percentage > 30:  # If >30% of problematic feedback has this issue
                for prompt_name in ['test_generation_basic', 'test_generation_advanced']:
                    prompt_issues[prompt_name].append(
                        f"High occurrence of {issue_type} issues ({percentage}%) - add clearer instructions"
                    )
        
        return dict(prompt_issues)
    
    def _refine_single_prompt(self, prompt_name: str, issues: List[str],
                              feedback_analysis: Dict[str, Any]) -> Optional[PromptUpdate]:
        """
        Refine a single prompt based on identified issues
        
        Args:
            prompt_name: Name of prompt to refine
            issues: List of issues to address
            feedback_analysis: Full feedback analysis
            
        Returns:
            PromptUpdate object or None if no improvements needed
        """
        # Get current prompt
        current_prompt = self.storage.ai_prompts.get_active_prompt(prompt_name)
        if not current_prompt:
            # Try latest version
            current_prompt = self.storage.ai_prompts.get_latest_prompt(prompt_name)
        
        if not current_prompt:
            logger.warning(f"Prompt '{prompt_name}' not found, skipping refinement")
            return None
        
        current_template = current_prompt.get('prompt_template', '')
        current_version = current_prompt.get('prompt_version', 1)
        
        # Generate improvements
        improvements = self._generate_improvements(issues, feedback_analysis)
        
        if not improvements:
            logger.debug(f"No improvements generated for prompt '{prompt_name}'")
            return None
        
        # Apply improvements to template
        improved_template = self._apply_improvements(current_template, improvements, issues)
        
        # Get next version number
        versions = self.storage.ai_prompts.list_prompt_versions(prompt_name)
        next_version = max([v['prompt_version'] for v in versions], default=current_version) + 1
        
        # Create metadata
        metadata = {
            'refined_from_version': current_version,
            'issues_addressed': issues,
            'improvements': improvements,
            'refined_at': self._get_timestamp()
        }
        
        return PromptUpdate(
            prompt_name=prompt_name,
            new_version=next_version,
            improved_template=improved_template,
            improvements=improvements,
            issues_addressed=issues,
            metadata=metadata
        )
    
    def _generate_improvements(self, issues: List[str],
                              feedback_analysis: Dict[str, Any]) -> List[str]:
        """
        Generate specific improvements based on issues
        
        Args:
            issues: List of issues to address
            feedback_analysis: Full feedback analysis
            
        Returns:
            List of improvement descriptions
        """
        improvements = []
        
        for issue in issues:
            issue_lower = issue.lower()
            
            # Format issues
            if 'format' in issue_lower:
                improvements.append(
                    "Add explicit instructions about data format requirements and validation"
                )
            
            # Data quality issues
            if 'data' in issue_lower or 'invalid' in issue_lower:
                improvements.append(
                    "Add examples of valid data formats and emphasize using realistic test data"
                )
            
            # Missing fields
            if 'missing' in issue_lower:
                improvements.append(
                    "Strengthen instructions about including all required fields and parameters"
                )
            
            # Coverage issues
            if 'coverage' in issue_lower or 'test' in issue_lower:
                improvements.append(
                    "Add guidance on generating comprehensive test scenarios including edge cases"
                )
            
            # Quality issues
            if 'quality' in issue_lower or 'low' in issue_lower or 'approval' in issue_lower:
                improvements.append(
                    "Enhance prompt clarity with more specific examples and clearer instructions"
                )
            
            # Method-specific issues
            if any(method in issue_lower for method in ['post', 'get', 'put', 'delete', 'patch']):
                improvements.append(
                    "Add method-specific guidance and examples for different HTTP methods"
                )
        
        # Add general improvements based on insights
        insights = feedback_analysis.get('actionable_insights', [])
        for insight in insights:
            if insight.get('priority') == 'high':
                recommendation = insight.get('recommendation', '')
                if recommendation and recommendation not in improvements:
                    improvements.append(recommendation)
        
        return list(set(improvements))  # Remove duplicates
    
    def _apply_improvements(self, template: str, improvements: List[str],
                           issues: List[str]) -> str:
        """
        Apply improvements to prompt template
        
        Args:
            template: Current prompt template
            improvements: List of improvements to apply
            issues: List of issues being addressed
            
        Returns:
            Improved prompt template
        """
        improved = template
        
        # Add improvement section to instructions if not present
        if "## Instructions" in improved or "<instructions>" in improved.lower():
            # Find instructions section and enhance it
            if "## Instructions" in improved:
                # Markdown format
                instructions_marker = "## Instructions"
                instructions_end = improved.find("\n\n", improved.find(instructions_marker))
                if instructions_end == -1:
                    instructions_end = len(improved)
                
                # Add improvement notes
                improvement_text = "\n\n**IMPROVEMENTS (v{next_version})**:\n"
                improvement_text += "- " + "\n- ".join(improvements[:3])  # Limit to top 3
                improvement_text += "\n"
                
                improved = (
                    improved[:instructions_end] +
                    improvement_text +
                    improved[instructions_end:]
                )
            elif "<instructions>" in improved.lower():
                # XML format
                instructions_start = improved.lower().find("<instructions>")
                instructions_end = improved.find("</instructions>", instructions_start)
                if instructions_end != -1:
                    improvement_text = "\n<improvements>\n"
                    improvement_text += "\n".join([f"- {imp}" for imp in improvements[:3]])
                    improvement_text += "\n</improvements>\n"
                    
                    improved = (
                        improved[:instructions_end] +
                        improvement_text +
                        improved[instructions_end:]
                    )
        
        # Enhance specific sections based on issues
        for issue in issues:
            issue_lower = issue.lower()
            
            # Add format validation instructions
            if 'format' in issue_lower and "format" not in improved.lower():
                format_note = "\n**IMPORTANT**: Ensure all data follows the correct format as specified in the schema."
                if "## Instructions" in improved:
                    improved = improved.replace("## Instructions", format_note + "\n## Instructions")
            
            # Add required fields emphasis
            if 'missing' in issue_lower or 'required' in issue_lower:
                required_note = "\n**CRITICAL**: Include ALL required fields and parameters in test cases."
                if "## Instructions" in improved and required_note not in improved:
                    improved = improved.replace("## Instructions", required_note + "\n## Instructions")
            
            # Add data quality emphasis
            if 'data' in issue_lower or 'invalid' in issue_lower:
                quality_note = "\n**DATA QUALITY**: Use realistic, valid test data that matches schema constraints."
                if "## Instructions" in improved and quality_note not in improved:
                    improved = improved.replace("## Instructions", quality_note + "\n## Instructions")
        
        return improved
    
    def save_refined_prompt(self, prompt_update: PromptUpdate, set_active: bool = False) -> int:
        """
        Save a refined prompt to storage
        
        Args:
            prompt_update: PromptUpdate object with refined template
            set_active: Whether to set this version as active (default: False for A/B testing)
            
        Returns:
            Prompt ID of saved prompt
        """
        prompt_id = self.storage.ai_prompts.save_prompt(
            prompt_name=prompt_update.prompt_name,
            prompt_template=prompt_update.improved_template,
            metadata=prompt_update.metadata,
            version=prompt_update.new_version
        )
        
        if set_active:
            self.storage.ai_prompts.set_active_prompt(
                prompt_update.prompt_name,
                prompt_update.new_version
            )
            logger.info(f"Set refined prompt '{prompt_update.prompt_name}' v{prompt_update.new_version} as active")
        else:
            logger.info(f"Saved refined prompt '{prompt_update.prompt_name}' v{prompt_update.new_version} (not active, for A/B testing)")
        
        return prompt_id
    
    def compare_prompt_versions(self, prompt_name: str, version1: int, version2: int) -> Dict[str, Any]:
        """
        Compare two prompt versions for A/B testing
        
        Args:
            prompt_name: Name of prompt
            version1: First version to compare
            version2: Second version to compare
            
        Returns:
            Dictionary with comparison metrics
        """
        prompt1 = self.storage.ai_prompts.get_prompt(prompt_name, version1)
        prompt2 = self.storage.ai_prompts.get_prompt(prompt_name, version2)
        
        if not prompt1 or not prompt2:
            logger.warning(f"Could not find one or both prompt versions for comparison")
            return {}
        
        # Get feedback for each version (would need to track which version was used)
        # For now, return basic comparison
        return {
            'version1': {
                'version': version1,
                'created_at': prompt1.get('created_at'),
                'is_active': prompt1.get('is_active', False),
                'template_length': len(prompt1.get('prompt_template', ''))
            },
            'version2': {
                'version': version2,
                'created_at': prompt2.get('created_at'),
                'is_active': prompt2.get('is_active', False),
                'template_length': len(prompt2.get('prompt_template', ''))
            },
            'differences': {
                'length_diff': len(prompt2.get('prompt_template', '')) - len(prompt1.get('prompt_template', '')),
                'has_improvements': 'IMPROVEMENTS' in prompt2.get('prompt_template', '')
            }
        }
    
    def _get_timestamp(self) -> str:
        """Get current timestamp as ISO string"""
        from datetime import datetime
        return datetime.utcnow().isoformat()

