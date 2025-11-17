"""
Storage module for API Tester CLI

Provides local-only storage for:
- Test results and history (SQLite database)
- Encrypted token storage (system keyring)
- Baseline tracking
- Learning patterns
- AI test cases and validation feedback
- Test case library

All data is stored locally on your machine only - never sent to external servers.
"""

from apitest.storage.database import Database, get_db_path, Storage
from apitest.storage.token_store import TokenStore
from apitest.storage.history import TestHistory
from apitest.storage.test_case_library import (
    get_library_dir,
    save_test_case_to_library,
    load_test_case_from_library,
    list_test_cases_in_library,
    get_test_cases_by_endpoint,
    delete_test_case_from_library
)

__all__ = [
    'Database', 'get_db_path', 'Storage', 'TokenStore', 'TestHistory',
    'get_library_dir', 'save_test_case_to_library', 'load_test_case_from_library',
    'list_test_cases_in_library', 'get_test_cases_by_endpoint',
    'delete_test_case_from_library'
]

