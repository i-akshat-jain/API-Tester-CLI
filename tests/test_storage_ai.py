"""
Tests for AI storage functionality (Phase 0)

Tests database schema, namespaces, and test case library.
"""

import pytest
import json
import tempfile
from pathlib import Path
from apitest.storage.database import Database, Storage, CURRENT_SCHEMA_VERSION
from apitest.storage.test_case_library import (
    save_test_case_to_library,
    load_test_case_from_library,
    list_test_cases_in_library,
    get_test_cases_by_endpoint,
    delete_test_case_from_library,
    get_library_dir
)


class TestDatabaseSchema:
    """Test database schema and migrations"""
    
    def test_schema_version(self):
        """Test that schema version is 2"""
        assert CURRENT_SCHEMA_VERSION == 2
    
    def test_database_initialization(self, tmp_path):
        """Test database initialization creates all tables"""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        
        cursor = db.conn.cursor()
        
        # Check that all tables exist
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name IN (
                'test_results', 'request_response_storage', 'baselines',
                'ai_test_cases', 'validation_feedback', 'ai_prompts', 'patterns',
                'schema_versions'
            )
        """)
        tables = {row[0] for row in cursor.fetchall()}
        
        expected_tables = {
            'test_results', 'request_response_storage', 'baselines',
            'ai_test_cases', 'validation_feedback', 'ai_prompts', 'patterns',
            'schema_versions'
        }
        assert tables == expected_tables
        
        db.close()
    
    def test_migration_to_v2(self, tmp_path):
        """Test migration from v1 to v2"""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        
        cursor = db.conn.cursor()
        
        # Check schema version was recorded
        cursor.execute("SELECT MAX(version) FROM schema_versions")
        version = cursor.fetchone()[0]
        assert version == 2
        
        # Check AI tables were created
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ai_test_cases'")
        assert cursor.fetchone() is not None
        
        db.close()


class TestAITestsNamespace:
    """Test AITestsNamespace"""
    
    def test_save_and_get_test_case(self, tmp_path):
        """Test saving and retrieving AI test case"""
        storage = Storage(tmp_path / "test.db")
        
        test_case_json = {
            'method': 'POST',
            'path': '/users',
            'request_body': {'name': 'Test User', 'email': 'test@example.com'},
            'expected_response': {'status': 201}
        }
        
        test_case_id = storage.ai_tests.save_test_case(
            schema_file='test.yaml',
            method='POST',
            path='/users',
            test_case_json=test_case_json,
            validation_status='pending'
        )
        
        assert test_case_id > 0
        
        # Retrieve test case
        retrieved = storage.ai_tests.get_test_case(test_case_id)
        assert retrieved is not None
        assert retrieved['schema_file'] == 'test.yaml'
        assert retrieved['method'] == 'POST'
        assert retrieved['path'] == '/users'
        assert retrieved['test_case_json'] == test_case_json
        assert retrieved['validation_status'] == 'pending'
        
        storage.close()
    
    def test_get_test_cases_by_endpoint(self, tmp_path):
        """Test getting test cases by endpoint"""
        storage = Storage(tmp_path / "test.db")
        
        test_case_json = {'request_body': {'name': 'Test'}}
        
        # Save multiple test cases
        storage.ai_tests.save_test_case('test.yaml', 'POST', '/users', test_case_json)
        storage.ai_tests.save_test_case('test.yaml', 'POST', '/users', test_case_json)
        storage.ai_tests.save_test_case('test.yaml', 'GET', '/users', test_case_json)
        
        # Get test cases for POST /users
        test_cases = storage.ai_tests.get_test_cases_by_endpoint('test.yaml', 'POST', '/users')
        assert len(test_cases) == 2
        assert all(tc['method'] == 'POST' for tc in test_cases)
        assert all(tc['path'] == '/users' for tc in test_cases)
        
        storage.close()
    
    def test_update_validation_status(self, tmp_path):
        """Test updating validation status"""
        storage = Storage(tmp_path / "test.db")
        
        test_case_id = storage.ai_tests.save_test_case(
            'test.yaml', 'POST', '/users', {'test': 'data'}, 'pending'
        )
        
        storage.ai_tests.update_validation_status(test_case_id, 'approved')
        
        test_case = storage.ai_tests.get_test_case(test_case_id)
        assert test_case['validation_status'] == 'approved'
        
        storage.close()
    
    def test_get_validated_test_cases(self, tmp_path):
        """Test getting validated test cases"""
        storage = Storage(tmp_path / "test.db")
        
        # Save test cases with different statuses
        storage.ai_tests.save_test_case('test.yaml', 'POST', '/users', {'test': '1'}, 'pending')
        storage.ai_tests.save_test_case('test.yaml', 'POST', '/posts', {'test': '2'}, 'approved')
        storage.ai_tests.save_test_case('test.yaml', 'GET', '/users', {'test': '3'}, 'approved')
        
        validated = storage.ai_tests.get_validated_test_cases()
        assert len(validated) == 2
        assert all(tc['validation_status'] == 'approved' for tc in validated)
        
        storage.close()
    
    def test_delete_test_case(self, tmp_path):
        """Test deleting test case"""
        storage = Storage(tmp_path / "test.db")
        
        test_case_id = storage.ai_tests.save_test_case(
            'test.yaml', 'POST', '/users', {'test': 'data'}
        )
        
        storage.ai_tests.delete_test_case(test_case_id)
        
        test_case = storage.ai_tests.get_test_case(test_case_id)
        assert test_case is None
        
        storage.close()


class TestValidationFeedbackNamespace:
    """Test ValidationFeedbackNamespace"""
    
    def test_save_and_get_validation(self, tmp_path):
        """Test saving and retrieving validation feedback"""
        storage = Storage(tmp_path / "test.db")
        
        # Create a test case first
        test_case_id = storage.ai_tests.save_test_case(
            'test.yaml', 'POST', '/users', {'test': 'data'}
        )
        
        # Save validation feedback
        validation_id = storage.validation_feedback.save_validation(
            test_case_id=test_case_id,
            status='approved',
            feedback_text='Looks good!',
            annotations={'note': 'Well structured'},
            validated_by='test_user'
        )
        
        assert validation_id > 0
        
        # Retrieve validation
        validation = storage.validation_feedback.get_validation(validation_id)
        assert validation is not None
        assert validation['status'] == 'approved'
        assert validation['feedback_text'] == 'Looks good!'
        assert validation['annotations_json'] == {'note': 'Well structured'}
        assert validation['validated_by'] == 'test_user'
        
        storage.close()
    
    def test_get_validations_by_test_case(self, tmp_path):
        """Test getting all validations for a test case"""
        storage = Storage(tmp_path / "test.db")
        
        test_case_id = storage.ai_tests.save_test_case(
            'test.yaml', 'POST', '/users', {'test': 'data'}
        )
        
        # Save multiple validations
        storage.validation_feedback.save_validation(test_case_id, 'rejected', 'First try')
        storage.validation_feedback.save_validation(test_case_id, 'approved', 'Second try')
        
        validations = storage.validation_feedback.get_validations_by_test_case(test_case_id)
        assert len(validations) == 2
        
        storage.close()
    
    def test_get_feedback_corpus(self, tmp_path):
        """Test getting feedback corpus"""
        storage = Storage(tmp_path / "test.db")
        
        test_case_id = storage.ai_tests.save_test_case(
            'test.yaml', 'POST', '/users', {'test': 'data'}
        )
        
        storage.validation_feedback.save_validation(test_case_id, 'approved', 'Good')
        
        corpus = storage.validation_feedback.get_feedback_corpus()
        assert len(corpus) >= 1
        assert corpus[0]['schema_file'] == 'test.yaml'
        
        storage.close()
    
    def test_get_feedback_stats(self, tmp_path):
        """Test getting feedback statistics"""
        storage = Storage(tmp_path / "test.db")
        
        test_case_id = storage.ai_tests.save_test_case(
            'test.yaml', 'POST', '/users', {'test': 'data'}
        )
        
        storage.validation_feedback.save_validation(test_case_id, 'approved', 'Good')
        storage.validation_feedback.save_validation(test_case_id, 'rejected', 'Bad')
        
        stats = storage.validation_feedback.get_feedback_stats()
        assert stats['total'] >= 2
        assert 'approved' in stats['by_status']
        assert 'rejected' in stats['by_status']
        
        storage.close()


class TestAIPromptsNamespace:
    """Test AIPromptsNamespace"""
    
    def test_save_and_get_prompt(self, tmp_path):
        """Test saving and retrieving AI prompt"""
        storage = Storage(tmp_path / "test.db")
        
        prompt_id = storage.ai_prompts.save_prompt(
            prompt_name='test_generation_basic',
            prompt_template='Generate test for {{method}} {{path}}',
            metadata={'version': '1.0', 'author': 'test'}
        )
        
        assert prompt_id > 0
        
        # Get prompt
        prompt = storage.ai_prompts.get_prompt('test_generation_basic', version=1)
        assert prompt is not None
        assert prompt['prompt_template'] == 'Generate test for {{method}} {{path}}'
        assert prompt['metadata_json'] == {'version': '1.0', 'author': 'test'}
        
        storage.close()
    
    def test_prompt_versioning(self, tmp_path):
        """Test prompt versioning"""
        storage = Storage(tmp_path / "test.db")
        
        # Save version 1
        storage.ai_prompts.save_prompt('test_prompt', 'Template v1', version=1)
        
        # Save version 2 (auto-increment)
        storage.ai_prompts.save_prompt('test_prompt', 'Template v2')
        
        # Get latest
        latest = storage.ai_prompts.get_latest_prompt('test_prompt')
        assert latest['prompt_version'] == 2
        assert latest['prompt_template'] == 'Template v2'
        
        storage.close()
    
    def test_set_active_prompt(self, tmp_path):
        """Test setting active prompt"""
        storage = Storage(tmp_path / "test.db")
        
        storage.ai_prompts.save_prompt('test_prompt', 'Template v1', version=1)
        storage.ai_prompts.save_prompt('test_prompt', 'Template v2', version=2)
        
        storage.ai_prompts.set_active_prompt('test_prompt', 2)
        
        active = storage.ai_prompts.get_active_prompt('test_prompt')
        assert active['prompt_version'] == 2
        assert active['is_active'] is True
        
        storage.close()
    
    def test_list_prompt_versions(self, tmp_path):
        """Test listing prompt versions"""
        storage = Storage(tmp_path / "test.db")
        
        storage.ai_prompts.save_prompt('test_prompt', 'Template v1', version=1)
        storage.ai_prompts.save_prompt('test_prompt', 'Template v2', version=2)
        storage.ai_prompts.save_prompt('test_prompt', 'Template v3', version=3)
        
        versions = storage.ai_prompts.list_prompt_versions('test_prompt')
        assert len(versions) == 3
        assert versions[0]['prompt_version'] == 3  # Latest first
        
        storage.close()


class TestPatternsNamespace:
    """Test PatternsNamespace"""
    
    def test_save_and_get_pattern(self, tmp_path):
        """Test saving and retrieving pattern"""
        storage = Storage(tmp_path / "test.db")
        
        pattern_data = {
            'type': 'email_format',
            'pattern': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        }
        
        pattern_id = storage.patterns.save_pattern(
            pattern_type='data_generation',
            pattern_data=pattern_data,
            effectiveness_score=0.95
        )
        
        assert pattern_id > 0
        
        # Get patterns
        patterns = storage.patterns.get_patterns(pattern_type='data_generation')
        assert len(patterns) >= 1
        assert patterns[0]['pattern_data'] == pattern_data
        assert patterns[0]['effectiveness_score'] == 0.95
        
        storage.close()
    
    def test_filter_patterns_by_effectiveness(self, tmp_path):
        """Test filtering patterns by effectiveness score"""
        storage = Storage(tmp_path / "test.db")
        
        storage.patterns.save_pattern('test_type', {'data': '1'}, 0.3)
        storage.patterns.save_pattern('test_type', {'data': '2'}, 0.7)
        storage.patterns.save_pattern('test_type', {'data': '3'}, 0.9)
        
        high_quality = storage.patterns.get_patterns(min_effectiveness=0.7)
        assert len(high_quality) == 2
        assert all(p['effectiveness_score'] >= 0.7 for p in high_quality)
        
        storage.close()
    
    def test_update_pattern_effectiveness(self, tmp_path):
        """Test updating pattern effectiveness"""
        storage = Storage(tmp_path / "test.db")
        
        pattern_id = storage.patterns.save_pattern(
            'test_type', {'data': 'test'}, 0.5
        )
        
        storage.patterns.update_pattern_effectiveness(pattern_id, 0.8)
        
        patterns = storage.patterns.get_patterns()
        updated = next(p for p in patterns if p['id'] == pattern_id)
        assert updated['effectiveness_score'] == 0.8
        
        storage.close()
    
    def test_delete_pattern(self, tmp_path):
        """Test deleting pattern"""
        storage = Storage(tmp_path / "test.db")
        
        pattern_id = storage.patterns.save_pattern('test_type', {'data': 'test'})
        
        storage.patterns.delete_pattern(pattern_id)
        
        patterns = storage.patterns.get_patterns()
        assert not any(p['id'] == pattern_id for p in patterns)
        
        storage.close()


class TestTestCaseLibrary:
    """Test test case library functions"""
    
    def test_save_and_load_test_case(self, tmp_path, monkeypatch):
        """Test saving and loading test case from library"""
        # Mock library directory to use tmp_path
        library_dir = tmp_path / 'library'
        library_dir.mkdir()
        monkeypatch.setattr('apitest.storage.test_case_library.get_library_dir', lambda: library_dir)
        
        test_case = {
            'schema_file': 'test.yaml',
            'method': 'POST',
            'path': '/users',
            'test_case_json': {'name': 'Test User'},
            'validation_status': 'approved',
            'version': 1
        }
        
        file_path = save_test_case_to_library(test_case)
        assert file_path.exists()
        
        loaded = load_test_case_from_library(file_path.name)
        assert loaded == test_case
    
    def test_list_test_cases(self, tmp_path, monkeypatch):
        """Test listing test cases in library"""
        library_dir = tmp_path / 'library'
        library_dir.mkdir()
        monkeypatch.setattr('apitest.storage.test_case_library.get_library_dir', lambda: library_dir)
        
        test_case1 = {'schema_file': 'test1.yaml', 'method': 'POST', 'path': '/users', 'test_case_json': {}, 'validation_status': 'approved'}
        test_case2 = {'schema_file': 'test2.yaml', 'method': 'GET', 'path': '/posts', 'test_case_json': {}, 'validation_status': 'approved'}
        
        save_test_case_to_library(test_case1)
        save_test_case_to_library(test_case2)
        
        files = list_test_cases_in_library()
        assert len(files) == 2
    
    def test_get_test_cases_by_endpoint(self, tmp_path, monkeypatch):
        """Test getting test cases by endpoint"""
        library_dir = tmp_path / 'library'
        library_dir.mkdir()
        monkeypatch.setattr('apitest.storage.test_case_library.get_library_dir', lambda: library_dir)
        
        test_case1 = {'schema_file': 'test.yaml', 'method': 'POST', 'path': '/users', 'test_case_json': {}, 'validation_status': 'approved'}
        test_case2 = {'schema_file': 'test.yaml', 'method': 'POST', 'path': '/users', 'test_case_json': {}, 'validation_status': 'approved'}
        test_case3 = {'schema_file': 'test.yaml', 'method': 'GET', 'path': '/users', 'test_case_json': {}, 'validation_status': 'approved'}
        
        save_test_case_to_library(test_case1)
        save_test_case_to_library(test_case2)
        save_test_case_to_library(test_case3)
        
        test_cases = get_test_cases_by_endpoint('test.yaml', 'POST', '/users')
        assert len(test_cases) == 2
    
    def test_delete_test_case(self, tmp_path, monkeypatch):
        """Test deleting test case from library"""
        library_dir = tmp_path / 'library'
        library_dir.mkdir()
        monkeypatch.setattr('apitest.storage.test_case_library.get_library_dir', lambda: library_dir)
        
        test_case = {'schema_file': 'test.yaml', 'method': 'POST', 'path': '/users', 'test_case_json': {}, 'validation_status': 'approved'}
        file_path = save_test_case_to_library(test_case)
        
        deleted = delete_test_case_from_library(file_path.name)
        assert deleted is True
        assert not file_path.exists()

