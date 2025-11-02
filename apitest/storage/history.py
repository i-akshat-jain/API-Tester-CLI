"""
Test history storage and baseline management

All data stored locally in SQLite database - never sent to external servers.
"""

import os
from typing import Optional, List, Dict, Any
from pathlib import Path
import logging

from apitest.storage.database import Database
from apitest.tester import TestResults, TestResult, TestStatus

logger = logging.getLogger(__name__)


class TestHistory:
    """Manage test history and baseline tracking"""
    
    def __init__(self, db: Optional[Database] = None):
        """
        Initialize test history manager
        
        Args:
            db: Optional Database instance. If None, creates a new one.
        """
        self.db = db or Database()
    
    def save_test_results(self, schema_file: str, test_results: TestResults,
                         store_payloads: bool = True) -> int:
        """
        Save test results to local database
        
        Args:
            schema_file: Path or identifier for the schema file
            test_results: TestResults object containing test results
            store_payloads: Whether to store request/response payloads (for learning)
            
        Returns:
            Number of results saved
        """
        saved_count = 0
        schema_identifier = self._normalize_schema_identifier(schema_file)
        
        try:
            for result in test_results.results:
                # Save test result
                test_id = self.db.save_test_result(
                    schema_file=schema_identifier,
                    method=result.method,
                    path=result.path,
                    status=result.status.value,
                    status_code=result.status_code,
                    expected_status=result.expected_status,
                    response_time_ms=result.response_time_ms,
                    error_message=result.error_message,
                    schema_mismatch=result.schema_mismatch,
                    response_size_bytes=result.response_size_bytes,
                    auth_attempts=result.auth_attempts,
                    auth_succeeded=result.auth_succeeded
                )
                saved_count += 1
                
                # Store request/response payloads if enabled and available
                if store_payloads and hasattr(result, 'request_headers') and hasattr(result, 'response_body'):
                    try:
                        self.db.save_request_response(
                            test_result_id=test_id,
                            request_method=result.method,
                            request_path=result.path,
                            request_headers=getattr(result, 'request_headers', None),
                            request_body=getattr(result, 'request_body', None),
                            request_params=getattr(result, 'request_params', None),
                            response_status_code=result.status_code,
                            response_headers=getattr(result, 'response_headers', None),
                            response_body=result.response_body,
                            response_time_ms=result.response_time_ms
                        )
                    except Exception as e:
                        logger.warning(f"Failed to save request/response payloads: {e}")
                
                # Establish baseline for first successful test
                if result.status == TestStatus.PASS and result.status_code:
                    self._establish_baseline_if_needed(
                        schema_identifier,
                        result.method,
                        result.path,
                        result.status_code,
                        result.response_time_ms,
                        result.response_body
                    )
            
            logger.debug(f"Saved {saved_count} test results to database")
            return saved_count
            
        except Exception as e:
            logger.error(f"Failed to save test results: {e}")
            raise
    
    def _establish_baseline_if_needed(self, schema_file: str, method: str, path: str,
                                     status_code: int, response_time_ms: float,
                                     response_body: Optional[Dict[str, Any]]):
        """
        Establish baseline for endpoint if one doesn't exist
        
        Args:
            schema_file: Schema identifier
            method: HTTP method
            path: Endpoint path
            status_code: Response status code
            response_time_ms: Response time in milliseconds
            response_body: Response body (used to extract schema)
        """
        try:
            # Check if baseline already exists
            existing_baseline = self.db.get_baseline(schema_file, method, path)
            
            if not existing_baseline:
                # Extract response schema from response body
                response_schema = None
                if response_body:
                    response_schema = self._extract_schema_from_response(response_body)
                
                # Establish baseline
                self.db.establish_baseline(
                    schema_file=schema_file,
                    method=method,
                    path=path,
                    status_code=status_code,
                    response_time_ms=response_time_ms,
                    response_schema=response_schema
                )
                logger.debug(f"Established baseline for {method} {path}")
        except Exception as e:
            logger.warning(f"Failed to establish baseline: {e}")
    
    def _extract_schema_from_response(self, response_body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract JSON schema structure from response body
        
        Args:
            response_body: Response body dictionary
            
        Returns:
            Basic JSON schema structure
        """
        if not isinstance(response_body, dict):
            return {'type': type(response_body).__name__}
        
        schema = {'type': 'object', 'properties': {}}
        
        for key, value in response_body.items():
            if isinstance(value, dict):
                schema['properties'][key] = {'type': 'object'}
            elif isinstance(value, list):
                schema['properties'][key] = {'type': 'array'}
                if value and isinstance(value[0], dict):
                    schema['properties'][key]['items'] = {'type': 'object'}
            elif isinstance(value, bool):
                schema['properties'][key] = {'type': 'boolean'}
            elif isinstance(value, int):
                schema['properties'][key] = {'type': 'integer'}
            elif isinstance(value, float):
                schema['properties'][key] = {'type': 'number'}
            else:
                schema['properties'][key] = {'type': 'string'}
        
        return schema
    
    def get_test_history(self, schema_file: str, method: Optional[str] = None,
                        path: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get test history for a schema
        
        Args:
            schema_file: Path or identifier for the schema file
            method: Optional filter by HTTP method
            path: Optional filter by endpoint path
            limit: Maximum number of results to return
            
        Returns:
            List of test result dictionaries
        """
        schema_identifier = self._normalize_schema_identifier(schema_file)
        return self.db.get_test_history(
            schema_file=schema_identifier,
            method=method,
            path=path,
            limit=limit
        )
    
    def get_baseline(self, schema_file: str, method: str, path: str) -> Optional[Dict[str, Any]]:
        """
        Get baseline for an endpoint
        
        Args:
            schema_file: Path or identifier for the schema file
            method: HTTP method
            path: Endpoint path
            
        Returns:
            Baseline dictionary or None if not found
        """
        schema_identifier = self._normalize_schema_identifier(schema_file)
        return self.db.get_baseline(schema_identifier, method, path)
    
    def get_all_baselines(self, schema_file: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all baselines, optionally filtered by schema file
        
        Args:
            schema_file: Optional schema file filter
            
        Returns:
            List of baseline dictionaries
        """
        if schema_file:
            schema_identifier = self._normalize_schema_identifier(schema_file)
            return self.db.get_all_baselines(schema_identifier)
        return self.db.get_all_baselines()
    
    def _normalize_schema_identifier(self, schema_file: str) -> str:
        """
        Normalize schema file identifier for storage
        
        Args:
            schema_file: Schema file path or identifier
            
        Returns:
            Normalized identifier (absolute path if file exists, otherwise as-is)
        """
        # If it's a file path that exists, use absolute path for consistency
        if os.path.exists(schema_file):
            return os.path.abspath(schema_file)
        
        # Otherwise, use as-is (could be URL or identifier)
        return schema_file
    
    def close(self):
        """Close database connection"""
        if self.db:
            self.db.close()
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

