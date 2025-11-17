"""
Feedback analyzer for AI-generated test cases

Analyzes validation feedback to identify patterns, common issues, and actionable insights
for improving AI test generation.
"""

import logging
from typing import Dict, Any, List, Optional
from collections import defaultdict, Counter
from datetime import datetime

logger = logging.getLogger(__name__)

# Validation status constants
VALIDATION_STATUS_APPROVED = 'approved'
VALIDATION_STATUS_REJECTED = 'rejected'
VALIDATION_STATUS_NEEDS_IMPROVEMENT = 'needs_improvement'
VALIDATION_STATUS_PENDING = 'pending'


class FeedbackAnalyzer:
    """
    Analyzes validation feedback to extract insights for improving AI test generation
    
    Identifies patterns in what works and what doesn't, calculates success rates,
    and provides actionable insights for prompt refinement.
    """
    
    def __init__(self, storage: Any):
        """
        Initialize feedback analyzer
        
        Args:
            storage: Storage instance with validation_feedback and ai_tests namespaces
        """
        self.storage = storage
    
    def analyze_feedback(self, limit: int = 100) -> Dict[str, Any]:
        """
        Analyze validation feedback to extract insights
        
        Args:
            limit: Maximum number of feedback entries to analyze
            
        Returns:
            Dictionary containing:
            - success_rates: Success rates by prompt version
            - common_issues: List of common rejection/improvement reasons
            - patterns: Patterns in approved vs rejected tests
            - actionable_insights: List of actionable insights for prompt improvement
            - feedback_summary: Summary statistics
        """
        # Load feedback corpus
        feedback_corpus = self.storage.validation_feedback.get_feedback_corpus(limit=limit)
        
        if not feedback_corpus:
            logger.warning("No feedback corpus found for analysis")
            return {
                'success_rates': {},
                'common_issues': [],
                'patterns': {},
                'actionable_insights': [],
                'feedback_summary': {
                    'total': 0,
                    'by_status': {}
                },
                'total_analyzed': 0
            }
        
        # Get feedback stats
        feedback_stats = self.storage.validation_feedback.get_feedback_stats()
        
        # Calculate success rates by prompt version
        success_rates = self._calculate_success_rates(feedback_corpus)
        
        # Identify common issues
        common_issues = self._identify_common_issues(feedback_corpus)
        
        # Extract patterns
        patterns = self._extract_patterns(feedback_corpus)
        
        # Extract actionable insights
        actionable_insights = self._extract_actionable_insights(
            feedback_corpus, success_rates, common_issues, patterns
        )
        
        return {
            'success_rates': success_rates,
            'common_issues': common_issues,
            'patterns': patterns,
            'actionable_insights': actionable_insights,
            'feedback_summary': feedback_stats,
            'total_analyzed': len(feedback_corpus)
        }
    
    def _calculate_success_rates(self, feedback_corpus: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Calculate success rates by prompt version
        
        Args:
            feedback_corpus: List of feedback entries
            
        Returns:
            Dictionary mapping prompt_version to success rate statistics
        """
        # Group feedback by prompt version
        by_prompt_version = defaultdict(lambda: {
            'approved': 0,
            'rejected': 0,
            'needs_improvement': 0,
            'total': 0
        })
        
        for feedback in feedback_corpus:
            # Extract prompt version from test case
            prompt_version = self._extract_prompt_version(feedback)
            
            status = feedback['status']
            by_prompt_version[prompt_version]['total'] += 1
            
            if status == VALIDATION_STATUS_APPROVED:
                by_prompt_version[prompt_version]['approved'] += 1
            elif status == VALIDATION_STATUS_REJECTED:
                by_prompt_version[prompt_version]['rejected'] += 1
            elif status == VALIDATION_STATUS_NEEDS_IMPROVEMENT:
                by_prompt_version[prompt_version]['needs_improvement'] += 1
        
        # Calculate success rates
        success_rates = {}
        for prompt_version, counts in by_prompt_version.items():
            total = counts['total']
            if total > 0:
                approved_rate = (counts['approved'] / total) * 100
                rejected_rate = (counts['rejected'] / total) * 100
                improvement_rate = (counts['needs_improvement'] / total) * 100
                
                success_rates[prompt_version] = {
                    'total': total,
                    'approved': counts['approved'],
                    'rejected': counts['rejected'],
                    'needs_improvement': counts['needs_improvement'],
                    'approved_rate': round(approved_rate, 2),
                    'rejected_rate': round(rejected_rate, 2),
                    'improvement_rate': round(improvement_rate, 2)
                }
        
        return success_rates
    
    def _extract_prompt_version(self, feedback: Dict[str, Any]) -> str:
        """
        Extract prompt version from feedback entry
        
        Args:
            feedback: Feedback dictionary with test_case_id
            
        Returns:
            Prompt version string (defaults to 'unknown' if not found)
        """
        test_case_id = feedback.get('test_case_id')
        if not test_case_id:
            return 'unknown'
        
        # Get test case to extract ai_metadata
        test_case = self.storage.ai_tests.get_test_case(test_case_id)
        if not test_case:
            return 'unknown'
        
        # Extract prompt version from test_case_json -> ai_metadata
        test_case_json = test_case.get('test_case_json', {})
        if isinstance(test_case_json, str):
            import json
            try:
                test_case_json = json.loads(test_case_json)
            except (json.JSONDecodeError, TypeError):
                return 'unknown'
        
        ai_metadata = test_case_json.get('ai_metadata', {})
        if isinstance(ai_metadata, str):
            import json
            try:
                ai_metadata = json.loads(ai_metadata)
            except (json.JSONDecodeError, TypeError):
                return 'unknown'
        
        prompt_version = ai_metadata.get('prompt_version', 'unknown')
        return str(prompt_version) if prompt_version else 'unknown'
    
    def _identify_common_issues(self, feedback_corpus: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Identify common issues from rejected/needs_improvement feedback
        
        Args:
            feedback_corpus: List of feedback entries
            
        Returns:
            List of common issues with counts and examples
        """
        # Filter for rejected/needs_improvement feedback
        problematic_feedback = [
            f for f in feedback_corpus
            if f['status'] in [VALIDATION_STATUS_REJECTED, VALIDATION_STATUS_NEEDS_IMPROVEMENT]
        ]
        
        if not problematic_feedback:
            return []
        
        # Extract feedback text and analyze
        feedback_texts = []
        for feedback in problematic_feedback:
            if feedback.get('feedback_text'):
                feedback_texts.append(feedback['feedback_text'].lower())
        
        # Common keywords/phrases that indicate issues
        issue_keywords = {
            'invalid': ['invalid', 'wrong', 'incorrect', 'bad'],
            'missing': ['missing', 'absent', 'not included', 'lack'],
            'format': ['format', 'structure', 'syntax', 'malformed'],
            'data': ['data', 'value', 'field', 'parameter'],
            'coverage': ['coverage', 'test', 'scenario', 'case'],
            'quality': ['quality', 'poor', 'low', 'unclear']
        }
        
        # Count occurrences of issue keywords
        issue_counts = defaultdict(int)
        issue_examples = defaultdict(list)
        
        for text in feedback_texts:
            for issue_type, keywords in issue_keywords.items():
                if any(keyword in text for keyword in keywords):
                    issue_counts[issue_type] += 1
                    # Store example (limit to 3 per issue type)
                    if len(issue_examples[issue_type]) < 3:
                        issue_examples[issue_type].append(text[:200])  # Truncate long examples
        
        # Build common issues list
        common_issues = []
        for issue_type, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True):
            common_issues.append({
                'issue_type': issue_type,
                'count': count,
                'percentage': round((count / len(problematic_feedback)) * 100, 2),
                'examples': issue_examples[issue_type]
            })
        
        return common_issues
    
    def _extract_patterns(self, feedback_corpus: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Extract patterns from feedback (what works, what doesn't)
        
        Args:
            feedback_corpus: List of feedback entries
            
        Returns:
            Dictionary of patterns
        """
        patterns = {
            'by_status': defaultdict(int),
            'by_endpoint': defaultdict(lambda: {'approved': 0, 'rejected': 0, 'needs_improvement': 0}),
            'by_method': defaultdict(lambda: {'approved': 0, 'rejected': 0, 'needs_improvement': 0}),
            'has_feedback_text': {'yes': 0, 'no': 0},
            'has_suggested_improvements': {'yes': 0, 'no': 0}
        }
        
        for feedback in feedback_corpus:
            status = feedback['status']
            patterns['by_status'][status] += 1
            
            # By endpoint (method + path)
            method = feedback.get('method', 'UNKNOWN')
            path = feedback.get('path', 'UNKNOWN')
            endpoint_key = f"{method} {path}"
            patterns['by_endpoint'][endpoint_key][status] += 1
            
            # By HTTP method
            patterns['by_method'][method][status] += 1
            
            # Feedback text presence
            if feedback.get('feedback_text'):
                patterns['has_feedback_text']['yes'] += 1
            else:
                patterns['has_feedback_text']['no'] += 1
            
            # Suggested improvements presence
            annotations = feedback.get('annotations_json', {})
            if isinstance(annotations, str):
                import json
                try:
                    annotations = json.loads(annotations)
                except (json.JSONDecodeError, TypeError):
                    annotations = {}
            
            if annotations and annotations.get('suggested_improvements'):
                patterns['has_suggested_improvements']['yes'] += 1
            else:
                patterns['has_suggested_improvements']['no'] += 1
        
        # Convert defaultdicts to regular dicts for JSON serialization
        patterns['by_status'] = dict(patterns['by_status'])
        patterns['by_endpoint'] = {k: dict(v) for k, v in patterns['by_endpoint'].items()}
        patterns['by_method'] = {k: dict(v) for k, v in patterns['by_method'].items()}
        
        return patterns
    
    def _extract_actionable_insights(self, feedback_corpus: List[Dict[str, Any]],
                                    success_rates: Dict[str, Dict[str, Any]],
                                    common_issues: List[Dict[str, Any]],
                                    patterns: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract actionable insights for prompt improvement
        
        Args:
            feedback_corpus: List of feedback entries
            success_rates: Success rates by prompt version
            common_issues: Common issues identified
            patterns: Patterns extracted
            
        Returns:
            List of actionable insights with priority and recommendations
        """
        insights = []
        
        # Insight 1: Prompt version performance
        if success_rates:
            best_version = max(
                success_rates.items(),
                key=lambda x: x[1].get('approved_rate', 0)
            )
            worst_version = min(
                success_rates.items(),
                key=lambda x: x[1].get('approved_rate', 100)
            )
            
            if best_version[1]['approved_rate'] > worst_version[1]['approved_rate'] + 10:
                insights.append({
                    'priority': 'high',
                    'category': 'prompt_version',
                    'insight': f"Prompt version '{best_version[0]}' performs significantly better than '{worst_version[0]}'",
                    'recommendation': f"Consider using '{best_version[0]}' as the default or analyze what makes it better",
                    'data': {
                        'best_version': best_version[0],
                        'best_approved_rate': best_version[1]['approved_rate'],
                        'worst_version': worst_version[0],
                        'worst_approved_rate': worst_version[1]['approved_rate']
                    }
                })
        
        # Insight 2: Common issues
        if common_issues:
            top_issue = common_issues[0]
            if top_issue['percentage'] > 30:  # If >30% of problematic feedback has this issue
                insights.append({
                    'priority': 'high',
                    'category': 'common_issue',
                    'insight': f"Most common issue: {top_issue['issue_type']} ({top_issue['percentage']}% of problematic tests)",
                    'recommendation': f"Update prompts to address {top_issue['issue_type']} issues. Add examples or clarify instructions.",
                    'data': {
                        'issue_type': top_issue['issue_type'],
                        'count': top_issue['count'],
                        'percentage': top_issue['percentage']
                    }
                })
        
        # Insight 3: Method-specific patterns
        if patterns.get('by_method'):
            method_issues = []
            for method, counts in patterns['by_method'].items():
                total = sum(counts.values())
                if total > 0:
                    rejected_rate = (counts.get('rejected', 0) / total) * 100
                    if rejected_rate > 50:  # >50% rejection rate
                        method_issues.append({
                            'method': method,
                            'rejected_rate': round(rejected_rate, 2),
                            'total': total
                        })
            
            if method_issues:
                worst_method = max(method_issues, key=lambda x: x['rejected_rate'])
                insights.append({
                    'priority': 'medium',
                    'category': 'method_pattern',
                    'insight': f"{worst_method['method']} requests have high rejection rate ({worst_method['rejected_rate']}%)",
                    'recommendation': f"Review and improve test generation for {worst_method['method']} requests. May need method-specific prompt templates.",
                    'data': worst_method
                })
        
        # Insight 4: Feedback quality
        total_feedback = len(feedback_corpus)
        has_feedback_text = patterns.get('has_feedback_text', {}).get('yes', 0)
        feedback_text_rate = (has_feedback_text / total_feedback * 100) if total_feedback > 0 else 0
        
        if feedback_text_rate < 50:  # <50% of feedback has text
            insights.append({
                'priority': 'low',
                'category': 'feedback_quality',
                'insight': f"Only {round(feedback_text_rate, 2)}% of feedback includes text comments",
                'recommendation': "Encourage users to provide detailed feedback text to improve learning",
                'data': {
                    'feedback_text_rate': round(feedback_text_rate, 2),
                    'total': total_feedback
                }
            })
        
        # Insight 5: Overall approval rate
        by_status = patterns.get('by_status', {})
        total = sum(by_status.values())
        approved = by_status.get('approved', 0)
        if total > 0:
            overall_approval_rate = (approved / total) * 100
            if overall_approval_rate < 50:  # <50% approval rate
                insights.append({
                    'priority': 'high',
                    'category': 'overall_performance',
                    'insight': f"Overall approval rate is {round(overall_approval_rate, 2)}% (below 50%)",
                    'recommendation': "Prompt quality needs significant improvement. Review common issues and update prompts accordingly.",
                    'data': {
                        'approval_rate': round(overall_approval_rate, 2),
                        'total': total,
                        'approved': approved
                    }
                })
        
        # Sort insights by priority (high -> medium -> low)
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        insights.sort(key=lambda x: priority_order.get(x['priority'], 3))
        
        return insights

