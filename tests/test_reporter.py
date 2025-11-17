"""
Comprehensive tests for Reporter class
"""

import pytest
import json
import csv
from pathlib import Path
from unittest.mock import Mock, patch
from apitest.reporter import Reporter
from apitest.tester import TestResults, TestResult, TestStatus


@pytest.fixture
def sample_results():
    """Sample test results for testing"""
    results = TestResults()
    results.add_result(TestResult(
        method='GET',
        path='/users',
        status_code=200,
        expected_status=200,
        response_time_ms=150.5,
        status=TestStatus.PASS
    ))
    results.add_result(TestResult(
        method='POST',
        path='/users',
        status_code=201,
        expected_status=201,
        response_time_ms=200.0,
        status=TestStatus.PASS
    ))
    results.add_result(TestResult(
        method='GET',
        path='/invalid',
        status_code=404,
        expected_status=200,
        response_time_ms=100.0,
        status=TestStatus.FAIL,
        error_message='Expected 200, got 404'
    ))
    results.add_result(TestResult(
        method='GET',
        path='/error',
        status_code=0,
        status=TestStatus.ERROR,
        error_message='Connection error'
    ))
    results.add_result(TestResult(
        method='GET',
        path='/warn',
        status_code=200,
        expected_status=200,
        response_time_ms=120.0,
        status=TestStatus.WARNING,
        schema_mismatch=True,
        schema_errors=['Missing required field: id']
    ))
    results.total_time_seconds = 2.5
    return results


@pytest.fixture
def empty_results():
    """Empty test results"""
    return TestResults()


@pytest.fixture
def reporter():
    """Reporter instance"""
    return Reporter()


class TestConsoleReport:
    """Test console report generation"""
    
    def test_print_console_report_basic(self, reporter, sample_results, capsys):
        """Test basic console report generation"""
        reporter.print_console_report(sample_results, verbose=False)
        output = capsys.readouterr().out
        
        assert 'API Tester' in output
        assert 'GET' in output
        assert '/users' in output
    
    def test_print_console_report_verbose(self, reporter, sample_results, capsys):
        """Test verbose console report generation"""
        reporter.print_console_report(sample_results, verbose=True)
        output = capsys.readouterr().out
        
        assert 'API Tester' in output
        assert 'Schema' in output or 'error' in output.lower()
    
    def test_print_console_report_empty(self, reporter, empty_results, capsys):
        """Test console report with empty results"""
        reporter.print_console_report(empty_results, verbose=False)
        output = capsys.readouterr().out
        
        assert 'API Tester' in output
        assert '0' in output or 'endpoint' in output.lower()
    
    def test_print_console_report_all_passed(self, reporter, capsys):
        """Test console report with all passed tests"""
        results = TestResults()
        results.add_result(TestResult('GET', '/users', 200, status=TestStatus.PASS))
        results.add_result(TestResult('POST', '/users', 201, status=TestStatus.PASS))
        results.total_time_seconds = 1.0
        
        reporter.print_console_report(results, verbose=False)
        output = capsys.readouterr().out
        
        assert '2/2' in output or '100%' in output


class TestHTMLReport:
    """Test HTML report generation"""
    
    def test_generate_html_report_basic(self, reporter, sample_results, tmp_path):
        """Test basic HTML report generation"""
        schema = {
            'info': {
                'title': 'Test API',
                'version': '1.0.0'
            }
        }
        output_path = tmp_path / 'report.html'
        
        reporter.generate_html_report(sample_results, str(output_path), schema, verbose=False)
        
        assert output_path.exists()
        content = output_path.read_text()
        assert '<html' in content
        assert 'Test API' in content
        assert 'GET' in content
        assert '/users' in content
    
    def test_generate_html_report_verbose(self, reporter, sample_results, tmp_path):
        """Test HTML report generation with verbose mode"""
        schema = {'info': {'title': 'Test API'}}
        output_path = tmp_path / 'report.html'
        
        # Add response body to a result
        result_with_body = TestResult(
            method='GET',
            path='/users',
            status_code=200,
            status=TestStatus.PASS,
            response_body={'id': 1, 'name': 'Test'}
        )
        results = TestResults()
        results.add_result(result_with_body)
        
        reporter.generate_html_report(results, str(output_path), schema, verbose=True)
        
        content = output_path.read_text()
        assert 'Response Preview' in content or 'id' in content
    
    def test_generate_html_report_empty(self, reporter, empty_results, tmp_path):
        """Test HTML report generation with empty results"""
        schema = {'info': {'title': 'Test API'}}
        output_path = tmp_path / 'report.html'
        
        reporter.generate_html_report(empty_results, str(output_path), schema, verbose=False)
        
        assert output_path.exists()
        content = output_path.read_text()
        assert '0' in content or 'Passed' in content
    
    def test_generate_html_report_all_statuses(self, reporter, tmp_path):
        """Test HTML report with all status types"""
        schema = {'info': {'title': 'Test API'}}
        results = TestResults()
        results.add_result(TestResult('GET', '/pass', 200, status=TestStatus.PASS))
        results.add_result(TestResult('GET', '/fail', 404, status=TestStatus.FAIL))
        results.add_result(TestResult('GET', '/warn', 200, status=TestStatus.WARNING))
        results.add_result(TestResult('GET', '/error', 0, status=TestStatus.ERROR))
        results.total_time_seconds = 1.0
        
        output_path = tmp_path / 'report.html'
        reporter.generate_html_report(results, str(output_path), schema, verbose=False)
        
        content = output_path.read_text()
        assert 'Pass' in content
        assert 'Fail' in content
        assert 'Warning' in content
        assert 'Error' in content
    
    def test_generate_html_report_schema_errors(self, reporter, tmp_path):
        """Test HTML report with schema errors"""
        schema = {'info': {'title': 'Test API'}}
        results = TestResults()
        result = TestResult(
            method='GET',
            path='/users',
            status_code=200,
            status=TestStatus.WARNING,
            schema_mismatch=True,
            schema_errors=['Missing field: id', 'Invalid type: name']
        )
        results.add_result(result)
        
        output_path = tmp_path / 'report.html'
        reporter.generate_html_report(results, str(output_path), schema, verbose=False)
        
        content = output_path.read_text()
        assert 'Schema Warning' in content or 'Schema' in content


