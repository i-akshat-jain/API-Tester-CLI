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
CURRENT_SCHEMA_VERSION = 1

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

