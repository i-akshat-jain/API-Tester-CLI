"""
Validation interface for AI-generated test cases

Provides CLI and JSON interfaces for human validation of AI-generated tests.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.text import Text

logger = logging.getLogger(__name__)

# Validation status constants
VALIDATION_STATUS_PENDING = 'pending'
VALIDATION_STATUS_APPROVED = 'approved'
VALIDATION_STATUS_REJECTED = 'rejected'
VALIDATION_STATUS_NEEDS_IMPROVEMENT = 'needs_improvement'


class ValidationStatus(Enum):
    """Validation status enum"""
    PENDING = VALIDATION_STATUS_PENDING
    APPROVED = VALIDATION_STATUS_APPROVED
    REJECTED = VALIDATION_STATUS_REJECTED
    NEEDS_IMPROVEMENT = VALIDATION_STATUS_NEEDS_IMPROVEMENT


@dataclass
class ValidationFeedback:
    """Feedback for a validated AI test case"""
    test_case_id: int
    status: str  # pending, approved, rejected, needs_improvement
    feedback_text: Optional[str] = None
    annotations: Optional[Dict[str, Any]] = None
    suggested_improvements: Optional[List[str]] = None
    validated_by: Optional[str] = None  # User identifier (optional)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'test_case_id': self.test_case_id,
            'status': self.status,
            'feedback_text': self.feedback_text,
            'annotations': self.annotations or {},
            'suggested_improvements': self.suggested_improvements or [],
            'validated_by': self.validated_by
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ValidationFeedback':
        """Create from dictionary"""
        return cls(
            test_case_id=data['test_case_id'],
            status=data['status'],
            feedback_text=data.get('feedback_text'),
            annotations=data.get('annotations'),
            suggested_improvements=data.get('suggested_improvements'),
            validated_by=data.get('validated_by')
        )


class ValidationUI:
    """
    CLI-based validation interface for AI-generated test cases
    
    Provides interactive interface for reviewing and validating AI tests.
    """
    
    def __init__(self, storage: Any):
        """
        Initialize validation UI
        
        Args:
            storage: Storage instance with ai_tests and validation_feedback namespaces
        """
        self.storage = storage
        self.console = Console()
    
    def review_ai_tests(self, test_results: Optional[List[Dict[str, Any]]] = None,
                       test_case_ids: Optional[List[int]] = None,
                       schema_file: Optional[str] = None) -> List[ValidationFeedback]:
        """
        Review and validate AI-generated test cases
        
        Args:
            test_results: Optional list of test result dictionaries
            test_case_ids: Optional list of test case IDs to review
            schema_file: Optional schema file to filter by
            
        Returns:
            List of ValidationFeedback objects
        """
        # Get test cases to review
        test_cases = self._get_test_cases_to_review(test_results, test_case_ids, schema_file)
        
        if not test_cases:
            self.console.print("[yellow]No AI test cases found for validation.[/yellow]")
            return []
        
        self.console.print(f"\n[bold cyan]Reviewing {len(test_cases)} AI-generated test case(s)[/bold cyan]\n")
        
        feedback_list = []
        
        for i, test_case in enumerate(test_cases, 1):
            feedback = self._review_single_test_case(test_case, i, len(test_cases))
            if feedback:
                feedback_list.append(feedback)
        
        return feedback_list
    
    def _get_test_cases_to_review(self, test_results: Optional[List[Dict[str, Any]]],
                                  test_case_ids: Optional[List[int]],
                                  schema_file: Optional[str]) -> List[Dict[str, Any]]:
        """Get test cases to review from various sources"""
        test_cases = []
        
        if test_case_ids:
            # Get specific test cases by ID
            for test_case_id in test_case_ids:
                test_case = self.storage.ai_tests.get_test_case(test_case_id)
                if test_case:
                    test_cases.append(test_case)
        elif test_results:
            # Extract test cases from test results
            for result in test_results:
                if result.get('is_ai_generated') and result.get('test_case_id'):
                    test_case = self.storage.ai_tests.get_test_case(result['test_case_id'])
                    if test_case:
                        test_cases.append(test_case)
        else:
            # Get all pending test cases from database
            test_cases = self.get_pending_test_cases(schema_file=schema_file)
        
        return test_cases
    
    def get_pending_test_cases(self, schema_file: Optional[str] = None, 
                               limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get all pending test cases from the database
        
        Args:
            schema_file: Optional schema file to filter by
            limit: Maximum number of test cases to return
            
        Returns:
            List of test case dictionaries with validation_status='pending'
        """
        # Use the storage interface method
        return self.storage.ai_tests.get_test_cases_by_status(
            status=VALIDATION_STATUS_PENDING,
            schema_file=schema_file,
            limit=limit
        )
    
    def get_all_test_cases_by_endpoint(self, schema_file: str, 
                                       method: Optional[str] = None,
                                       path: Optional[str] = None) -> Dict[tuple, List[Dict[str, Any]]]:
        """
        Get all test cases (pending, approved, rejected) grouped by endpoint
        
        Args:
            schema_file: Schema file identifier
            method: Optional HTTP method filter
            path: Optional path filter
            
        Returns:
            Dictionary mapping (method, path) tuples to lists of test cases
        """
        # Get all test cases for the schema
        all_test_cases = self.storage.ai_tests.get_all_test_cases(
            schema_file=schema_file,
            limit=1000
        )
        
        # Filter by method and path if specified
        if method:
            all_test_cases = [tc for tc in all_test_cases if tc['method'].upper() == method.upper()]
        if path:
            all_test_cases = [tc for tc in all_test_cases if tc['path'] == path]
        
        # Group by endpoint
        from collections import defaultdict
        endpoint_groups = defaultdict(list)
        
        for test_case in all_test_cases:
            key = (test_case['method'], test_case['path'])
            endpoint_groups[key].append(test_case)
        
        return dict(endpoint_groups)
    
    def _review_single_test_case(self, test_case: Dict[str, Any], 
                                 current: int, total: int) -> Optional[ValidationFeedback]:
        """Review a single test case interactively"""
        test_case_id = test_case['id']
        test_case_json = test_case.get('test_case_json', {})
        method = test_case.get('method', 'UNKNOWN')
        path = test_case.get('path', 'UNKNOWN')
        test_scenario = test_case_json.get('test_scenario', 'N/A')
        request_body = test_case_json.get('request_body')
        expected_response = test_case_json.get('expected_response', {})
        
        # Display test case
        self.console.print(f"\n[bold]Test Case {current}/{total}[/bold]")
        self.console.print(f"[dim]ID: {test_case_id}[/dim]")
        
        # Create table for test case details
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Field", style="cyan", width=20)
        table.add_column("Value", style="white")
        
        table.add_row("Method", method)
        table.add_row("Path", path)
        table.add_row("Scenario", test_scenario)
        
        if request_body:
            request_str = json.dumps(request_body, indent=2)
            if len(request_str) > 200:
                request_str = request_str[:200] + "..."
            table.add_row("Request Body", request_str)
        
        if expected_response:
            response_str = json.dumps(expected_response, indent=2)
            if len(response_str) > 200:
                response_str = response_str[:200] + "..."
            table.add_row("Expected Response", response_str)
        
        self.console.print(table)
        
        # Prompt for validation
        self.console.print("\n[bold]Validation Options:[/bold]")
        self.console.print("  [green]a[/green] - Approve")
        self.console.print("  [red]r[/red] - Reject")
        self.console.print("  [yellow]i[/yellow] - Needs Improvement")
        self.console.print("  [dim]s[/dim] - Skip")
        self.console.print("  [dim]q[/dim] - Quit")
        
        choice = Prompt.ask("\n[bold]Your choice[/bold]", 
                           choices=['a', 'r', 'i', 's', 'q'], 
                           default='s')
        
        if choice == 'q':
            return None
        
        if choice == 's':
            return None
        
        # Map choice to status
        status_map = {
            'a': VALIDATION_STATUS_APPROVED,
            'r': VALIDATION_STATUS_REJECTED,
            'i': VALIDATION_STATUS_NEEDS_IMPROVEMENT
        }
        status = status_map[choice]
        
        # Get feedback text
        feedback_text = None
        if choice in ['r', 'i']:
            feedback_text = Prompt.ask("[yellow]Feedback (optional)[/yellow]", default="")
            if not feedback_text.strip():
                feedback_text = None
        
        # Get suggested improvements if needed
        suggested_improvements = None
        if choice == 'i':
            improvements = []
            self.console.print("\n[bold]Suggested Improvements (press Enter with empty line to finish):[/bold]")
            while True:
                improvement = Prompt.ask("  Improvement", default="")
                if not improvement.strip():
                    break
                improvements.append(improvement)
            suggested_improvements = improvements if improvements else None
        
        # Create feedback
        feedback = ValidationFeedback(
            test_case_id=test_case_id,
            status=status,
            feedback_text=feedback_text,
            suggested_improvements=suggested_improvements
        )
        
        return feedback
    
    def save_feedback(self, feedback_list: List[ValidationFeedback]) -> None:
        """
        Save validation feedback to storage
        
        Args:
            feedback_list: List of ValidationFeedback objects
        """
        for feedback in feedback_list:
            try:
                # Save feedback
                validation_id = self.storage.validation_feedback.save_validation(
                    test_case_id=feedback.test_case_id,
                    status=feedback.status,
                    feedback_text=feedback.feedback_text,
                    annotations=feedback.annotations
                )
                
                # Update test case validation status
                self.storage.ai_tests.update_validation_status(
                    feedback.test_case_id,
                    feedback.status
                )
                
                logger.debug(f"Saved validation {validation_id} for test case {feedback.test_case_id}")
            except Exception as e:
                logger.error(f"Error saving feedback for test case {feedback.test_case_id}: {e}")
                self.console.print(f"[red]Error saving feedback: {e}[/red]")
        
        self.console.print(f"\n[green]✓ Saved {len(feedback_list)} validation(s)[/green]")
    
    def export_to_json(self, test_cases: List[Dict[str, Any]], 
                      output_path: Path) -> None:
        """
        Export test cases to JSON for external validation
        
        Args:
            test_cases: List of test case dictionaries
            output_path: Path to output JSON file
        """
        export_data = {
            'test_cases': []
        }
        
        for test_case in test_cases:
            export_data['test_cases'].append({
                'id': test_case['id'],
                'schema_file': test_case.get('schema_file'),
                'method': test_case.get('method'),
                'path': test_case.get('path'),
                'test_case_json': test_case.get('test_case_json'),
                'validation_status': test_case.get('validation_status'),
                'created_at': test_case.get('created_at')
            })
        
        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        self.console.print(f"[green]✓ Exported {len(test_cases)} test case(s) to {output_path}[/green]")
    
    def import_from_json(self, input_path: Path) -> List[ValidationFeedback]:
        """
        Import validation feedback from JSON file
        
        Args:
            input_path: Path to input JSON file
            
        Returns:
            List of ValidationFeedback objects
        """
        with open(input_path, 'r') as f:
            data = json.load(f)
        
        feedback_list = []
        
        for validation_data in data.get('validations', []):
            feedback = ValidationFeedback.from_dict(validation_data)
            feedback_list.append(feedback)
        
        return feedback_list

