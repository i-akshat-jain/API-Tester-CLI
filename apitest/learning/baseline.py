"""
Baseline tracking and regression detection

This module provides functionality for:
- Establishing baselines from successful test runs
- Detecting regressions by comparing new results to baselines
- Tracking response times, status codes, and schema changes
"""

import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from apitest.storage.database import Database
from apitest.tester import TestResult, TestStatus

logger = logging.getLogger(__name__)


class RegressionType(Enum):
    """Types of regressions that can be detected"""
    RESPONSE_TIME = "response_time"
    STATUS_CODE = "status_code"
    SCHEMA_CHANGE = "schema_change"
    NONE = "none"


@dataclass
class Regression:
    """Represents a detected regression"""
    type: RegressionType
    endpoint: str  # method + path
    message: str
    baseline_value: Any
    current_value: Any
    severity: str = "warning"  # "warning" or "error"


class BaselineManager:
    """Manage baselines and detect regressions"""
    
    def __init__(self, db: Optional[Database] = None):
        """
        Initialize baseline manager
        
        Args:
            db: Optional Database instance. If None, creates a new one.
        """
        self.db = db or Database()
    
    def establish_baseline(self, schema_file: str, method: str, path: str,
                          status_code: int, response_time_ms: float,
                          response_body: Optional[Dict[str, Any]] = None) -> bool:
        """
        Store first successful test as baseline
        
        Tracks response times, status codes, and schemas.
        Only establishes baseline if one doesn't already exist.
        
        Args:
            schema_file: Schema file identifier
            method: HTTP method
            path: Endpoint path
            status_code: Response status code
            response_time_ms: Response time in milliseconds
            response_body: Optional response body (for schema extraction)
            
        Returns:
            True if baseline was established, False if one already exists
        """
        # Check if baseline already exists
        existing_baseline = self.db.get_baseline(schema_file, method, path)
        
        if existing_baseline:
            logger.debug(f"Baseline already exists for {method} {path}")
            return False
        
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
        
        logger.info(f"Baseline established for {method} {path}: status={status_code}, time={response_time_ms}ms")
        return True
    
    def detect_regressions(self, schema_file: str, method: str, path: str,
                          status_code: int, response_time_ms: float,
                          response_body: Optional[Dict[str, Any]] = None,
                          response_time_threshold: float = 1.5) -> List[Regression]:
        """
        Compare new results to baseline and detect regressions
        
        Flags:
        - Response time increases (if > threshold * baseline)
        - Schema changes (if response schema differs)
        - Status code changes (if status code differs)
        
        Args:
            schema_file: Schema file identifier
            method: HTTP method
            path: Endpoint path
            status_code: Current response status code
            response_time_ms: Current response time in milliseconds
            response_body: Optional response body (for schema comparison)
            response_time_threshold: Multiplier for response time regression (default: 1.5x)
            
        Returns:
            List of detected regressions
        """
        regressions = []
        
        # Get baseline
        baseline = self.db.get_baseline(schema_file, method, path)
        
        if not baseline:
            logger.debug(f"No baseline found for {method} {path}, skipping regression detection")
            return regressions
        
        endpoint = f"{method} {path}"
        
        # Check status code regression
        if status_code != baseline['status_code']:
            regressions.append(Regression(
                type=RegressionType.STATUS_CODE,
                endpoint=endpoint,
                message=f"Status code changed from {baseline['status_code']} to {status_code}",
                baseline_value=baseline['status_code'],
                current_value=status_code,
                severity="error" if status_code >= 400 else "warning"
            ))
        
        # Check response time regression
        baseline_time = baseline['response_time_ms']
        threshold_time = baseline_time * response_time_threshold
        
        if response_time_ms > threshold_time:
            increase_percent = ((response_time_ms - baseline_time) / baseline_time) * 100
            regressions.append(Regression(
                type=RegressionType.RESPONSE_TIME,
                endpoint=endpoint,
                message=f"Response time increased by {increase_percent:.1f}% "
                       f"({baseline_time:.1f}ms → {response_time_ms:.1f}ms)",
                baseline_value=baseline_time,
                current_value=response_time_ms,
                severity="warning" if increase_percent < 100 else "error"
            ))
        
        # Check schema regression
        if response_body and baseline.get('response_schema'):
            current_schema = self._extract_schema_from_response(response_body)
            baseline_schema = baseline['response_schema']
            
            if not self._schemas_match(baseline_schema, current_schema):
                regressions.append(Regression(
                    type=RegressionType.SCHEMA_CHANGE,
                    endpoint=endpoint,
                    message="Response schema has changed from baseline",
                    baseline_value=baseline_schema,
                    current_value=current_schema,
                    severity="warning"
                ))
        
        return regressions
    
    def _extract_schema_from_response(self, response_body: Any) -> Optional[Dict[str, Any]]:
        """
        Extract JSON schema from response body
        
        Args:
            response_body: Response body (dict, list, or primitive)
            
        Returns:
            Simplified schema representation or None
        """
        if response_body is None:
            return None
        
        if isinstance(response_body, dict):
            schema = {'type': 'object', 'properties': {}}
            for key, value in response_body.items():
                schema['properties'][key] = self._get_value_schema(value)
            return schema
        elif isinstance(response_body, list):
            if response_body:
                # Use first item as template
                item_schema = self._get_value_schema(response_body[0])
                return {'type': 'array', 'items': item_schema}
            else:
                return {'type': 'array', 'items': {}}
        else:
            return self._get_value_schema(response_body)
    
    def _get_value_schema(self, value: Any) -> Dict[str, Any]:
        """Get schema for a single value"""
        if isinstance(value, bool):
            return {'type': 'boolean'}
        elif isinstance(value, int):
            return {'type': 'integer'}
        elif isinstance(value, float):
            return {'type': 'number'}
        elif isinstance(value, str):
            return {'type': 'string'}
        elif isinstance(value, dict):
            return {'type': 'object', 'properties': {
                k: self._get_value_schema(v) for k, v in value.items()
            }}
        elif isinstance(value, list):
            if value:
                return {'type': 'array', 'items': self._get_value_schema(value[0])}
            else:
                return {'type': 'array', 'items': {}}
        else:
            return {'type': 'string'}  # Default fallback
    
    def _schemas_match(self, schema1: Dict[str, Any], schema2: Dict[str, Any]) -> bool:
        """
        Compare two schemas to see if they match
        
        Args:
            schema1: First schema
            schema2: Second schema
            
        Returns:
            True if schemas match, False otherwise
        """
        # Simple comparison - check type and structure
        if schema1.get('type') != schema2.get('type'):
            return False
        
        schema_type = schema1.get('type')
        
        if schema_type == 'object':
            props1 = set(schema1.get('properties', {}).keys())
            props2 = set(schema2.get('properties', {}).keys())
            # Check if property sets match
            if props1 != props2:
                return False
            # Recursively check nested properties
            for prop in props1:
                if not self._schemas_match(
                    schema1['properties'][prop],
                    schema2['properties'][prop]
                ):
                    return False
        
        elif schema_type == 'array':
            items1 = schema1.get('items', {})
            items2 = schema2.get('items', {})
            return self._schemas_match(items1, items2)
        
        # For primitive types, type match is sufficient
        return True
    
    def get_baseline(self, schema_file: str, method: str, path: str) -> Optional[Dict[str, Any]]:
        """
        Get baseline for an endpoint
        
        Args:
            schema_file: Schema file identifier
            method: HTTP method
            path: Endpoint path
            
        Returns:
            Baseline dictionary or None if not found
        """
        return self.db.get_baseline(schema_file, method, path)
    
    def get_all_baselines(self, schema_file: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all baselines, optionally filtered by schema file
        
        Args:
            schema_file: Optional filter by schema file
            
        Returns:
            List of baseline dictionaries
        """
        return self.db.get_all_baselines(schema_file)

