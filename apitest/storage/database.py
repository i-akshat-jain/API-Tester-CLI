"""
Local SQLite database for storing test results and history

All data is stored locally at ~/.apitest/data.db
Never synced to external servers.
"""

import sqlite3
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Database schema version for migration tracking
CURRENT_SCHEMA_VERSION = 2

# Database location (local file only)
def get_db_path() -> Path:
    """Get the path to the local SQLite database"""
    db_dir = Path.home() / '.apitest'
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / 'data.db'


class Database:
    """Local SQLite database manager for test results and history"""
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize database connection
        
        Args:
            db_path: Optional path to database file. Defaults to ~/.apitest/data.db
        """
        self.db_path = db_path or get_db_path()
        self.conn: Optional[sqlite3.Connection] = None
        self._initialize()
    
    def _initialize(self):
        """Initialize database and create schema if needed"""
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Connect to database
        self.conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            timeout=30.0
        )
        self.conn.row_factory = sqlite3.Row  # Enable column access by name
        
        # Create tables
        self._create_schema()
        
        # Run migrations if needed
        self._run_migrations()
    
    def _create_schema(self):
        """Create database schema if it doesn't exist"""
        cursor = self.conn.cursor()
        
        # Schema versions table (for tracking migrations)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_versions (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                description TEXT
            )
        """)
        
        # Test results table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schema_file TEXT NOT NULL,
                method TEXT NOT NULL,
                path TEXT NOT NULL,
                status TEXT NOT NULL,
                status_code INTEGER,
                expected_status INTEGER,
                response_time_ms REAL,
                error_message TEXT,
                schema_mismatch BOOLEAN DEFAULT 0,
                response_size_bytes INTEGER DEFAULT 0,
                auth_attempts INTEGER DEFAULT 1,
                auth_succeeded BOOLEAN DEFAULT 1,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(schema_file, method, path, timestamp)
            )
        """)
        
        # Request/response storage table (full payloads for learning)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS request_response_storage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_result_id INTEGER,
                request_method TEXT NOT NULL,
                request_path TEXT NOT NULL,
                request_headers TEXT,  -- JSON
                request_body TEXT,     -- JSON
                request_params TEXT,   -- JSON
                response_status_code INTEGER,
                response_headers TEXT, -- JSON
                response_body TEXT,    -- JSON (can be large)
                response_time_ms REAL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (test_result_id) REFERENCES test_results(id) ON DELETE CASCADE
            )
        """)
        
        # Baseline tracking table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS baselines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schema_file TEXT NOT NULL,
                method TEXT NOT NULL,
                path TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                response_time_ms REAL,
                response_schema TEXT,  -- JSON schema of response
                established_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(schema_file, method, path)
            )
        """)
        
        # Create indexes for better query performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_test_results_schema 
            ON test_results(schema_file, timestamp DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_test_results_path 
            ON test_results(method, path, timestamp DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_baselines_schema 
            ON baselines(schema_file, method, path)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_request_response_test_id 
            ON request_response_storage(test_result_id)
        """)
        
        # AI test cases table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_test_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schema_file TEXT NOT NULL,
                method TEXT NOT NULL,
                path TEXT NOT NULL,
                test_case_json TEXT NOT NULL,  -- JSON string of test case
                validation_status TEXT DEFAULT 'pending',  -- pending, approved, rejected, needs_improvement
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                version INTEGER DEFAULT 1
            )
        """)
        
        # Validation feedback table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS validation_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_case_id INTEGER NOT NULL,
                status TEXT NOT NULL,  -- approved, rejected, needs_improvement
                feedback_text TEXT,
                annotations_json TEXT,  -- JSON string of annotations
                validated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                validated_by TEXT,  -- Optional identifier (e.g., username)
                FOREIGN KEY (test_case_id) REFERENCES ai_test_cases(id) ON DELETE CASCADE
            )
        """)
        
        # AI prompts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt_name TEXT NOT NULL,
                prompt_version INTEGER NOT NULL,
                prompt_template TEXT NOT NULL,
                metadata_json TEXT,  -- JSON string of metadata
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 0,
                UNIQUE(prompt_name, prompt_version)
            )
        """)
        
        # Patterns table (for learned patterns)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_type TEXT NOT NULL,  -- e.g., 'data_generation', 'test_scenario', etc.
                pattern_data TEXT NOT NULL,  -- JSON string of pattern data
                effectiveness_score REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for AI tables
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ai_test_cases_endpoint 
            ON ai_test_cases(schema_file, method, path)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ai_test_cases_status 
            ON ai_test_cases(validation_status)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_validation_feedback_test_case 
            ON validation_feedback(test_case_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ai_prompts_name_version 
            ON ai_prompts(prompt_name, prompt_version)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ai_prompts_active 
            ON ai_prompts(is_active)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_patterns_type 
            ON patterns(pattern_type)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_patterns_effectiveness 
            ON patterns(effectiveness_score)
        """)
        
        self.conn.commit()
    
    def _run_migrations(self):
        """Run database migrations if needed"""
        cursor = self.conn.cursor()
        
        # Get current schema version
        cursor.execute("SELECT MAX(version) FROM schema_versions")
        result = cursor.fetchone()
        current_version = result[0] if result[0] is not None else 0
        
        # Run migrations if current version is less than target version
        if current_version < CURRENT_SCHEMA_VERSION:
            logger.info(f"Running database migrations from version {current_version} to {CURRENT_SCHEMA_VERSION}")
            
            # Migration 1: Initial schema (already created in _create_schema)
            if current_version < 1:
                # Schema already created, just record the version
                cursor.execute("""
                    INSERT INTO schema_versions (version, description)
                    VALUES (1, 'Initial schema with test results, request/response storage, and baselines')
                """)
                self.conn.commit()
                current_version = 1
            
            # Migration 2: Add AI-related tables
            if current_version < 2:
                self._migrate_to_v2(cursor)
                cursor.execute("""
                    INSERT INTO schema_versions (version, description)
                    VALUES (2, 'Added AI test cases, validation feedback, AI prompts, and patterns tables')
                """)
                self.conn.commit()
    
    def _migrate_to_v2(self, cursor):
        """
        Migration to version 2: Add AI-related tables
        
        Args:
            cursor: Database cursor for executing SQL
        """
        logger.info("Running migration to version 2: Adding AI-related tables")
        
        # AI test cases table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_test_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schema_file TEXT NOT NULL,
                method TEXT NOT NULL,
                path TEXT NOT NULL,
                test_case_json TEXT NOT NULL,
                validation_status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                version INTEGER DEFAULT 1
            )
        """)
        
        # Validation feedback table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS validation_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_case_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                feedback_text TEXT,
                annotations_json TEXT,
                validated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                validated_by TEXT,
                FOREIGN KEY (test_case_id) REFERENCES ai_test_cases(id) ON DELETE CASCADE
            )
        """)
        
        # AI prompts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt_name TEXT NOT NULL,
                prompt_version INTEGER NOT NULL,
                prompt_template TEXT NOT NULL,
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 0,
                UNIQUE(prompt_name, prompt_version)
            )
        """)
        
        # Patterns table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_type TEXT NOT NULL,
                pattern_data TEXT NOT NULL,
                effectiveness_score REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for AI tables
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ai_test_cases_endpoint 
            ON ai_test_cases(schema_file, method, path)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ai_test_cases_status 
            ON ai_test_cases(validation_status)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_validation_feedback_test_case 
            ON validation_feedback(test_case_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ai_prompts_name_version 
            ON ai_prompts(prompt_name, prompt_version)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ai_prompts_active 
            ON ai_prompts(is_active)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_patterns_type 
            ON patterns(pattern_type)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_patterns_effectiveness 
            ON patterns(effectiveness_score)
        """)
        
        logger.info("Migration to version 2 completed successfully")
    
    def save_test_result(self, schema_file: str, method: str, path: str, 
                        status: str, status_code: Optional[int] = None,
                        expected_status: Optional[int] = None,
                        response_time_ms: float = 0.0,
                        error_message: Optional[str] = None,
                        schema_mismatch: bool = False,
                        response_size_bytes: int = 0,
                        auth_attempts: int = 1,
                        auth_succeeded: bool = True) -> int:
        """
        Save a test result to the database
        
        Args:
            schema_file: Path or identifier for the schema file
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path
            status: Test status (pass, fail, warning, error)
            status_code: HTTP response status code
            expected_status: Expected HTTP status code
            response_time_ms: Response time in milliseconds
            error_message: Error message if test failed
            schema_mismatch: Whether schema validation failed
            response_size_bytes: Size of response in bytes
            auth_attempts: Number of auth methods tried
            auth_succeeded: Whether authentication succeeded
            
        Returns:
            ID of inserted test result
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO test_results (
                schema_file, method, path, status, status_code, expected_status,
                response_time_ms, error_message, schema_mismatch, response_size_bytes,
                auth_attempts, auth_succeeded
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            schema_file, method, path, status, status_code, expected_status,
            response_time_ms, error_message, schema_mismatch, response_size_bytes,
            auth_attempts, auth_succeeded
        ))
        self.conn.commit()
        return cursor.lastrowid
    
    def save_request_response(self, test_result_id: int, request_method: str,
                             request_path: str, request_headers: Optional[Dict[str, str]] = None,
                             request_body: Optional[Dict[str, Any]] = None,
                             request_params: Optional[Dict[str, Any]] = None,
                             response_status_code: Optional[int] = None,
                             response_headers: Optional[Dict[str, str]] = None,
                             response_body: Optional[Dict[str, Any]] = None,
                             response_time_ms: float = 0.0):
        """
        Save request/response payloads for learning
        
        Args:
            test_result_id: ID of the associated test result
            request_method: HTTP method
            request_path: API endpoint path
            request_headers: Request headers as dict
            request_body: Request body as dict
            request_params: Query parameters as dict
            response_status_code: HTTP response status code
            response_headers: Response headers as dict
            response_body: Response body as dict
            response_time_ms: Response time in milliseconds
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO request_response_storage (
                test_result_id, request_method, request_path,
                request_headers, request_body, request_params,
                response_status_code, response_headers, response_body,
                response_time_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            test_result_id, request_method, request_path,
            json.dumps(request_headers) if request_headers else None,
            json.dumps(request_body) if request_body else None,
            json.dumps(request_params) if request_params else None,
            response_status_code,
            json.dumps(response_headers) if response_headers else None,
            json.dumps(response_body) if response_body else None,
            response_time_ms
        ))
        self.conn.commit()
    
    def get_test_history(self, schema_file: Optional[str] = None,
                        method: Optional[str] = None,
                        path: Optional[str] = None,
                        limit: int = 100,
                        start_date: Optional[datetime] = None,
                        end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Get test history with optional filtering
        
        Args:
            schema_file: Filter by schema file
            method: Filter by HTTP method
            path: Filter by endpoint path
            limit: Maximum number of results to return
            start_date: Filter results after this date
            end_date: Filter results before this date
            
        Returns:
            List of test result dictionaries
        """
        cursor = self.conn.cursor()
        query = "SELECT * FROM test_results WHERE 1=1"
        params = []
        
        if schema_file:
            query += " AND schema_file = ?"
            params.append(schema_file)
        
        if method:
            query += " AND method = ?"
            params.append(method.upper())
        
        if path:
            query += " AND path = ?"
            params.append(path)
        
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date.isoformat())
        
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date.isoformat())
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        # Convert rows to dictionaries
        results = []
        for row in rows:
            results.append({
                'id': row['id'],
                'schema_file': row['schema_file'],
                'method': row['method'],
                'path': row['path'],
                'status': row['status'],
                'status_code': row['status_code'],
                'expected_status': row['expected_status'],
                'response_time_ms': row['response_time_ms'],
                'error_message': row['error_message'],
                'schema_mismatch': bool(row['schema_mismatch']),
                'response_size_bytes': row['response_size_bytes'],
                'auth_attempts': row['auth_attempts'],
                'auth_succeeded': bool(row['auth_succeeded']),
                'timestamp': row['timestamp']
            })
        
        return results
    
    def establish_baseline(self, schema_file: str, method: str, path: str,
                          status_code: int, response_time_ms: float,
                          response_schema: Optional[Dict[str, Any]] = None):
        """
        Establish or update baseline for an endpoint
        
        Args:
            schema_file: Path or identifier for the schema file
            method: HTTP method
            path: API endpoint path
            status_code: Expected status code
            response_time_ms: Expected response time
            response_schema: JSON schema of the response
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO baselines (
                schema_file, method, path, status_code, 
                response_time_ms, response_schema, established_at
            ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            schema_file, method, path, status_code,
            response_time_ms,
            json.dumps(response_schema) if response_schema else None
        ))
        self.conn.commit()
    
    def get_baseline(self, schema_file: str, method: str, path: str) -> Optional[Dict[str, Any]]:
        """
        Get baseline for an endpoint
        
        Args:
            schema_file: Path or identifier for the schema file
            method: HTTP method
            path: API endpoint path
            
        Returns:
            Baseline dictionary or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM baselines
            WHERE schema_file = ? AND method = ? AND path = ?
        """, (schema_file, method.upper(), path))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        return {
            'id': row['id'],
            'schema_file': row['schema_file'],
            'method': row['method'],
            'path': row['path'],
            'status_code': row['status_code'],
            'response_time_ms': row['response_time_ms'],
            'response_schema': json.loads(row['response_schema']) if row['response_schema'] else None,
            'established_at': row['established_at']
        }
    
    def get_all_baselines(self, schema_file: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all baselines, optionally filtered by schema file
        
        Args:
            schema_file: Optional filter by schema file
            
        Returns:
            List of baseline dictionaries
        """
        cursor = self.conn.cursor()
        
        if schema_file:
            cursor.execute("""
                SELECT * FROM baselines WHERE schema_file = ?
                ORDER BY method, path
            """, (schema_file,))
        else:
            cursor.execute("""
                SELECT * FROM baselines
                ORDER BY schema_file, method, path
            """)
        
        rows = cursor.fetchall()
        results = []
        for row in rows:
            results.append({
                'id': row['id'],
                'schema_file': row['schema_file'],
                'method': row['method'],
                'path': row['path'],
                'status_code': row['status_code'],
                'response_time_ms': row['response_time_ms'],
                'response_schema': json.loads(row['response_schema']) if row['response_schema'] else None,
                'established_at': row['established_at']
            })
        
        return results
    
    # AI Test Cases methods
    def save_ai_test_case(self, schema_file: str, method: str, path: str,
                          test_case_json: Dict[str, Any],
                          validation_status: str = 'pending',
                          version: int = 1) -> int:
        """
        Save an AI-generated test case
        
        Args:
            schema_file: Path or identifier for the schema file
            method: HTTP method
            path: API endpoint path
            test_case_json: Test case data as dictionary
            validation_status: Validation status (pending, approved, rejected, needs_improvement)
            version: Test case version number
            
        Returns:
            ID of inserted test case
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO ai_test_cases (
                schema_file, method, path, test_case_json, validation_status, version
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            schema_file, method.upper(), path,
            json.dumps(test_case_json), validation_status, version
        ))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_ai_test_case(self, test_case_id: int) -> Optional[Dict[str, Any]]:
        """Get an AI test case by ID"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM ai_test_cases WHERE id = ?", (test_case_id,))
        row = cursor.fetchone()
        if not row:
            return None
        
        return {
            'id': row['id'],
            'schema_file': row['schema_file'],
            'method': row['method'],
            'path': row['path'],
            'test_case_json': json.loads(row['test_case_json']),
            'validation_status': row['validation_status'],
            'created_at': row['created_at'],
            'version': row['version']
        }
    
    def get_ai_test_cases_by_endpoint(self, schema_file: str, method: str,
                                      path: str) -> List[Dict[str, Any]]:
        """Get all AI test cases for a specific endpoint"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM ai_test_cases
            WHERE schema_file = ? AND method = ? AND path = ?
            ORDER BY created_at DESC
        """, (schema_file, method.upper(), path))
        
        rows = cursor.fetchall()
        results = []
        for row in rows:
            results.append({
                'id': row['id'],
                'schema_file': row['schema_file'],
                'method': row['method'],
                'path': row['path'],
                'test_case_json': json.loads(row['test_case_json']),
                'validation_status': row['validation_status'],
                'created_at': row['created_at'],
                'version': row['version']
            })
        return results
    
    def get_validated_ai_test_cases(self, schema_file: Optional[str] = None,
                                    limit: int = 100) -> List[Dict[str, Any]]:
        """Get validated (approved) AI test cases"""
        cursor = self.conn.cursor()
        query = "SELECT * FROM ai_test_cases WHERE validation_status = 'approved'"
        params = []
        
        if schema_file:
            query += " AND schema_file = ?"
            params.append(schema_file)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        results = []
        for row in rows:
            results.append({
                'id': row['id'],
                'schema_file': row['schema_file'],
                'method': row['method'],
                'path': row['path'],
                'test_case_json': json.loads(row['test_case_json']),
                'validation_status': row['validation_status'],
                'created_at': row['created_at'],
                'version': row['version']
            })
        return results
    
    def get_ai_test_cases_by_status(self, status: str, schema_file: Optional[str] = None,
                                    limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get AI test cases by validation status
        
        Args:
            status: Validation status ('pending', 'approved', 'rejected', 'needs_improvement')
            schema_file: Optional schema file to filter by
            limit: Maximum number of results to return
            
        Returns:
            List of test case dictionaries
        """
        cursor = self.conn.cursor()
        query = "SELECT * FROM ai_test_cases WHERE validation_status = ?"
        params = [status]
        
        if schema_file:
            query += " AND schema_file = ?"
            params.append(schema_file)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        results = []
        for row in rows:
            results.append({
                'id': row['id'],
                'schema_file': row['schema_file'],
                'method': row['method'],
                'path': row['path'],
                'test_case_json': json.loads(row['test_case_json']),
                'validation_status': row['validation_status'],
                'created_at': row['created_at'],
                'version': row['version']
            })
        return results
    
    def get_all_ai_test_cases(self, schema_file: Optional[str] = None,
                              limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Get all AI test cases (regardless of status)
        
        Args:
            schema_file: Optional schema file to filter by
            limit: Maximum number of results to return
            
        Returns:
            List of test case dictionaries
        """
        cursor = self.conn.cursor()
        query = "SELECT * FROM ai_test_cases"
        params = []
        
        if schema_file:
            query += " WHERE schema_file = ?"
            params.append(schema_file)
        
        query += " ORDER BY schema_file, method, path, created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        results = []
        for row in rows:
            results.append({
                'id': row['id'],
                'schema_file': row['schema_file'],
                'method': row['method'],
                'path': row['path'],
                'test_case_json': json.loads(row['test_case_json']),
                'validation_status': row['validation_status'],
                'created_at': row['created_at'],
                'version': row['version']
            })
        return results
    
    def update_ai_test_case_validation_status(self, test_case_id: int,
                                              status: str) -> None:
        """Update validation status of an AI test case"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE ai_test_cases
            SET validation_status = ?
            WHERE id = ?
        """, (status, test_case_id))
        self.conn.commit()
    
    def delete_ai_test_case(self, test_case_id: int) -> None:
        """Delete an AI test case"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM ai_test_cases WHERE id = ?", (test_case_id,))
        self.conn.commit()
    
    # Validation Feedback methods
    def save_validation_feedback(self, test_case_id: int, status: str,
                                 feedback_text: Optional[str] = None,
                                 annotations: Optional[Dict[str, Any]] = None,
                                 validated_by: Optional[str] = None) -> int:
        """Save validation feedback for an AI test case"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO validation_feedback (
                test_case_id, status, feedback_text, annotations_json, validated_by
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            test_case_id, status, feedback_text,
            json.dumps(annotations) if annotations else None,
            validated_by
        ))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_validation_feedback(self, validation_id: int) -> Optional[Dict[str, Any]]:
        """Get validation feedback by ID"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM validation_feedback WHERE id = ?", (validation_id,))
        row = cursor.fetchone()
        if not row:
            return None
        
        return {
            'id': row['id'],
            'test_case_id': row['test_case_id'],
            'status': row['status'],
            'feedback_text': row['feedback_text'],
            'annotations_json': json.loads(row['annotations_json']) if row['annotations_json'] else None,
            'validated_at': row['validated_at'],
            'validated_by': row['validated_by']
        }
    
    def get_validations_by_test_case(self, test_case_id: int) -> List[Dict[str, Any]]:
        """Get all validation feedback for a test case"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM validation_feedback
            WHERE test_case_id = ?
            ORDER BY validated_at DESC
        """, (test_case_id,))
        
        rows = cursor.fetchall()
        results = []
        for row in rows:
            results.append({
                'id': row['id'],
                'test_case_id': row['test_case_id'],
                'status': row['status'],
                'feedback_text': row['feedback_text'],
                'annotations_json': json.loads(row['annotations_json']) if row['annotations_json'] else None,
                'validated_at': row['validated_at'],
                'validated_by': row['validated_by']
            })
        return results
    
    def get_feedback_corpus(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get feedback corpus for learning"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT vf.*, atc.schema_file, atc.method, atc.path
            FROM validation_feedback vf
            JOIN ai_test_cases atc ON vf.test_case_id = atc.id
            ORDER BY vf.validated_at DESC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        results = []
        for row in rows:
            results.append({
                'id': row['id'],
                'test_case_id': row['test_case_id'],
                'status': row['status'],
                'feedback_text': row['feedback_text'],
                'annotations_json': json.loads(row['annotations_json']) if row['annotations_json'] else None,
                'validated_at': row['validated_at'],
                'validated_by': row['validated_by'],
                'schema_file': row['schema_file'],
                'method': row['method'],
                'path': row['path']
            })
        return results
    
    def get_feedback_stats(self) -> Dict[str, Any]:
        """Get statistics about validation feedback"""
        cursor = self.conn.cursor()
        
        # Count by status
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM validation_feedback
            GROUP BY status
        """)
        status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
        
        # Total count
        cursor.execute("SELECT COUNT(*) as total FROM validation_feedback")
        total = cursor.fetchone()['total']
        
        return {
            'total': total,
            'by_status': status_counts
        }
    
    # AI Prompts methods
    def save_ai_prompt(self, prompt_name: str, prompt_template: str,
                       metadata: Optional[Dict[str, Any]] = None,
                       version: Optional[int] = None) -> int:
        """Save an AI prompt template"""
        cursor = self.conn.cursor()
        
        # Get next version if not specified
        if version is None:
            cursor.execute("""
                SELECT MAX(prompt_version) as max_version
                FROM ai_prompts
                WHERE prompt_name = ?
            """, (prompt_name,))
            result = cursor.fetchone()
            version = (result['max_version'] or 0) + 1
        
        cursor.execute("""
            INSERT INTO ai_prompts (
                prompt_name, prompt_version, prompt_template, metadata_json
            ) VALUES (?, ?, ?, ?)
        """, (
            prompt_name, version, prompt_template,
            json.dumps(metadata) if metadata else None
        ))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_ai_prompt(self, prompt_name: str, version: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Get an AI prompt by name and version"""
        cursor = self.conn.cursor()
        if version:
            cursor.execute("""
                SELECT * FROM ai_prompts
                WHERE prompt_name = ? AND prompt_version = ?
            """, (prompt_name, version))
        else:
            cursor.execute("""
                SELECT * FROM ai_prompts
                WHERE prompt_name = ? AND is_active = 1
                ORDER BY prompt_version DESC
                LIMIT 1
            """, (prompt_name,))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        return {
            'id': row['id'],
            'prompt_name': row['prompt_name'],
            'prompt_version': row['prompt_version'],
            'prompt_template': row['prompt_template'],
            'metadata_json': json.loads(row['metadata_json']) if row['metadata_json'] else None,
            'created_at': row['created_at'],
            'is_active': bool(row['is_active'])
        }
    
    def get_latest_ai_prompt(self, prompt_name: str) -> Optional[Dict[str, Any]]:
        """Get the latest version of an AI prompt"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM ai_prompts
            WHERE prompt_name = ?
            ORDER BY prompt_version DESC
            LIMIT 1
        """, (prompt_name,))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        return {
            'id': row['id'],
            'prompt_name': row['prompt_name'],
            'prompt_version': row['prompt_version'],
            'prompt_template': row['prompt_template'],
            'metadata_json': json.loads(row['metadata_json']) if row['metadata_json'] else None,
            'created_at': row['created_at'],
            'is_active': bool(row['is_active'])
        }
    
    def list_ai_prompt_versions(self, prompt_name: str) -> List[Dict[str, Any]]:
        """List all versions of an AI prompt"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM ai_prompts
            WHERE prompt_name = ?
            ORDER BY prompt_version DESC
        """, (prompt_name,))
        
        rows = cursor.fetchall()
        results = []
        for row in rows:
            results.append({
                'id': row['id'],
                'prompt_name': row['prompt_name'],
                'prompt_version': row['prompt_version'],
                'prompt_template': row['prompt_template'],
                'metadata_json': json.loads(row['metadata_json']) if row['metadata_json'] else None,
                'created_at': row['created_at'],
                'is_active': bool(row['is_active'])
            })
        return results
    
    def set_active_ai_prompt(self, prompt_name: str, version: int) -> None:
        """Set a specific version of a prompt as active"""
        cursor = self.conn.cursor()
        # First, deactivate all versions of this prompt
        cursor.execute("""
            UPDATE ai_prompts
            SET is_active = 0
            WHERE prompt_name = ?
        """, (prompt_name,))
        # Then activate the specified version
        cursor.execute("""
            UPDATE ai_prompts
            SET is_active = 1
            WHERE prompt_name = ? AND prompt_version = ?
        """, (prompt_name, version))
        self.conn.commit()
    
    def get_active_ai_prompt(self, prompt_name: str) -> Optional[Dict[str, Any]]:
        """Get the active version of an AI prompt"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM ai_prompts
            WHERE prompt_name = ? AND is_active = 1
            ORDER BY prompt_version DESC
            LIMIT 1
        """, (prompt_name,))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        return {
            'id': row['id'],
            'prompt_name': row['prompt_name'],
            'prompt_version': row['prompt_version'],
            'prompt_template': row['prompt_template'],
            'metadata_json': json.loads(row['metadata_json']) if row['metadata_json'] else None,
            'created_at': row['created_at'],
            'is_active': bool(row['is_active'])
        }
    
    # Patterns methods
    def save_pattern(self, pattern_type: str, pattern_data: Dict[str, Any],
                     effectiveness_score: float = 0.0) -> int:
        """Save a learned pattern"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO patterns (
                pattern_type, pattern_data, effectiveness_score
            ) VALUES (?, ?, ?)
        """, (
            pattern_type, json.dumps(pattern_data), effectiveness_score
        ))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_patterns(self, pattern_type: Optional[str] = None,
                     min_effectiveness: float = 0.0) -> List[Dict[str, Any]]:
        """Get patterns, optionally filtered by type and effectiveness"""
        cursor = self.conn.cursor()
        query = "SELECT * FROM patterns WHERE effectiveness_score >= ?"
        params = [min_effectiveness]
        
        if pattern_type:
            query += " AND pattern_type = ?"
            params.append(pattern_type)
        
        query += " ORDER BY effectiveness_score DESC, created_at DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        results = []
        for row in rows:
            results.append({
                'id': row['id'],
                'pattern_type': row['pattern_type'],
                'pattern_data': json.loads(row['pattern_data']),
                'effectiveness_score': row['effectiveness_score'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            })
        return results
    
    def update_pattern_effectiveness(self, pattern_id: int, score: float) -> None:
        """Update effectiveness score of a pattern"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE patterns
            SET effectiveness_score = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (score, pattern_id))
        self.conn.commit()
    
    def delete_pattern(self, pattern_id: int) -> None:
        """Delete a pattern"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM patterns WHERE id = ?", (pattern_id,))
        self.conn.commit()
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
    
    def __del__(self):
        """Cleanup on deletion"""
        self.close()


class ResultsNamespace:
    """Namespace for test results and history operations"""
    
    def __init__(self, db: Database):
        self._db = db
    
    def save_test_result(self, schema_file: str, method: str, path: str, 
                        status: str, status_code: Optional[int] = None,
                        expected_status: Optional[int] = None,
                        response_time_ms: float = 0.0,
                        error_message: Optional[str] = None,
                        schema_mismatch: bool = False,
                        response_size_bytes: int = 0,
                        auth_attempts: int = 1,
                        auth_succeeded: bool = True) -> int:
        """Save a test result"""
        return self._db.save_test_result(
            schema_file, method, path, status, status_code, expected_status,
            response_time_ms, error_message, schema_mismatch, response_size_bytes,
            auth_attempts, auth_succeeded
        )
    
    def save_request_response(self, test_result_id: int, request_method: str,
                             request_path: str, request_headers: Optional[Dict[str, str]] = None,
                             request_body: Optional[Dict[str, Any]] = None,
                             request_params: Optional[Dict[str, Any]] = None,
                             response_status_code: Optional[int] = None,
                             response_headers: Optional[Dict[str, str]] = None,
                             response_body: Optional[Dict[str, Any]] = None,
                             response_time_ms: float = 0.0):
        """Save request/response payloads"""
        return self._db.save_request_response(
            test_result_id, request_method, request_path, request_headers,
            request_body, request_params, response_status_code, response_headers,
            response_body, response_time_ms
        )
    
    def get_test_history(self, schema_file: Optional[str] = None,
                        method: Optional[str] = None,
                        path: Optional[str] = None,
                        limit: int = 100,
                        start_date: Optional[datetime] = None,
                        end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get test history with optional filtering"""
        return self._db.get_test_history(
            schema_file, method, path, limit, start_date, end_date
        )


