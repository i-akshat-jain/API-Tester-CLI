"""
Pattern extraction from successful test runs

This module analyzes successful API test requests to extract patterns
and common values for intelligent test data generation.
"""

import json
import re
from typing import Dict, Any, List, Optional, Set
from collections import Counter, defaultdict
from datetime import datetime
import logging

from apitest.storage.database import Database, Storage

logger = logging.getLogger(__name__)


class PatternExtractor:
    """Extract patterns from successful test runs"""
    
    def __init__(self, db: Optional[Database] = None):
        """
        Initialize pattern extractor
        
        Args:
            db: Optional Database instance. If None, creates a new one.
        """
        self.db = db or Database()
    
    def extract_common_values(self, schema_file: str, method: Optional[str] = None,
                            path: Optional[str] = None, min_occurrences: int = 2) -> Dict[str, Any]:
        """
        Analyze successful request payloads and extract frequently used values per field
        
        Args:
            schema_file: Schema file identifier to analyze
            method: Optional HTTP method filter (e.g., 'POST', 'PUT')
            path: Optional endpoint path filter
            min_occurrences: Minimum number of occurrences for a value to be considered common
            
        Returns:
            Dictionary mapping field paths to common values and patterns:
            {
                'field_name': {
                    'common_values': [('value1', count), ('value2', count), ...],
                    'patterns': {
                        'format': 'email|uuid|date',
                        'min_length': 5,
                        'max_length': 50,
                        'min_value': 1,
                        'max_value': 100,
                        'type': 'string|integer|number|boolean'
                    }
                }
            }
        """
        logger.debug(f"Extracting common values for schema: {schema_file}, method: {method}, path: {path}")
        
        # Get successful test results
        test_results = self.db.get_test_history(
            schema_file=schema_file,
            method=method,
            path=path,
            limit=1000  # Analyze up to 1000 recent tests
        )
        
        # Filter for successful tests only
        successful_tests = [
            tr for tr in test_results 
            if tr.get('status') == 'pass' and tr.get('status_code', 0) < 400
        ]
        
        if not successful_tests:
            logger.debug("No successful tests found for pattern extraction")
            return {}
        
        # Get request bodies for successful tests
        request_bodies = self._get_request_bodies([tr['id'] for tr in successful_tests])
        
        if not request_bodies:
            logger.debug("No request bodies found for pattern extraction")
            return {}
        
        # Analyze patterns
        field_patterns = defaultdict(lambda: {
            'values': Counter(),
            'lengths': [],
            'numeric_values': [],
            'formats': set(),
            'types': set()
        })
        
        for request_body in request_bodies:
            if not request_body:
                continue
            
            self._analyze_request_body(request_body, field_patterns, '')
        
        # Build result dictionary
        result = {}
        for field_path, patterns in field_patterns.items():
            # Get common values (appearing at least min_occurrences times)
            common_values = [
                (value, count) for value, count in patterns['values'].most_common()
                if count >= min_occurrences
            ]
            
            if not common_values and not patterns['lengths'] and not patterns['numeric_values']:
                continue  # Skip fields with no useful patterns
            
            field_info = {}
            
            if common_values:
                field_info['common_values'] = common_values
            
            # Extract patterns
            pattern_info = {}
            
            # Type pattern
            if patterns['types']:
                # Use most common type
                type_counter = Counter(patterns['types'])
                pattern_info['type'] = type_counter.most_common(1)[0][0]
            
            # Length patterns (for strings)
            if patterns['lengths']:
                pattern_info['min_length'] = min(patterns['lengths'])
                pattern_info['max_length'] = max(patterns['lengths'])
                pattern_info['avg_length'] = sum(patterns['lengths']) / len(patterns['lengths'])
            
            # Numeric patterns
            if patterns['numeric_values']:
                pattern_info['min_value'] = min(patterns['numeric_values'])
                pattern_info['max_value'] = max(patterns['numeric_values'])
                pattern_info['avg_value'] = sum(patterns['numeric_values']) / len(patterns['numeric_values'])
            
            # Format patterns (email, uuid, date, etc.)
            if patterns['formats']:
                # Join formats with | for regex pattern
                pattern_info['format'] = '|'.join(sorted(patterns['formats']))
            
            if pattern_info:
                field_info['patterns'] = pattern_info
            
            if field_info:
                result[field_path] = field_info
        
        logger.debug(f"Extracted patterns for {len(result)} fields")
        return result
    
    def _get_request_bodies(self, test_result_ids: List[int]) -> List[Optional[Dict[str, Any]]]:
        """
        Get request bodies for given test result IDs
        
        Args:
            test_result_ids: List of test result IDs
            
        Returns:
            List of request body dictionaries (or None if not available)
        """
        if not test_result_ids:
            return []
        
        cursor = self.db.conn.cursor()
        placeholders = ','.join(['?'] * len(test_result_ids))
        query = f"""
            SELECT request_body 
            FROM request_response_storage 
            WHERE test_result_id IN ({placeholders})
            AND request_body IS NOT NULL
        """
        
        cursor.execute(query, test_result_ids)
        rows = cursor.fetchall()
        
        request_bodies = []
        for row in rows:
            try:
                if row['request_body']:
                    request_bodies.append(json.loads(row['request_body']))
                else:
                    request_bodies.append(None)
            except (json.JSONDecodeError, TypeError):
                request_bodies.append(None)
        
        return request_bodies
    
    def _analyze_request_body(self, body: Any, field_patterns: Dict, field_path: str):
        """
        Recursively analyze request body to extract patterns
        
        Args:
            body: Request body (dict, list, or primitive)
            field_patterns: Dictionary to accumulate patterns
            field_path: Current field path (e.g., 'user.name')
        """
        if isinstance(body, dict):
            for key, value in body.items():
                new_path = f"{field_path}.{key}" if field_path else key
                self._analyze_request_body(value, field_patterns, new_path)
        elif isinstance(body, list):
            for i, item in enumerate(body):
                new_path = f"{field_path}[{i}]" if field_path else f"[{i}]"
                self._analyze_request_body(item, field_patterns, new_path)
        else:
            # Primitive value - analyze it
            if field_path not in field_patterns:
                field_patterns[field_path] = {
                    'values': Counter(),
                    'lengths': [],
                    'numeric_values': [],
                    'formats': set(),
                    'types': set()
                }
            
            patterns = field_patterns[field_path]
            
            # Track value occurrence
            if body is not None:
                patterns['values'][str(body)] += 1
            
            # Track type
            value_type = type(body).__name__
            patterns['types'].add(value_type)
            
            # Analyze based on type
            if isinstance(body, str):
                patterns['lengths'].append(len(body))
                # Detect format patterns
                format_type = self._detect_format(body)
                if format_type:
                    patterns['formats'].add(format_type)
            elif isinstance(body, (int, float)):
                patterns['numeric_values'].append(float(body))
    
    def _detect_format(self, value: str) -> Optional[str]:
        """
        Detect format pattern in string value
        
        Args:
            value: String value to analyze
            
        Returns:
            Format type ('email', 'uuid', 'date', 'date-time', 'uri', etc.) or None
        """
        if not isinstance(value, str):
            return None
        
        # Email pattern
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if re.match(email_pattern, value):
            return 'email'
        
        # UUID pattern
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        if re.match(uuid_pattern, value, re.IGNORECASE):
            return 'uuid'
        
        # Date pattern (YYYY-MM-DD)
        date_pattern = r'^\d{4}-\d{2}-\d{2}$'
        if re.match(date_pattern, value):
            return 'date'
        
        # Date-time pattern (ISO 8601)
        datetime_pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}'
        if re.match(datetime_pattern, value):
            return 'date-time'
        
        # URI pattern
        uri_pattern = r'^https?://'
        if re.match(uri_pattern, value):
            return 'uri'
        
        return None
    
    def learn_data_relationships(self, schema_file: str) -> Dict[str, Any]:
        """
        Map field relationships and track endpoint dependencies
        
        Examples:
        - user_id → user object (from GET /users/{id})
        - order_id → order object (from GET /orders/{id})
        - Track endpoint dependencies (POST /orders requires user_id from GET /users)
        
        Args:
            schema_file: Schema file identifier
            
        Returns:
            Dictionary containing:
            {
                'field_relationships': {
                    'user_id': {
                        'source_endpoint': 'GET /users/{id}',
                        'target_field': 'id',
                        'related_data': {...}
                    }
                },
                'endpoint_dependencies': {
                    'POST /orders': ['GET /users/{id}']  # Requires user_id
                },
                'data_flow_graph': {
                    'nodes': [...],
                    'edges': [...]
                }
            }
        """
        logger.debug(f"Learning data relationships for schema: {schema_file}")
        
        # Get all test history
        test_results = self.db.get_test_history(schema_file=schema_file, limit=1000)
        successful_tests = [
            tr for tr in test_results 
            if tr.get('status') == 'pass' and tr.get('status_code', 0) < 400
        ]
        
        field_relationships = {}
        endpoint_dependencies = defaultdict(set)
        data_flow_nodes = set()
        data_flow_edges = []
        
        # Analyze request/response pairs to find relationships
        for test in successful_tests:
            method = test.get('method', '').upper()
            path = test.get('path', '')
            endpoint = f"{method} {path}"
            data_flow_nodes.add(endpoint)
            
            # Get request and response bodies
            request_body = self._get_request_body(test.get('id'))
            response_body = self._get_response_body(test.get('id'))
            
            if not request_body or not response_body:
                continue
            
            # Find ID fields in requests that match response IDs
            request_ids = self._extract_id_fields(request_body)
            response_ids = self._extract_id_fields(response_body)
            
            # Map relationships: if request has user_id and response has id, they're related
            for req_id_field, req_id_value in request_ids.items():
                for resp_id_field, resp_id_value in response_ids.items():
                    if req_id_value == resp_id_value:
                        # Found a relationship
                        relationship_key = req_id_field
                        if relationship_key not in field_relationships:
                            field_relationships[relationship_key] = {
                                'source_endpoint': endpoint,
                                'target_field': resp_id_field,
                                'related_data': response_body,
                                'occurrences': 0
                            }
                        field_relationships[relationship_key]['occurrences'] += 1
            
            # Track dependencies: if POST/PUT/PATCH uses an ID, track dependency
            if method in ['POST', 'PUT', 'PATCH']:
                for req_id_field in request_ids.keys():
                    # Find GET endpoint that could provide this ID
                    for other_test in successful_tests:
                        other_method = other_test.get('method', '').upper()
                        other_path = other_test.get('path', '')
                        if other_method == 'GET' and f'/{req_id_field.replace("_id", "")}' in other_path.lower():
                            dependency_endpoint = f"{other_method} {other_path}"
                            endpoint_dependencies[endpoint].add(dependency_endpoint)
                            data_flow_edges.append((dependency_endpoint, endpoint))
        
        return {
            'field_relationships': field_relationships,
            'endpoint_dependencies': dict(endpoint_dependencies),
            'data_flow_graph': {
                'nodes': list(data_flow_nodes),
                'edges': data_flow_edges
            }
        }
    
    def _get_request_body(self, test_id: int) -> Optional[Dict[str, Any]]:
        """Get request body for a test ID"""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT request_body FROM request_responses WHERE test_id = ?
            """, (test_id,))
            row = cursor.fetchone()
            if row and row[0]:
                return json.loads(row[0])
        except Exception as e:
            logger.debug(f"Failed to get request body: {e}")
        return None
    
    def _get_response_body(self, test_id: int) -> Optional[Dict[str, Any]]:
        """Get response body for a test ID"""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT response_body FROM request_responses WHERE test_id = ?
            """, (test_id,))
            row = cursor.fetchone()
            if row and row[0]:
                return json.loads(row[0])
        except Exception as e:
            logger.debug(f"Failed to get response body: {e}")
        return None
    
    def _extract_id_fields(self, data: Any, prefix: str = '') -> Dict[str, Any]:
        """
        Extract ID fields from data structure
        
        Args:
            data: Data structure (dict, list, or primitive)
            prefix: Field path prefix
            
        Returns:
            Dictionary mapping field paths to ID values
        """
        id_fields = {}
        
        if isinstance(data, dict):
            for key, value in data.items():
                field_path = f"{prefix}.{key}" if prefix else key
                
                # Check if this looks like an ID field
                if key.lower().endswith('_id') or key.lower() == 'id':
                    if isinstance(value, (int, str)):
                        id_fields[field_path] = value
                
                # Recursively check nested structures
                nested_ids = self._extract_id_fields(value, field_path)
                id_fields.update(nested_ids)
        
        elif isinstance(data, list):
            for i, item in enumerate(data):
                nested_ids = self._extract_id_fields(item, f"{prefix}[{i}]")
                id_fields.update(nested_ids)
        
        return id_fields
    
    def extract_patterns_from_ai_tests(self, schema_file: Optional[str] = None,
                                       storage: Optional[Storage] = None) -> Dict[str, Any]:
        """
        Extract patterns from validated AI test cases (status='approved')
        
        Analyzes approved AI-generated test cases to learn what makes a good test case:
        - Effective test scenarios
        - Good edge case coverage
        - Proper data generation strategies
        - Test structure patterns
        
        Args:
            schema_file: Optional schema file to filter by
            storage: Optional Storage instance. If None, creates a new one.
            
        Returns:
            Dictionary containing extracted patterns:
            {
                'test_scenario_patterns': [...],
                'data_quality_patterns': [...],
                'edge_case_patterns': [...],
                'structure_patterns': [...],
                'patterns_saved': 5
            }
        """
        logger.debug(f"Extracting patterns from AI tests for schema: {schema_file}")
        
        # Use Storage if provided, otherwise create new one
        if storage is None:
            storage = Storage()
        
        # Get validated (approved) AI test cases
        validated_tests = storage.ai_tests.get_validated_test_cases(
            schema_file=schema_file,
            limit=1000
        )
        
        if not validated_tests:
            logger.debug("No validated AI test cases found for pattern extraction")
            return {
                'test_scenario_patterns': [],
                'data_quality_patterns': [],
                'edge_case_patterns': [],
                'structure_patterns': [],
                'patterns_saved': 0
            }
        
        logger.debug(f"Analyzing {len(validated_tests)} validated AI test cases")
        
        # Extract different types of patterns
        test_scenario_patterns = self._extract_test_scenario_patterns(validated_tests)
        data_quality_patterns = self._extract_data_quality_patterns(validated_tests)
        edge_case_patterns = self._extract_edge_case_patterns(validated_tests)
        structure_patterns = self._extract_structure_patterns(validated_tests)
        
        # Store patterns in storage
        patterns_saved = 0
        
        # Store test scenario patterns
        for pattern in test_scenario_patterns:
            pattern_id = storage.patterns.save_pattern(
                pattern_type='ai_test_scenario',
                pattern_data=pattern,
                effectiveness_score=pattern.get('effectiveness_score', 0.8)
            )
            patterns_saved += 1
            logger.debug(f"Saved test scenario pattern {pattern_id}")
        
        # Store data quality patterns
        for pattern in data_quality_patterns:
            pattern_id = storage.patterns.save_pattern(
                pattern_type='ai_data_quality',
                pattern_data=pattern,
                effectiveness_score=pattern.get('effectiveness_score', 0.8)
            )
            patterns_saved += 1
            logger.debug(f"Saved data quality pattern {pattern_id}")
        
        # Store edge case patterns
        for pattern in edge_case_patterns:
            pattern_id = storage.patterns.save_pattern(
                pattern_type='ai_edge_case',
                pattern_data=pattern,
                effectiveness_score=pattern.get('effectiveness_score', 0.8)
            )
            patterns_saved += 1
            logger.debug(f"Saved edge case pattern {pattern_id}")
        
        # Store structure patterns
        for pattern in structure_patterns:
            pattern_id = storage.patterns.save_pattern(
                pattern_type='ai_structure',
                pattern_data=pattern,
                effectiveness_score=pattern.get('effectiveness_score', 0.8)
            )
            patterns_saved += 1
            logger.debug(f"Saved structure pattern {pattern_id}")
        
        logger.info(f"Extracted and saved {patterns_saved} patterns from {len(validated_tests)} AI test cases")
        
        return {
            'test_scenario_patterns': test_scenario_patterns,
            'data_quality_patterns': data_quality_patterns,
            'edge_case_patterns': edge_case_patterns,
            'structure_patterns': structure_patterns,
            'patterns_saved': patterns_saved
        }
    
    def _extract_test_scenario_patterns(self, validated_tests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract patterns about effective test scenarios
        
        Args:
            validated_tests: List of validated AI test case dictionaries
            
        Returns:
            List of test scenario patterns
        """
        scenario_patterns = []
        scenario_counter = Counter()
        method_scenario_map = defaultdict(list)
        
        for test_case in validated_tests:
            test_case_json = test_case.get('test_case_json', {})
            if isinstance(test_case_json, str):
                try:
                    test_case_json = json.loads(test_case_json)
                except (json.JSONDecodeError, TypeError):
                    continue
            
            test_scenario = test_case_json.get('test_scenario', '')
            method = test_case.get('method', '').upper()
            path = test_case.get('path', '')
            
            if test_scenario:
                scenario_counter[test_scenario.lower()] += 1
                method_scenario_map[method].append({
                    'scenario': test_scenario,
                    'path': path
                })
        
        # Identify common effective scenarios
        for scenario, count in scenario_counter.most_common(10):
            if count >= 2:  # At least 2 occurrences
                # Extract scenario keywords
                keywords = self._extract_scenario_keywords(scenario)
                
                pattern = {
                    'scenario_text': scenario,
                    'keywords': keywords,
                    'occurrences': count,
                    'effectiveness_score': min(count / 10.0, 1.0),  # Normalize to 0-1
                    'pattern_type': 'scenario'
                }
                scenario_patterns.append(pattern)
        
        # Identify method-specific scenario patterns
        for method, scenarios in method_scenario_map.items():
            if len(scenarios) >= 3:
                common_keywords = self._find_common_keywords([s['scenario'] for s in scenarios])
                if common_keywords:
                    pattern = {
                        'method': method,
                        'common_keywords': common_keywords,
                        'scenario_count': len(scenarios),
                        'effectiveness_score': min(len(scenarios) / 20.0, 1.0),
                        'pattern_type': 'method_scenario'
                    }
                    scenario_patterns.append(pattern)
        
        return scenario_patterns
    
    def _extract_data_quality_patterns(self, validated_tests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract patterns about data quality in test cases
        
        Args:
            validated_tests: List of validated AI test case dictionaries
            
        Returns:
            List of data quality patterns
        """
        data_patterns = []
        field_usage = defaultdict(lambda: {'count': 0, 'types': Counter(), 'examples': []})
        
        for test_case in validated_tests:
            test_case_json = test_case.get('test_case_json', {})
            if isinstance(test_case_json, str):
                try:
                    test_case_json = json.loads(test_case_json)
                except (json.JSONDecodeError, TypeError):
                    continue
            
            request_body = test_case_json.get('request_body', {})
            if not isinstance(request_body, dict):
                continue
            
            # Analyze request body structure
            self._analyze_data_structure(request_body, field_usage, '')
        
        # Build patterns from field usage
        for field_path, usage_info in field_usage.items():
            if usage_info['count'] >= 2:  # At least 2 occurrences
                pattern = {
                    'field_path': field_path,
                    'usage_count': usage_info['count'],
                    'common_types': dict(usage_info['types'].most_common(3)),
                    'sample_values': usage_info['examples'][:5],  # Limit to 5 examples
                    'effectiveness_score': min(usage_info['count'] / 10.0, 1.0),
                    'pattern_type': 'data_quality'
                }
                data_patterns.append(pattern)
        
        return data_patterns
    
    def _extract_edge_case_patterns(self, validated_tests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract patterns about effective edge cases
        
        Args:
            validated_tests: List of validated AI test case dictionaries
            
        Returns:
            List of edge case patterns
        """
        edge_case_patterns = []
        edge_case_keywords = {
            'boundary': ['boundary', 'limit', 'min', 'max', 'edge', 'extreme'],
            'invalid': ['invalid', 'error', 'wrong', 'bad', 'malformed'],
            'empty': ['empty', 'null', 'missing', 'absent'],
            'special': ['special', 'unicode', 'special character', 'whitespace']
        }
        
        edge_case_counter = defaultdict(int)
        
        for test_case in validated_tests:
            test_case_json = test_case.get('test_case_json', {})
            if isinstance(test_case_json, str):
                try:
                    test_case_json = json.loads(test_case_json)
                except (json.JSONDecodeError, TypeError):
                    continue
            
            test_scenario = test_case_json.get('test_scenario', '').lower()
            request_body = test_case_json.get('request_body', {})
            
            # Check if this is an edge case test
            for edge_type, keywords in edge_case_keywords.items():
                if any(keyword in test_scenario for keyword in keywords):
                    edge_case_counter[edge_type] += 1
                    
                    # Extract edge case details
                    edge_details = self._extract_edge_case_details(request_body, edge_type)
                    if edge_details:
                        pattern = {
                            'edge_type': edge_type,
                            'scenario': test_scenario,
                            'details': edge_details,
                            'method': test_case.get('method', ''),
                            'path': test_case.get('path', ''),
                            'effectiveness_score': 0.9,  # Edge cases are valuable
                            'pattern_type': 'edge_case'
                        }
                        edge_case_patterns.append(pattern)
        
        # Add summary patterns
        for edge_type, count in edge_case_counter.items():
            if count > 0:
                pattern = {
                    'edge_type': edge_type,
                    'occurrences': count,
                    'effectiveness_score': min(count / 5.0, 1.0),
                    'pattern_type': 'edge_case_summary'
                }
                edge_case_patterns.append(pattern)
        
        return edge_case_patterns
    
    def _extract_structure_patterns(self, validated_tests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract patterns about test case structure
        
        Args:
            validated_tests: List of validated AI test case dictionaries
            
        Returns:
            List of structure patterns
        """
        structure_patterns = []
        structure_stats = {
            'has_scenario': 0,
            'has_request_body': 0,
            'has_expected_response': 0,
            'request_body_depth': [],
            'request_body_field_count': []
        }
        
        for test_case in validated_tests:
            test_case_json = test_case.get('test_case_json', {})
            if isinstance(test_case_json, str):
                try:
                    test_case_json = json.loads(test_case_json)
                except (json.JSONDecodeError, TypeError):
                    continue
            
            # Check structure completeness
            if test_case_json.get('test_scenario'):
                structure_stats['has_scenario'] += 1
            
            request_body = test_case_json.get('request_body', {})
            if request_body:
                structure_stats['has_request_body'] += 1
                if isinstance(request_body, dict):
                    structure_stats['request_body_depth'].append(self._calculate_depth(request_body))
                    structure_stats['request_body_field_count'].append(len(request_body))
            
            if test_case_json.get('expected_response'):
                structure_stats['has_expected_response'] += 1
        
        total = len(validated_tests)
        if total > 0:
            # Create structure quality pattern
            pattern = {
                'scenario_coverage': structure_stats['has_scenario'] / total,
                'request_body_coverage': structure_stats['has_request_body'] / total,
                'expected_response_coverage': structure_stats['has_expected_response'] / total,
                'avg_request_body_depth': sum(structure_stats['request_body_depth']) / len(structure_stats['request_body_depth']) if structure_stats['request_body_depth'] else 0,
                'avg_field_count': sum(structure_stats['request_body_field_count']) / len(structure_stats['request_body_field_count']) if structure_stats['request_body_field_count'] else 0,
                'effectiveness_score': (
                    (structure_stats['has_scenario'] / total) * 0.3 +
                    (structure_stats['has_request_body'] / total) * 0.4 +
                    (structure_stats['has_expected_response'] / total) * 0.3
                ),
                'pattern_type': 'structure_quality',
                'sample_size': total
            }
            structure_patterns.append(pattern)
        
        return structure_patterns
    
    def _extract_scenario_keywords(self, scenario: str) -> List[str]:
        """Extract keywords from test scenario text"""
        # Common test keywords
        keywords = []
        scenario_lower = scenario.lower()
        
        test_keywords = [
            'create', 'update', 'delete', 'get', 'list', 'search',
            'validate', 'verify', 'check', 'test',
            'success', 'failure', 'error', 'invalid',
            'empty', 'null', 'missing', 'required',
            'boundary', 'edge', 'limit', 'min', 'max'
        ]
        
        for keyword in test_keywords:
            if keyword in scenario_lower:
                keywords.append(keyword)
        
        return keywords
    
    def _find_common_keywords(self, scenarios: List[str]) -> List[str]:
        """Find common keywords across multiple scenarios"""
        keyword_sets = [set(self._extract_scenario_keywords(s)) for s in scenarios]
        if not keyword_sets:
            return []
        
        # Find intersection of all keyword sets
        if len(keyword_sets) == 1:
            common = keyword_sets[0]
        else:
            common = set.intersection(*keyword_sets)
        return list(common)
    
    def _analyze_data_structure(self, data: Any, field_usage: Dict, field_path: str):
        """Analyze data structure and track field usage"""
        if isinstance(data, dict):
            for key, value in data.items():
                new_path = f"{field_path}.{key}" if field_path else key
                
                # Initialize if not exists
                if new_path not in field_usage:
                    field_usage[new_path] = {'count': 0, 'types': Counter(), 'examples': []}
                
                field_usage[new_path]['count'] += 1
                field_usage[new_path]['types'][type(value).__name__] += 1
                
                # Store example values (limit to 5)
                if len(field_usage[new_path]['examples']) < 5:
                    if isinstance(value, (str, int, float, bool)):
                        field_usage[new_path]['examples'].append(str(value)[:50])  # Truncate long values
                
                # Recursively analyze nested structures
                if isinstance(value, (dict, list)):
                    self._analyze_data_structure(value, field_usage, new_path)
        
        elif isinstance(data, list):
            for i, item in enumerate(data):
                new_path = f"{field_path}[{i}]" if field_path else f"[{i}]"
                self._analyze_data_structure(item, field_usage, new_path)
    
    def _extract_edge_case_details(self, request_body: Any, edge_type: str) -> Optional[Dict[str, Any]]:
        """Extract details about an edge case from request body"""
        if not isinstance(request_body, dict):
            return None
        
        details = {}
        
        if edge_type == 'boundary':
            # Look for min/max values
            for key, value in request_body.items():
                if isinstance(value, (int, float)):
                    if 'min' in key.lower() or value == 0:
                        details['min_value'] = value
                    if 'max' in key.lower() or value > 1000:
                        details['max_value'] = value
        
        elif edge_type == 'empty':
            # Look for empty/null values
            empty_fields = [k for k, v in request_body.items() if v in [None, '', [], {}]]
            if empty_fields:
                details['empty_fields'] = empty_fields
        
        elif edge_type == 'invalid':
            # Look for invalid format values
            invalid_fields = []
            for key, value in request_body.items():
                if isinstance(value, str) and len(value) > 100:  # Suspiciously long
                    invalid_fields.append(key)
            if invalid_fields:
                details['invalid_fields'] = invalid_fields
        
        return details if details else None
    
    def _calculate_depth(self, data: Any, current_depth: int = 0) -> int:
        """Calculate maximum depth of nested data structure"""
        if isinstance(data, dict):
            if not data:
                return current_depth
            return max(
                self._calculate_depth(value, current_depth + 1)
                for value in data.values()
            )
        elif isinstance(data, list):
            if not data:
                return current_depth
            return max(
                self._calculate_depth(item, current_depth + 1)
                for item in data
            )
        else:
            return current_depth

