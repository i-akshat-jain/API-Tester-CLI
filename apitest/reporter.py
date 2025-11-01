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
            
            table.add_row(
                f"[{status_color}]{status_icon}[/{status_color}]",
                method_text,
                path_text,
                status_code_text,
                time_text
            )
            
            # Show error details in verbose mode or if there are errors
            if (verbose or result.status in [TestStatus.FAIL, TestStatus.ERROR]) and result.error_message:
                table.add_row("", "", f"[dim red]  → {result.error_message}[/dim red]", "", "", style="dim")
            
            if verbose and result.schema_mismatch and result.schema_errors:
                for error in result.schema_errors:
                    table.add_row("", "", f"[dim yellow]  ⚠ Schema: {error}[/dim yellow]", "", "", style="dim")
        
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
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            color: #333;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            padding: 40px;
        }}
        .header {{
            border-bottom: 3px solid #ecf0f1;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        h1 {{
            color: #2c3e50;
            margin-bottom: 5px;
            font-size: 32px;
        }}
        .subtitle {{
            color: #7f8c8d;
            margin-bottom: 5px;
        }}
        .api-info {{
            color: #95a5a6;
            font-size: 14px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            padding: 25px;
            border-radius: 10px;
            border-left: 5px solid #3498db;
            transition: transform 0.2s;
        }}
        .stat-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }}
        .stat-card.success {{ border-left-color: #27ae60; background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%); }}
        .stat-card.warning {{ border-left-color: #f39c12; background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%); }}
        .stat-card.error {{ border-left-color: #e74c3c; background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%); }}
        .stat-card h3 {{
            font-size: 36px;
            margin-bottom: 5px;
            font-weight: 700;
        }}
        .stat-card p {{
            color: #555;
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
            border-bottom: 1px solid #ecf0f1;
        }}
        tr:hover {{ background: #f8f9fa; }}
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
            color: #e74c3c;
            font-size: 13px;
            padding: 10px;
            background: #fff5f5;
            border-left: 3px solid #e74c3c;
        }}
        code {{
            background: #f4f4f4;
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
        }}
        details summary:hover {{
            color: #3498db;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 API Test Report</h1>
            <p class="subtitle">Generated on {self._get_timestamp()}</p>
            <p class="api-info">API: {schema_title} {schema_version if schema_version else ''}</p>
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
        <table>
            <thead>
                <tr>
                    <th>Method</th>
                    <th>Endpoint</th>
                    <th>Status</th>
                    <th>Response Time</th>
                    <th>Result</th>
                </tr>
            </thead>
            <tbody>
"""
        
        for result in results.results:
            status_class = f"status-{result.status.value}"
            method_class = f"method-{result.method}"
            
            status_display = "✓ Pass" if result.status == TestStatus.PASS else \
                           "✗ Fail" if result.status == TestStatus.FAIL else \
                           "⚠ Warning" if result.status == TestStatus.WARNING else \
                           "✗ Error"
            
            status_code_display = f"{result.status_code}" if result.status_code > 0 else "N/A"
            time_display = f"{result.response_time_ms:.0f}ms" if result.response_time_ms > 0 else "N/A"
            
            html += f"""
                <tr>
                    <td><span class="{method_class}">{result.method}</span></td>
                    <td><code>{result.path}</code></td>
                    <td>{status_code_display}</td>
                    <td>{time_display}</td>
                    <td class="{status_class}">{status_display}</td>
                </tr>
"""
            
            if result.error_message:
                html += f"""
                <tr>
                    <td colspan="5" class="error-details">❌ Error: {result.error_message}</td>
                </tr>
"""
            
            if result.schema_mismatch and result.schema_errors:
                for error in result.schema_errors:
                    html += f"""
                <tr>
                    <td colspan="5" class="error-details">⚠️ Schema Warning: {error}</td>
                </tr>
"""
            
            # Show response example in verbose mode
            if verbose and result.response_body:
                import json
                try:
                    response_json = json.dumps(result.response_body, indent=2)
                    response_preview = response_json[:500]
                    if len(response_json) > 500:
                        response_preview += "..."
                    html += f"""
                <tr>
                    <td colspan="5" style="background: #f8f9fa; padding: 10px;">
                        <details>
                            <summary style="cursor: pointer; font-weight: 600; color: #555;">Response Preview</summary>
                            <pre style="background: #2d2d2d; color: #f8f8f2; padding: 15px; border-radius: 6px; overflow-x: auto; margin-top: 10px;"><code>{response_preview}</code></pre>
                        </details>
                    </td>
                </tr>
"""
                except (TypeError, ValueError):
                    # If response_body can't be serialized, skip
                    pass
        
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

