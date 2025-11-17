"""
Test case library for storing validated AI-generated test cases

This module provides functionality for saving and loading validated test cases
to/from a local directory structure.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


def get_library_dir() -> Path:
    """Get the path to the test case library directory"""
    library_dir = Path.home() / '.apitest' / 'validated_tests'
    library_dir.mkdir(parents=True, exist_ok=True)
    return library_dir


def save_test_case_to_library(test_case: Dict[str, Any], 
                               filename: Optional[str] = None) -> Path:
    """
    Save a validated test case to the library
    
    Args:
        test_case: Test case dictionary containing:
            - schema_file: Schema file identifier
            - method: HTTP method
            - path: Endpoint path
            - test_case_json: Test case data
            - validation_status: Should be 'approved'
            - version: Optional version number
        filename: Optional custom filename. If not provided, generates one.
        
    Returns:
        Path to the saved file
    """
    library_dir = get_library_dir()
    
    # Generate filename if not provided
    if not filename:
        schema_file = test_case.get('schema_file', 'unknown')
        method = test_case.get('method', 'UNKNOWN')
        path = test_case.get('path', 'unknown')
        version = test_case.get('version', 1)
        
        # Sanitize path for filename (replace / with _)
        safe_path = path.replace('/', '_').replace('{', '').replace('}', '')
        safe_schema = Path(schema_file).stem if schema_file != 'unknown' else 'unknown'
        
        filename = f"{safe_schema}_{method}_{safe_path}_v{version}.json"
    
    file_path = library_dir / filename
    
    # Ensure unique filename if file already exists
    counter = 1
    original_path = file_path
    while file_path.exists():
        stem = original_path.stem
        suffix = original_path.suffix
        file_path = library_dir / f"{stem}_{counter}{suffix}"
        counter += 1
    
    # Save test case to file
    with open(file_path, 'w') as f:
        json.dump(test_case, f, indent=2)
    
    logger.debug(f"Saved test case to library: {file_path}")
    return file_path


def load_test_case_from_library(filename: str) -> Dict[str, Any]:
    """
    Load a test case from the library
    
    Args:
        filename: Name of the test case file
        
    Returns:
        Test case dictionary
        
    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is not valid JSON
    """
    library_dir = get_library_dir()
    file_path = library_dir / filename
    
    if not file_path.exists():
        raise FileNotFoundError(f"Test case file not found: {file_path}")
    
    with open(file_path, 'r') as f:
        test_case = json.load(f)
    
    return test_case


def list_test_cases_in_library() -> List[Path]:
    """
    List all test case files in the library
    
    Returns:
        List of Path objects for test case files
    """
    library_dir = get_library_dir()
    
    if not library_dir.exists():
        return []
    
    # Get all JSON files
    test_case_files = list(library_dir.glob('*.json'))
    return sorted(test_case_files, key=lambda p: p.stat().st_mtime, reverse=True)


def get_test_cases_by_endpoint(schema_file: str, method: str, 
                                path: str) -> List[Dict[str, Any]]:
    """
    Get all test cases from library for a specific endpoint
    
    Args:
        schema_file: Schema file identifier
        method: HTTP method
        path: Endpoint path
        
    Returns:
        List of test case dictionaries
    """
    test_cases = []
    
    # Load all test cases and filter
    for file_path in list_test_cases_in_library():
        try:
            test_case = load_test_case_from_library(file_path.name)
            
            # Check if matches endpoint
            if (test_case.get('schema_file') == schema_file and
                test_case.get('method', '').upper() == method.upper() and
                test_case.get('path') == path):
                test_cases.append(test_case)
        except Exception as e:
            logger.warning(f"Failed to load test case from {file_path}: {e}")
            continue
    
    return test_cases


def delete_test_case_from_library(filename: str) -> bool:
    """
    Delete a test case from the library
    
    Args:
        filename: Name of the test case file
        
    Returns:
        True if deleted, False if file didn't exist
    """
    library_dir = get_library_dir()
    file_path = library_dir / filename
    
    if file_path.exists():
        file_path.unlink()
        logger.debug(f"Deleted test case from library: {file_path}")
        return True
    
    return False