class BaselinesNamespace:
    """Namespace for baseline operations"""
    
    def __init__(self, db: Database):
        self._db = db
    
    def establish_baseline(self, schema_file: str, method: str, path: str,
                          status_code: int, response_time_ms: float,
                          response_schema: Optional[Dict[str, Any]] = None):
        """Establish or update baseline for an endpoint"""
        return self._db.establish_baseline(
            schema_file, method, path, status_code, response_time_ms, response_schema
        )
    
    def get_baseline(self, schema_file: str, method: str, path: str) -> Optional[Dict[str, Any]]:
        """Get baseline for an endpoint"""
        return self._db.get_baseline(schema_file, method, path)
    
    def get_all_baselines(self, schema_file: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all baselines, optionally filtered by schema file"""
        return self._db.get_all_baselines(schema_file)


class AITestsNamespace:
    """Namespace for AI test cases operations"""
    
    def __init__(self, db: Database):
        self._db = db
    
    def save_test_case(self, schema_file: str, method: str, path: str,
                      test_case_json: Dict[str, Any],
                      validation_status: str = 'pending') -> int:
        """Save an AI-generated test case"""
        return self._db.save_ai_test_case(
            schema_file, method, path, test_case_json, validation_status
        )
    
    def get_test_case(self, test_case_id: int) -> Optional[Dict[str, Any]]:
        """Get an AI test case by ID"""
        return self._db.get_ai_test_case(test_case_id)
    
    def get_test_cases_by_endpoint(self, schema_file: str, method: str,
                                   path: str) -> List[Dict[str, Any]]:
        """Get all AI test cases for a specific endpoint"""
        return self._db.get_ai_test_cases_by_endpoint(schema_file, method, path)
    
    def get_validated_test_cases(self, schema_file: Optional[str] = None,
                                 limit: int = 100) -> List[Dict[str, Any]]:
        """Get validated (approved) AI test cases"""
        return self._db.get_validated_ai_test_cases(schema_file, limit)
    
    def get_test_cases_by_status(self, status: str, schema_file: Optional[str] = None,
                                 limit: int = 100) -> List[Dict[str, Any]]:
        """Get AI test cases by validation status"""
        return self._db.get_ai_test_cases_by_status(status, schema_file, limit)
    
    def get_all_test_cases(self, schema_file: Optional[str] = None,
                           limit: int = 1000) -> List[Dict[str, Any]]:
        """Get all AI test cases (regardless of status)"""
        return self._db.get_all_ai_test_cases(schema_file, limit)
    
    def update_validation_status(self, test_case_id: int, status: str) -> None:
        """Update validation status of an AI test case"""
        return self._db.update_ai_test_case_validation_status(test_case_id, status)
    
    def delete_test_case(self, test_case_id: int) -> None:
        """Delete an AI test case"""
        return self._db.delete_ai_test_case(test_case_id)


class ValidationFeedbackNamespace:
    """Namespace for validation feedback operations"""
    
    def __init__(self, db: Database):
        self._db = db
    
    def save_validation(self, test_case_id: int, status: str,
                       feedback_text: Optional[str] = None,
                       annotations: Optional[Dict[str, Any]] = None,
                       validated_by: Optional[str] = None) -> int:
        """Save validation feedback for an AI test case"""
        return self._db.save_validation_feedback(
            test_case_id, status, feedback_text, annotations, validated_by
        )
    
    def get_validation(self, validation_id: int) -> Optional[Dict[str, Any]]:
        """Get validation feedback by ID"""
        return self._db.get_validation_feedback(validation_id)
    
    def get_validations_by_test_case(self, test_case_id: int) -> List[Dict[str, Any]]:
        """Get all validation feedback for a test case"""
        return self._db.get_validations_by_test_case(test_case_id)
    
    def get_feedback_corpus(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get feedback corpus for learning"""
        return self._db.get_feedback_corpus(limit)
    
    def get_feedback_stats(self) -> Dict[str, Any]:
        """Get statistics about validation feedback"""
        return self._db.get_feedback_stats()


class AIPromptsNamespace:
    """Namespace for AI prompts operations"""
    
    def __init__(self, db: Database):
        self._db = db
    
    def save_prompt(self, prompt_name: str, prompt_template: str,
                   metadata: Optional[Dict[str, Any]] = None,
                   version: Optional[int] = None) -> int:
        """Save an AI prompt template"""
        return self._db.save_ai_prompt(prompt_name, prompt_template, metadata, version)
    
    def get_prompt(self, prompt_name: str, version: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Get an AI prompt by name and version"""
        return self._db.get_ai_prompt(prompt_name, version)
    
    def get_latest_prompt(self, prompt_name: str) -> Optional[Dict[str, Any]]:
        """Get the latest version of an AI prompt"""
        return self._db.get_latest_ai_prompt(prompt_name)
    
    def list_prompt_versions(self, prompt_name: str) -> List[Dict[str, Any]]:
        """List all versions of an AI prompt"""
        return self._db.list_ai_prompt_versions(prompt_name)
    
    def set_active_prompt(self, prompt_name: str, version: int) -> None:
        """Set a specific version of a prompt as active"""
        return self._db.set_active_ai_prompt(prompt_name, version)
    
    def get_active_prompt(self, prompt_name: str) -> Optional[Dict[str, Any]]:
        """Get the active version of an AI prompt"""
        return self._db.get_active_ai_prompt(prompt_name)


class PatternsNamespace:
    """Namespace for patterns operations"""
    
    def __init__(self, db: Database):
        self._db = db
    
    def save_pattern(self, pattern_type: str, pattern_data: Dict[str, Any],
                     effectiveness_score: float = 0.0) -> int:
        """Save a learned pattern"""
        return self._db.save_pattern(pattern_type, pattern_data, effectiveness_score)
    
    def get_patterns(self, pattern_type: Optional[str] = None,
                     min_effectiveness: float = 0.0) -> List[Dict[str, Any]]:
        """Get patterns, optionally filtered by type and effectiveness"""
        return self._db.get_patterns(pattern_type, min_effectiveness)
    
    def update_pattern_effectiveness(self, pattern_id: int, score: float) -> None:
        """Update effectiveness score of a pattern"""
        return self._db.update_pattern_effectiveness(pattern_id, score)
    
    def delete_pattern(self, pattern_id: int) -> None:
        """Delete a pattern"""
        return self._db.delete_pattern(pattern_id)


class Storage:
    """Unified storage interface with namespaces for all persistence operations"""
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize unified storage
        
        Args:
            db_path: Optional path to database file. Defaults to ~/.apitest/data.db
        """
        self._db = Database(db_path)
        self.results = ResultsNamespace(self._db)
        self.baselines = BaselinesNamespace(self._db)
        self.ai_tests = AITestsNamespace(self._db)
        self.validation_feedback = ValidationFeedbackNamespace(self._db)
        self.ai_prompts = AIPromptsNamespace(self._db)
        self.patterns = PatternsNamespace(self._db)
    
    def close(self):
        """Close database connection"""
        self._db.close()
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
    
    def __del__(self):
        """Cleanup on deletion"""
        self.close()