class TestJSONReport:
    """Test JSON report generation"""
    
    def test_generate_json_report_basic(self, reporter, sample_results, tmp_path):
        """Test basic JSON report generation"""
        output_path = tmp_path / 'report.json'
        
        reporter.generate_json_report(sample_results, str(output_path))
        
        assert output_path.exists()
        data = json.loads(output_path.read_text())
        
        assert 'summary' in data
        assert 'results' in data
        assert data['summary']['total'] == 5
        assert data['summary']['passed'] == 2
        assert data['summary']['failed'] == 1
        assert data['summary']['errors'] == 1
        assert data['summary']['warnings'] == 1
    
    def test_generate_json_report_empty(self, reporter, empty_results, tmp_path):
        """Test JSON report generation with empty results"""
        output_path = tmp_path / 'report.json'
        
        reporter.generate_json_report(empty_results, str(output_path))
        
        assert output_path.exists()
        data = json.loads(output_path.read_text())
        
        assert data['summary']['total'] == 0
        assert data['summary']['passed'] == 0
        assert len(data['results']) == 0
    
    def test_generate_json_report_structure(self, reporter, sample_results, tmp_path):
        """Test JSON report structure"""
        output_path = tmp_path / 'report.json'
        
        reporter.generate_json_report(sample_results, str(output_path))
        
        data = json.loads(output_path.read_text())
        
        # Check summary structure
        assert 'total' in data['summary']
        assert 'passed' in data['summary']
        assert 'failed' in data['summary']
        assert 'warnings' in data['summary']
        assert 'errors' in data['summary']
        assert 'success_rate' in data['summary']
        assert 'total_time_seconds' in data['summary']
        
        # Check result structure
        if data['results']:
            result = data['results'][0]
            assert 'method' in result
            assert 'path' in result
            assert 'status_code' in result
            assert 'status' in result


