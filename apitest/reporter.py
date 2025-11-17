"""
Report generation for test results
"""

import json
import csv
from typing import Dict, Any, List
from pathlib import Path
import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.text import Text

from apitest.tester import TestResults, TestResult, TestStatus


class Reporter:
    """Generate various report formats"""
    
    def __init__(self):
        self.console = Console()
    
    def print_console_report(self, results: TestResults, verbose: bool = False):
        """
        Print console report with colors and formatting using Rich
        
        Args:
            results: TestResults object
            verbose: Whether to show detailed output
        """
        # Header
        self.console.print()
        self.console.print(Panel.fit(
            "[bold cyan]🔍 API Tester v1.0[/bold cyan]",
            border_style="cyan"
        ))
        self.console.print()
        
        # Summary
        total = len(results.results)
        passed = len(results.get_passed())
        failed = len(results.get_failed())
        warnings = len(results.get_warnings())
        errors = len(results.get_errors())
        
        self.console.print(f"[white]📄 Found [bold]{total}[/bold] endpoints to test[/white]")
        self.console.print()
        
        # Results table
        table = Table(show_header=True, header_style="bold white", box=None)
        table.add_column("Status", width=3, justify="center")
        table.add_column("Method", width=8, style="cyan")
        table.add_column("Endpoint", width=35)
        table.add_column("Status Code", width=12)
        table.add_column("Response Time", width=15, justify="right")
        table.add_column("Data Source", width=12, justify="center")
        
        for result in results.results:
            status_icon = self._get_status_icon(result.status)
            status_color = self._get_status_color_rich(result.status)
            
            method_text = f"[bold]{result.method}[/bold]"
            path_text = result.path
            if len(path_text) > 33:
                path_text = path_text[:30] + "..."
            
            if result.status_code > 0:
                status_code_text = f"[{status_color}]{result.status_code} {self._get_status_text(result.status_code)}[/{status_color}]"
                time_text = f"[dim]{result.response_time_ms:.0f}ms[/dim]"
            else:
                status_code_text = f"[red]Error[/red]"
                time_text = "[dim]N/A[/dim]"
            
            # Data source indicator
            if result.data_source:
                if result.data_source == 'learned':
                    data_source_text = "[green]learned[/green]"
                else:
                    data_source_text = "[dim]generated[/dim]"
            else:
                data_source_text = "[dim]-[/dim]"
            
            table.add_row(
                f"[{status_color}]{status_icon}[/{status_color}]",
                method_text,
                path_text,
                status_code_text,
                time_text,
                data_source_text
            )
            
            # Show error details in verbose mode or if there are errors
            if (verbose or result.status in [TestStatus.FAIL, TestStatus.ERROR]) and result.error_message:
                table.add_row("", "", f"[dim red]  → {result.error_message}[/dim red]", "", "", "", style="dim")
            
            if verbose and result.schema_mismatch and result.schema_errors:
                for error in result.schema_errors:
                    table.add_row("", "", f"[dim yellow]  ⚠ Schema: {error}[/dim yellow]", "", "", "", style="dim")
        
        self.console.print(table)
        self.console.print()
        
        # Summary stats
        success_rate = results.get_success_rate()
        rate_color = "green" if success_rate >= 80 else "yellow" if success_rate >= 50 else "red"
        
        summary_panel = Panel(
            f"[bold]{passed}/{total} passed[/bold] ([{rate_color}]{success_rate:.0f}% success rate[/{rate_color}])\n"
            f"[dim]⏱  Total time: {results.total_time_seconds:.1f}s[/dim]",
            border_style=rate_color,
            title="📈 Results"
        )
        self.console.print(summary_panel)
        self.console.print()
    
    def generate_html_report(self, results: TestResults, output_path: str, schema: Dict[str, Any], verbose: bool = False):
        """
        Generate HTML report
        
        Args:
            results: TestResults object
            output_path: Path to save HTML file
            schema: Original schema for reference
            verbose: Whether to include detailed response examples
        """
        total = len(results.results)
        passed = len(results.get_passed())
        failed = len(results.get_failed())
        warnings = len(results.get_warnings())
        errors = len(results.get_errors())
        success_rate = results.get_success_rate()
        
        schema_title = schema.get('info', {}).get('title', 'API')
        schema_version = schema.get('info', {}).get('version', '')
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>API Test Report - {schema_title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: #000000;
            padding: 20px;
            color: #ffffff;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: #000000;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            padding: 40px;
        }}
        .header {{
            border-bottom: 3px solid #333333;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        h1 {{
            color: #ffffff;
            margin-bottom: 5px;
            font-size: 32px;
        }}
        h2 {{
            color: #ffffff;
            margin-top: 30px;
            margin-bottom: 20px;
            font-size: 24px;
        }}
        .subtitle {{
            color: #ffffff;
            margin-bottom: 5px;
        }}
        .api-info {{
            color: #ffffff;
            font-size: 14px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: #1a1a1a;
            padding: 25px;
            border-radius: 10px;
            border-left: 5px solid #3498db;
            transition: transform 0.2s;
            color: #ffffff;
        }}
        .stat-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(255,255,255,0.1);
        }}
        .stat-card.success {{ border-left-color: #27ae60; background: #1a1a1a; color: #ffffff; }}
        .stat-card.warning {{ border-left-color: #f39c12; background: #1a1a1a; color: #ffffff; }}
        .stat-card.error {{ border-left-color: #e74c3c; background: #1a1a1a; color: #ffffff; }}
        .stat-card h3 {{
            font-size: 36px;
            margin-bottom: 5px;
            font-weight: 700;
            color: #ffffff;
        }}
        .stat-card p {{
            color: #ffffff;
            font-size: 14px;
            font-weight: 500;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            border-radius: 8px;
            overflow: hidden;
        }}
        th {{
            background: linear-gradient(135deg, #34495e 0%, #2c3e50 100%);
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: 600;
        }}
        td {{
            padding: 15px;
            border-bottom: 1px solid #333333;
            color: #ffffff;
        }}
        tr:hover {{ background: #1a1a1a; }}
        tr:last-child td {{ border-bottom: none; }}
        .status-pass {{ color: #27ae60; font-weight: 600; }}
        .status-fail {{ color: #e74c3c; font-weight: 600; }}
        .status-warning {{ color: #f39c12; font-weight: 600; }}
        .status-error {{ color: #e74c3c; font-weight: 600; }}
        .method {{
            display: inline-block;
            padding: 5px 10px;
            border-radius: 5px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            margin-right: 8px;
        }}
        .method-GET {{ background: #3498db; color: white; }}
        .method-POST {{ background: #27ae60; color: white; }}
        .method-PUT {{ background: #f39c12; color: white; }}
        .method-DELETE {{ background: #e74c3c; color: white; }}
        .method-PATCH {{ background: #9b59b6; color: white; }}
        .error-details {{
            color: #ffffff;
            font-size: 13px;
            padding: 15px;
            background: #2a1a1a;
            border-left: 4px solid #e74c3c;
            border-radius: 4px;
            margin: 5px 0;
            max-height: 400px;
            overflow-y: auto;
            overflow-x: auto;
            word-wrap: break-word;
            word-break: break-word;
            white-space: pre-wrap;
        }}
        .error-details::-webkit-scrollbar {{
            width: 8px;
            height: 8px;
        }}
        .error-details::-webkit-scrollbar-track {{
            background: #1a1a1a;
            border-radius: 4px;
        }}
        .error-details::-webkit-scrollbar-thumb {{
            background: #555555;
            border-radius: 4px;
        }}
        .error-details::-webkit-scrollbar-thumb:hover {{
            background: #666666;
        }}
        .error-details strong {{
            color: #ff6b6b;
            font-size: 14px;
            display: block;
            margin-bottom: 8px;
        }}
        .error-details pre {{
            margin: 8px 0;
            padding: 10px;
            background: #1a1a1a;
            border: 1px solid #444444;
            border-radius: 4px;
            overflow-x: auto;
            overflow-y: auto;
            max-height: 300px;
            font-size: 12px;
            line-height: 1.4;
            white-space: pre-wrap;
            word-wrap: break-word;
            word-break: break-word;
        }}
        .error-details pre::-webkit-scrollbar {{
            width: 6px;
            height: 6px;
        }}
        .error-details pre::-webkit-scrollbar-track {{
            background: #0a0a0a;
            border-radius: 3px;
        }}
        .error-details pre::-webkit-scrollbar-thumb {{
            background: #444444;
            border-radius: 3px;
        }}
        .error-details pre::-webkit-scrollbar-thumb:hover {{
            background: #555555;
        }}
        code {{
            background: #1a1a1a;
            color: #ffffff;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 13px;
        }}
        pre {{
            background: #2d2d2d;
            color: #f8f8f2;
            padding: 15px;
            border-radius: 6px;
            overflow-x: auto;
            font-size: 13px;
            line-height: 1.5;
        }}
        details summary {{
            cursor: pointer;
            user-select: none;
            color: #ffffff;
        }}
        details summary:hover {{
            color: #3498db;
        }}
        .download-btn {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            margin-top: 15px;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }}
        .download-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }}
        .download-btn:active {{
            transform: translateY(0);
        }}
        .filter-container {{
            display: flex;
            align-items: center;
            gap: 15px;
            margin-bottom: 20px;
            padding: 15px;
            background: #1a1a1a;
            border-radius: 8px;
            flex-wrap: wrap;
        }}
        .filter-label {{
            color: #ffffff;
            font-weight: 600;
            font-size: 14px;
        }}
        .filter-select {{
            background: #2d2d2d;
            color: #ffffff;
            border: 1px solid #444444;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 14px;
            cursor: pointer;
            min-width: 150px;
            transition: border-color 0.2s;
        }}
        .filter-select:hover {{
            border-color: #667eea;
        }}
        .filter-select:focus {{
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.2);
        }}
        .filter-select option {{
            background: #2d2d2d;
            color: #ffffff;
        }}
        .filter-reset {{
            background: #444444;
            color: #ffffff;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 14px;
            cursor: pointer;
            transition: background 0.2s;
        }}
        .filter-reset:hover {{
            background: #555555;
        }}
        .filter-count {{
            color: #aaaaaa;
            font-size: 13px;
            margin-left: auto;
        }}
    </style>
    <script>
        function downloadTestResultsJSON() {{
            const testResults = [];
            const rows = document.querySelectorAll('table tbody tr');
            
            let currentTest = null;
            
            for (let i = 0; i < rows.length; i++) {{
                const row = rows[i];
                const cells = row.querySelectorAll('td');
                
                // Check if this is a test result row (has method or test case)
                const methodCell = cells[0];
                const pathCell = cells[1];
                const testCaseCell = cells[2];
                const statusCell = cells[3];
                const timeCell = cells[4];
                const resultCell = cells[5];
                
                if (cells.length === 6 && (methodCell.textContent.trim() || testCaseCell.textContent.trim())) {{
                    // This is a test result row
                    const methodSpan = methodCell.querySelector('span[class^="method-"]');
                    const method = methodSpan?.textContent.trim() || methodCell.textContent.trim() || 
                                 (currentTest ? currentTest.method : '');
                    const path = pathCell.querySelector('code')?.textContent.trim() || 
                               (currentTest ? currentTest.path : '');
                    const testCase = testCaseCell.textContent.trim();
                    const statusCode = parseInt(statusCell.textContent.trim()) || null;
                    const responseTime = timeCell.textContent.trim();
                    const result = resultCell.textContent.trim();
                    
                    if (method && path) {{
                        currentTest = {{
                            method: method,
                            path: path,
                            test_case: testCase,
                            status_code: statusCode,
                            response_time: responseTime,
                            result: result,
                            request_body: null,
                            expected_response: null,
                            actual_response: null
                        }};
                        testResults.push(currentTest);
                    }} else if (currentTest && testCase) {{
                        // Update current test with test case info
                        currentTest.test_case = testCase;
                        currentTest.status_code = statusCode;
                        currentTest.response_time = responseTime;
                        currentTest.result = result;
                    }}
                }} else if (cells.length === 6 && cells[0].colSpan === 6) {{
                    // This is a details row - extract request/response data
                    const details = row.querySelector('details');
                    if (details && currentTest) {{
                        // Force open the details to access content (even if collapsed)
                        const wasOpen = details.open;
                        details.open = true;
                        
                        // Find the details content div - try multiple selectors
                        let detailsDiv = details.querySelector('div[style*="margin-top"]');
                        if (!detailsDiv) {{
                            detailsDiv = details.querySelector('div');
                        }}
                        
                        if (detailsDiv) {{
                            // Helper function to extract JSON from a section
                            const extractSectionData = (h4Text) => {{
                                // Find the h4 element matching the text
                                const allH4s = Array.from(detailsDiv.querySelectorAll('h4'));
                                const targetH4 = allH4s.find(h4 => {{
                                    const text = h4.textContent || '';
                                    return text.includes(h4Text) || 
                                           (h4Text === 'Request Body' && text.includes('📤')) ||
                                           (h4Text === 'Expected Response' && text.includes('✅')) ||
                                           (h4Text === 'Actual Response' && text.includes('📥'));
                                }});
                                
                                if (!targetH4) return null;
                                
                                // Find the parent div containing both h4 and pre
                                let parentDiv = targetH4.closest('div[style*="margin-bottom"]');
                                if (!parentDiv) {{
                                    parentDiv = targetH4.parentElement;
                                }}
                                
                                if (!parentDiv) return null;
                                
                                // Find the code element with the JSON
                                const codeElement = parentDiv.querySelector('pre code');
                                if (!codeElement) return null;
                                
                                // Extract and parse the text
                                let text = codeElement.textContent || codeElement.innerText || '';
                                text = text.trim();
                                
                                if (!text) return null;
                                
                                // Try to parse as JSON, fallback to raw text
                                try {{
                                    return JSON.parse(text);
                                }} catch (e) {{
                                    return text;
                                }}
                            }};
                            
                            // Extract each section
                            const requestBody = extractSectionData('Request Body');
                            if (requestBody !== null) {{
                                currentTest.request_body = requestBody;
                            }}
                            
                            const expectedResponse = extractSectionData('Expected Response');
                            if (expectedResponse !== null) {{
                                currentTest.expected_response = expectedResponse;
                            }}
                            
                            const actualResponse = extractSectionData('Actual Response');
                            if (actualResponse !== null) {{
                                currentTest.actual_response = actualResponse;
                            }}
                        }}
                        
                        // Restore original state
                        details.open = wasOpen;
                    }}
                }}
            }}
            
            // Create JSON structure
            const jsonData = {{
                metadata: {{
                    api_title: document.querySelector('.api-info')?.textContent || '',
                    generated_at: document.querySelector('.subtitle')?.textContent.replace('Generated on ', '') || '',
                    summary: {{
                        passed: document.querySelector('.stat-card.success h3')?.textContent || '0',
                        failed: document.querySelector('.stat-card.error h3')?.textContent || '0',
                        warnings: document.querySelector('.stat-card.warning h3')?.textContent || '0',
                        success_rate: document.querySelectorAll('.stat-card')[3]?.querySelector('h3')?.textContent || '0%',
                        total_time: document.querySelectorAll('.stat-card')[4]?.querySelector('h3')?.textContent || '0s'
                    }}
                }},
                test_results: testResults
            }};
            
            // Download as JSON file
            const blob = new Blob([JSON.stringify(jsonData, null, 2)], {{ type: 'application/json' }});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'api_test_results.json';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }}
        
        function filterByStatusCode() {{
            const filterValue = document.getElementById('statusCodeFilter').value;
            const rows = Array.from(document.querySelectorAll('table tbody tr'));
            let visibleCount = 0;
            
            // First pass: mark test result rows
            rows.forEach((row, index) => {{
                const cells = row.querySelectorAll('td');
                // Check if this is a test result row (not a detail row)
                if (cells.length === 6 && (!cells[0].hasAttribute('colspan') || cells[0].colSpan !== 6)) {{
                    const statusCell = cells[3];
                    const statusCode = statusCell.textContent.trim();
                    
                    if (filterValue === 'all' || statusCode === filterValue) {{
                        row.style.display = '';
                        row.dataset.shouldShow = 'true';
                        visibleCount++;
                    }} else {{
                        row.style.display = 'none';
                        row.dataset.shouldShow = 'false';
                    }}
                }}
            }});
            
            // Second pass: handle detail rows based on their associated test result row
            rows.forEach((row, index) => {{
                const cells = row.querySelectorAll('td');
                // Check if this is a detail row (colspan row)
                if (cells.length === 6 && cells[0].hasAttribute('colspan') && cells[0].colSpan === 6) {{
                    // Find the previous test result row
                    let prevRow = row.previousElementSibling;
                    while (prevRow) {{
                        const prevCells = prevRow.querySelectorAll('td');
                        if (prevCells.length === 6 && (!prevCells[0].hasAttribute('colspan') || prevCells[0].colSpan !== 6)) {{
                            // Found the associated test result row
                            if (prevRow.dataset.shouldShow === 'true') {{
                                row.style.display = '';
                            }} else {{
                                row.style.display = 'none';
                            }}
                            break;
                        }}
                        prevRow = prevRow.previousElementSibling;
                    }}
                }}
            }});
            
            // Update count
            const countElement = document.getElementById('filterCount');
            if (countElement) {{
                if (filterValue === 'all') {{
                    countElement.textContent = '';
                }} else {{
                    countElement.textContent = `Showing ${{visibleCount}} result(s) with status code ${{filterValue}}`;
                }}
            }}
        }}
        
        function resetFilter() {{
            document.getElementById('statusCodeFilter').value = 'all';
            filterByStatusCode();
        }}
        
        // Extract unique status codes on page load
        function initializeFilter() {{
            const rows = document.querySelectorAll('table tbody tr');
            const statusCodes = new Set();
            
            rows.forEach(row => {{
                const cells = row.querySelectorAll('td');
                if (cells.length === 6 && cells[0].colSpan !== 6) {{
                    const statusCode = cells[3].textContent.trim();
                    if (statusCode && statusCode !== 'N/A') {{
                        statusCodes.add(statusCode);
                    }}
                }}
            }});
            
            const filterSelect = document.getElementById('statusCodeFilter');
            const sortedCodes = Array.from(statusCodes).sort((a, b) => {{
                const numA = parseInt(a) || 0;
                const numB = parseInt(b) || 0;
                return numA - numB;
            }});
            
            // Add options for each status code
            sortedCodes.forEach(code => {{
                const option = document.createElement('option');
                option.value = code;
                option.textContent = code;
                filterSelect.appendChild(option);
            }});
        }}
        
        // Initialize filter when page loads
        window.addEventListener('DOMContentLoaded', initializeFilter);
    </script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 API Test Report</h1>
            <p class="subtitle">Generated on {self._get_timestamp()}</p>
            <p class="api-info">API: {schema_title} {schema_version if schema_version else ''}</p>
            <button class="download-btn" onclick="downloadTestResultsJSON()">
                📥 Download Test Results (JSON)
            </button>
        </div>
        
        <div class="summary">
            <div class="stat-card success">
                <h3>{passed}</h3>
                <p>Passed</p>
            </div>
            <div class="stat-card error">
                <h3>{failed + errors}</h3>
                <p>Failed</p>
            </div>
            <div class="stat-card warning">
                <h3>{warnings}</h3>
                <p>Warnings</p>
            </div>
            <div class="stat-card">
                <h3>{success_rate:.1f}%</h3>
                <p>Success Rate</p>
            </div>
            <div class="stat-card">
                <h3>{results.total_time_seconds:.1f}s</h3>
                <p>Total Time</p>
            </div>
        </div>
        
        <h2>Test Results</h2>
        <div class="filter-container">
            <label class="filter-label" for="statusCodeFilter">Filter by Status Code:</label>
            <select id="statusCodeFilter" class="filter-select" onchange="filterByStatusCode()">
                <option value="all">All Status Codes</option>
            </select>
            <button class="filter-reset" onclick="resetFilter()">Reset Filter</button>
            <span id="filterCount" class="filter-count"></span>
        </div>
        <table>
            <thead>
                <tr>
                    <th>Method</th>
                    <th>Endpoint</th>
                    <th>Test Case</th>
                    <th>Status</th>
                    <th>Response Time</th>
                    <th>Result</th>
                </tr>
            </thead>
            <tbody>
"""
        
        # Group results by endpoint (method + path) to show all test cases
        from collections import defaultdict
        endpoint_groups = defaultdict(list)
        for result in results.results:
            key = (result.method, result.path)
            endpoint_groups[key].append(result)
        
        # Sort endpoints for consistent display
        sorted_endpoints = sorted(endpoint_groups.items(), key=lambda x: (x[0][0], x[0][1]))
        
        for (method, path), test_results in sorted_endpoints:
            # Show all test cases for this endpoint
            for idx, result in enumerate(test_results, 1):
                status_class = f"status-{result.status.value}"
                method_class = f"method-{result.method}"
                
                status_display = "✓ Pass" if result.status == TestStatus.PASS else \
                               "✗ Fail" if result.status == TestStatus.FAIL else \
                               "⚠ Warning" if result.status == TestStatus.WARNING else \
                               "✗ Error"
                
                status_code_display = f"{result.status_code}" if result.status_code > 0 else "N/A"
                time_display = f"{result.response_time_ms:.0f}ms" if result.response_time_ms > 0 else "N/A"
                
                # Test case identifier
                test_case_label = ""
                if len(test_results) > 1:
                    test_case_label = f"Test #{idx}"
                if result.test_scenario:
                    test_case_label = result.test_scenario if not test_case_label else f"{test_case_label}: {result.test_scenario}"
                if result.is_ai_generated:
                    test_case_label = f"🤖 AI" + (f" - {test_case_label}" if test_case_label else "")
                if not test_case_label:
                    test_case_label = "-"
                
                # Only show method/path on first row for grouped endpoints
                method_cell = f'<span class="{method_class}">{method}</span>' if idx == 1 else ""
                path_cell = f'<code>{path}</code>' if idx == 1 else ""
                
                html += f"""
                <tr>
                    <td>{method_cell}</td>
                    <td>{path_cell}</td>
                    <td><small>{test_case_label}</small></td>
                    <td>{status_code_display}</td>
                    <td>{time_display}</td>
                    <td class="{status_class}">{status_display}</td>
                </tr>
"""
                
                # Extract and display explicit error messages for 400 and 500 status codes
                error_message_display = None
                if result.status_code in [400, 500] and result.response_body:
                    error_message_display = self._extract_error_message(result.response_body)
                
                # Show error message if available
                if error_message_display:
                    # error_message_display already contains formatted HTML
                    html += f"""
                <tr>
                    <td colspan="6" class="error-details">
                        <strong>🚨 Error Details (Status {result.status_code}):</strong><br>
                        {error_message_display}
                    </td>
                </tr>
"""
                elif result.error_message:
                    html += f"""
                <tr>
                    <td colspan="6" class="error-details">❌ Error: {result.error_message}</td>
                </tr>
"""
                
                if result.schema_mismatch and result.schema_errors:
                    for error in result.schema_errors:
                        html += f"""
                <tr>
                    <td colspan="6" class="error-details">⚠️ Schema Warning: {error}</td>
                </tr>
"""
                
                # Show request body, expected response, and actual response
                has_details = False
                details_html = ""
                
                # Request Body
                if result.request_body:
                    has_details = True
                    try:
                        request_json = json.dumps(result.request_body, indent=2)
                        details_html += f"""
                        <div style="margin-bottom: 15px;">
                            <h4 style="color: #3498db; margin-bottom: 8px; font-size: 14px; font-weight: 600;">📤 Request Body</h4>
                            <pre style="background: #2d2d2d; color: #f8f8f2; padding: 15px; border-radius: 6px; overflow-x: auto; margin: 0; font-size: 12px;"><code>{self._escape_html(request_json)}</code></pre>
                        </div>
"""
                    except (TypeError, ValueError):
                        details_html += f"""
                        <div style="margin-bottom: 15px;">
                            <h4 style="color: #3498db; margin-bottom: 8px; font-size: 14px; font-weight: 600;">📤 Request Body</h4>
                            <pre style="background: #2d2d2d; color: #f8f8f2; padding: 15px; border-radius: 6px; overflow-x: auto; margin: 0; font-size: 12px;"><code>{self._escape_html(str(result.request_body))}</code></pre>
                        </div>
"""
                
                # Expected Response
                if result.expected_response:
                    has_details = True
                    try:
                        expected_status = result.expected_response.get('status_code', result.expected_status)
                        expected_body = result.expected_response.get('body') or result.expected_response.get('content', {})
                        
                        # Try to extract example from expected response
                        expected_content = None
                        if isinstance(expected_body, dict):
                            # Check for example in content
                            json_content = expected_body.get('application/json', {})
                            if json_content:
                                schema = json_content.get('schema', {})
                                if 'example' in schema:
                                    expected_content = schema['example']
                                elif 'examples' in json_content:
                                    # Get first example
                                    examples = json_content.get('examples', {})
                                    if examples:
                                        first_example = list(examples.values())[0]
                                        if isinstance(first_example, dict) and 'value' in first_example:
                                            expected_content = first_example['value']
                                        else:
                                            expected_content = first_example
                        
                        expected_display = {
                            'status_code': expected_status
                        }
                        if expected_content:
                            expected_display['body'] = expected_content
                        
                        expected_json = json.dumps(expected_display, indent=2)
                        details_html += f"""
                        <div style="margin-bottom: 15px;">
                            <h4 style="color: #27ae60; margin-bottom: 8px; font-size: 14px; font-weight: 600;">✅ Expected Response</h4>
                            <pre style="background: #2d2d2d; color: #f8f8f2; padding: 15px; border-radius: 6px; overflow-x: auto; margin: 0; font-size: 12px;"><code>{self._escape_html(expected_json)}</code></pre>
                        </div>
"""
                    except (TypeError, ValueError) as e:
                        expected_str = json.dumps(result.expected_response, indent=2, default=str)
                        details_html += f"""
                        <div style="margin-bottom: 15px;">
                            <h4 style="color: #27ae60; margin-bottom: 8px; font-size: 14px; font-weight: 600;">✅ Expected Response</h4>
                            <pre style="background: #2d2d2d; color: #f8f8f2; padding: 15px; border-radius: 6px; overflow-x: auto; margin: 0; font-size: 12px;"><code>{self._escape_html(expected_str)}</code></pre>
                        </div>
"""
                elif result.expected_status:
                    has_details = True
                    details_html += f"""
                        <div style="margin-bottom: 15px;">
                            <h4 style="color: #27ae60; margin-bottom: 8px; font-size: 14px; font-weight: 600;">✅ Expected Response</h4>
                            <pre style="background: #2d2d2d; color: #f8f8f2; padding: 15px; border-radius: 6px; overflow-x: auto; margin: 0; font-size: 12px;"><code>{self._escape_html(json.dumps({'status_code': result.expected_status}, indent=2))}</code></pre>
                        </div>
"""
                
                # Actual Response
                if result.response_body:
                    has_details = True
                    try:
                        response_json = json.dumps(result.response_body, indent=2)
                        details_html += f"""
                        <div style="margin-bottom: 15px;">
                            <h4 style="color: #e74c3c; margin-bottom: 8px; font-size: 14px; font-weight: 600;">📥 Actual Response (Status: {result.status_code})</h4>
                            <pre style="background: #2d2d2d; color: #f8f8f2; padding: 15px; border-radius: 6px; overflow-x: auto; margin: 0; font-size: 12px;"><code>{self._escape_html(response_json)}</code></pre>
                        </div>
"""
                    except (TypeError, ValueError):
                        details_html += f"""
                        <div style="margin-bottom: 15px;">
                            <h4 style="color: #e74c3c; margin-bottom: 8px; font-size: 14px; font-weight: 600;">📥 Actual Response (Status: {result.status_code})</h4>
                            <pre style="background: #2d2d2d; color: #f8f8f2; padding: 15px; border-radius: 6px; overflow-x: auto; margin: 0; font-size: 12px;"><code>{self._escape_html(str(result.response_body))}</code></pre>
                        </div>
"""
                
                # Display details if available
                if has_details:
                    html += f"""
                <tr>
                    <td colspan="6" style="background: #1a1a1a; padding: 15px;">
                        <details>
                            <summary style="cursor: pointer; font-weight: 600; color: #ffffff; margin-bottom: 10px;">📋 View Request/Response Details</summary>
                            <div style="margin-top: 10px;">
                                {details_html}
                            </div>
                        </details>
                    </td>
                </tr>
"""
        
        html += """
            </tbody>
        </table>
    </div>
</body>
</html>
"""
        
        Path(output_path).write_text(html, encoding='utf-8')
    
    def generate_json_report(self, results: TestResults, output_path: str):
        """Generate JSON report"""
        report = {
            'summary': {
                'total': len(results.results),
                'passed': len(results.get_passed()),
                'failed': len(results.get_failed()),
                'warnings': len(results.get_warnings()),
                'errors': len(results.get_errors()),
                'success_rate': results.get_success_rate(),
                'total_time_seconds': results.total_time_seconds
            },
            'results': [
                {
                    'method': r.method,
                    'path': r.path,
                    'status_code': r.status_code,
                    'expected_status': r.expected_status,
                    'response_time_ms': r.response_time_ms,
                    'status': r.status.value,
                    'error_message': r.error_message,
                    'schema_mismatch': r.schema_mismatch,
                    'schema_errors': r.schema_errors
                }
                for r in results.results
            ]
        }
        
        Path(output_path).write_text(json.dumps(report, indent=2), encoding='utf-8')
    
    def generate_csv_report(self, results: TestResults, output_path: str):
        """Generate CSV report"""
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Method', 'Path', 'Status Code', 'Expected Status', 
                           'Response Time (ms)', 'Status', 'Error Message'])
            
            for result in results.results:
                writer.writerow([
                    result.method,
                    result.path,
                    result.status_code,
                    result.expected_status or '',
                    f"{result.response_time_ms:.2f}",
                    result.status.value,
                    result.error_message or ''
                ])
    
    def _get_status_icon(self, status: TestStatus) -> str:
        """Get status icon"""
        icons = {
            TestStatus.PASS: "✓",
            TestStatus.FAIL: "✗",
            TestStatus.WARNING: "⚠",
            TestStatus.ERROR: "✗"
        }
        return icons.get(status, "?")
    
    def _get_status_color(self, status: TestStatus) -> str:
        """Get status color (for click)"""
        colors = {
            TestStatus.PASS: "green",
            TestStatus.FAIL: "red",
            TestStatus.WARNING: "yellow",
            TestStatus.ERROR: "red"
        }
        return colors.get(status, "white")
    
    def _get_status_color_rich(self, status: TestStatus) -> str:
        """Get status color (for Rich)"""
        colors = {
            TestStatus.PASS: "green",
            TestStatus.FAIL: "red",
            TestStatus.WARNING: "yellow",
            TestStatus.ERROR: "red"
        }
        return colors.get(status, "white")
    
    def _get_status_text(self, status_code: int) -> str:
        """Get HTTP status text"""
        status_texts = {
            200: "OK",
            201: "Created",
            202: "Accepted",
            204: "No Content",
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            500: "Internal Server Error"
        }
        return status_texts.get(status_code, "")
    
    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters"""
        import html
        return html.escape(text)
    
    def _extract_error_message(self, response_body: Any) -> str:
        """
        Extract explicit error message from response body for 400/500 errors
        
        Args:
            response_body: Response body (dict, list, or string)
            
        Returns:
            Formatted error message string
        """
        if not response_body:
            return ""
        
        error_parts = []
        
        # Handle dict responses
        if isinstance(response_body, dict):
            # Common error fields to check
            error_fields = ['message', 'error', 'errors', 'detail', 'detail_message', 
                          'error_message', 'error_description', 'msg', 'error_msg']
            
            for field in error_fields:
                if field in response_body:
                    value = response_body[field]
                    if value:
                        if isinstance(value, (dict, list)):
                            # Format complex error structures
                            try:
                                formatted = json.dumps(value, indent=2)
                                error_parts.append(f"<strong>{field}:</strong><pre style='margin: 5px 0; padding: 8px; background: #2d2d2d; border-radius: 4px; overflow-x: auto;'>{self._escape_html(formatted)}</pre>")
                            except (TypeError, ValueError):
                                error_parts.append(f"<strong>{field}:</strong> {self._escape_html(str(value))}")
                        else:
                            error_parts.append(f"<strong>{field}:</strong> {self._escape_html(str(value))}")
            
            # If no standard error fields found, show the whole response
            if not error_parts:
                try:
                    formatted = json.dumps(response_body, indent=2)
                    error_parts.append(f"<pre style='margin: 5px 0; padding: 8px; background: #2d2d2d; border-radius: 4px; overflow-x: auto;'>{self._escape_html(formatted)}</pre>")
                except (TypeError, ValueError):
                    error_parts.append(self._escape_html(str(response_body)))
        
        # Handle list responses (sometimes errors are in arrays)
        elif isinstance(response_body, list):
            for item in response_body:
                if isinstance(item, dict):
                    msg = self._extract_error_message(item)
                    if msg:
                        error_parts.append(msg)
                else:
                    error_parts.append(self._escape_html(str(item)))
        
        # Handle string responses
        else:
            error_parts.append(self._escape_html(str(response_body)))
        
        # Join all error parts with line breaks
        return "<br>".join(error_parts) if error_parts else ""