class TestCSVReport:
    """Test CSV report generation"""
    
    def test_generate_csv_report_basic(self, reporter, sample_results, tmp_path):
        """Test basic CSV report generation"""
        output_path = tmp_path / 'report.csv'
        
        reporter.generate_csv_report(sample_results, str(output_path))
        
        assert output_path.exists()
        content = output_path.read_text()
        
        assert 'Method' in content
        assert 'Path' in content
        assert 'Status Code' in content
        assert 'GET' in content
        assert '/users' in content
    
    def test_generate_csv_report_empty(self, reporter, empty_results, tmp_path):
        """Test CSV report generation with empty results"""
        output_path = tmp_path / 'report.csv'
        
        reporter.generate_csv_report(empty_results, str(output_path))
        
        assert output_path.exists()
        content = output_path.read_text()
        
        # Should have header row
        lines = content.strip().split('\n')
        assert len(lines) >= 1
        assert 'Method' in lines[0]
    
    def test_generate_csv_report_parsing(self, reporter, sample_results, tmp_path):
        """Test CSV report can be parsed correctly"""
        output_path = tmp_path / 'report.csv'
        
        reporter.generate_csv_report(sample_results, str(output_path))
        
        with open(output_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        assert len(rows) == 5
        assert rows[0]['Method'] == 'GET'
        assert rows[0]['Path'] == '/users'
        assert rows[0]['Status Code'] == '200'
    
    def test_generate_csv_report_all_fields(self, reporter, sample_results, tmp_path):
        """Test CSV report includes all fields"""
        output_path = tmp_path / 'report.csv'
        
        reporter.generate_csv_report(sample_results, str(output_path))
        
        with open(output_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        if rows:
            row = rows[0]
            assert 'Method' in row
            assert 'Path' in row
            assert 'Status Code' in row
            assert 'Expected Status' in row
            assert 'Response Time (ms)' in row
            assert 'Status' in row
            assert 'Error Message' in row


class TestHelperMethods:
    """Test helper methods"""
    
    def test_get_status_icon(self, reporter):
        """Test getting status icons"""
        assert reporter._get_status_icon(TestStatus.PASS) == "✓"
        assert reporter._get_status_icon(TestStatus.FAIL) == "✗"
        assert reporter._get_status_icon(TestStatus.WARNING) == "⚠"
        assert reporter._get_status_icon(TestStatus.ERROR) == "✗"
    
    def test_get_status_color(self, reporter):
        """Test getting status colors"""
        assert reporter._get_status_color(TestStatus.PASS) == "green"
        assert reporter._get_status_color(TestStatus.FAIL) == "red"
        assert reporter._get_status_color(TestStatus.WARNING) == "yellow"
        assert reporter._get_status_color(TestStatus.ERROR) == "red"
    
    def test_get_status_color_rich(self, reporter):
        """Test getting Rich status colors"""
        assert reporter._get_status_color_rich(TestStatus.PASS) == "green"
        assert reporter._get_status_color_rich(TestStatus.FAIL) == "red"
        assert reporter._get_status_color_rich(TestStatus.WARNING) == "yellow"
        assert reporter._get_status_color_rich(TestStatus.ERROR) == "red"
    
    def test_get_status_text(self, reporter):
        """Test getting HTTP status text"""
        assert reporter._get_status_text(200) == "OK"
        assert reporter._get_status_text(201) == "Created"
        assert reporter._get_status_text(404) == "Not Found"
        assert reporter._get_status_text(500) == "Internal Server Error"
        assert reporter._get_status_text(999) == ""  # Unknown status
    
    def test_get_timestamp(self, reporter):
        """Test getting timestamp"""
        timestamp = reporter._get_timestamp()
        assert len(timestamp) > 0
        assert '202' in timestamp or '2024' in timestamp or '2025' in timestamp  # Year check


class TestEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_html_report_large_response_body(self, reporter, tmp_path):
        """Test HTML report with very large response body"""
        schema = {'info': {'title': 'Test API'}}
        results = TestResults()
        large_body = {'data': ['x' * 1000] * 100}  # Large response
        result = TestResult(
            method='GET',
            path='/large',
            status_code=200,
            status=TestStatus.PASS,
            response_body=large_body
        )
        results.add_result(result)
        
        output_path = tmp_path / 'report.html'
        reporter.generate_html_report(results, str(output_path), schema, verbose=True)
        
        # Should handle large responses gracefully
        assert output_path.exists()
    
    def test_json_report_unicode_characters(self, reporter, tmp_path):
        """Test JSON report with unicode characters"""
        results = TestResults()
        result = TestResult(
            method='GET',
            path='/test',
            status_code=200,
            status=TestStatus.PASS,
            error_message='Test with émojis 🎉 and 中文'
        )
        results.add_result(result)
        
        output_path = tmp_path / 'report.json'
        reporter.generate_json_report(results, str(output_path))
        
        # Should handle unicode correctly
        data = json.loads(output_path.read_text(encoding='utf-8'))
        assert 'émojis' in data['results'][0]['error_message'] or data['results'][0]['error_message'] is None
    
    def test_csv_report_special_characters(self, reporter, tmp_path):
        """Test CSV report with special characters in paths"""
        results = TestResults()
        result = TestResult(
            method='GET',
            path='/test?param=value&other=test',
            status_code=200,
            status=TestStatus.PASS
        )
        results.add_result(result)
        
        output_path = tmp_path / 'report.csv'
        reporter.generate_csv_report(results, str(output_path))
        
        # Should handle special characters
        assert output_path.exists()
        content = output_path.read_text()
        assert '/test' in content
    
    def test_html_report_missing_schema_info(self, reporter, sample_results, tmp_path):
        """Test HTML report with missing schema info"""
        schema = {}  # Empty schema
        output_path = tmp_path / 'report.html'
        
        reporter.generate_html_report(sample_results, str(output_path), schema, verbose=False)
        
        assert output_path.exists()
        content = output_path.read_text()
        assert 'API' in content  # Should still generate report
    
    def test_json_report_none_values(self, reporter, tmp_path):
        """Test JSON report with None values"""
        results = TestResults()
        result = TestResult(
            method='GET',
            path='/test',
            status_code=200,
            expected_status=None,
            status=TestStatus.PASS,
            error_message=None
        )
        results.add_result(result)
        
        output_path = tmp_path / 'report.json'
        reporter.generate_json_report(results, str(output_path))
        
        # Should handle None values
        data = json.loads(output_path.read_text())
        assert data['results'][0]['expected_status'] is None or data['results'][0]['expected_status'] == ''

