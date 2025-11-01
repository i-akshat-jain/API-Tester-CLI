"""
Command-line interface for API Tester CLI
"""

import click
import os
import sys
from pathlib import Path
from typing import Optional

from apitest.schema_parser import SchemaParser
from apitest.validator import SchemaValidator
from apitest.tester import APITester
from apitest.reporter import Reporter
from apitest.auth import AuthHandler
from apitest.utils import expand_env_vars
from apitest import __version__
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.console import Console


@click.command()
@click.argument('schema_file', type=click.Path(exists=True, readable=True))
@click.option('--base-url', '-u', help='Override base URL from schema')
@click.option('--auth', '-a', help='Authentication: bearer=TOKEN or apikey=KEY:VALUE or header=KEY:VALUE. Supports $ENV_VAR for tokens.')
@click.option('--path-params', help='Path parameters as comma-separated key=value pairs (e.g., id=123,petId=abc). Supports $ENV_VAR.')
@click.option('--format', '-f', type=click.Choice(['console', 'html', 'json', 'csv'], case_sensitive=False), 
              default='console', help='Output format')
@click.option('--output', '-o', type=click.Path(), help='Output file path (for html/json/csv)')
@click.option('--parallel', '-p', is_flag=True, help='Run tests in parallel')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.option('--timeout', '-t', type=int, default=30, help='Request timeout in seconds')
@click.version_option(version=__version__)
def main(schema_file: str, base_url: Optional[str], auth: Optional[str], 
         path_params: Optional[str], format: str, output: Optional[str], 
         parallel: bool, verbose: bool, timeout: int):
    """
    API Tester CLI - Automate OpenAPI/Swagger API Testing
    
    Reads an OpenAPI schema file and automatically tests all endpoints.
    
    Example:
    
        apitest schema.yaml
    
    With authentication:
    
        apitest schema.yaml --auth bearer=your_token_here
    """
    try:
        # Initialize components
        schema_path = Path(schema_file)
        
        # Parse schema
        parser = SchemaParser()
        schema = parser.parse(schema_path)
        
        # Validate schema
        validator = SchemaValidator()
        validation_result = validator.validate(schema)
        
        if not validation_result.is_valid:
            click.echo(click.style("✗ Schema validation failed:", fg="red", bold=True))
            for error in validation_result.errors:
                click.echo(click.style(f"  • {error}", fg="red"))
            sys.exit(1)
        
        # Setup authentication
        auth_handler = AuthHandler()
        if auth:
            # Expand environment variables in auth string
            auth_expanded = expand_env_vars(auth)
            auth_handler.parse_auth_string(auth_expanded)
        
        # Parse path parameters
        path_params_dict = {}
        if path_params:
            for param in path_params.split(','):
                param = param.strip()
                if '=' in param:
                    key, value = param.split('=', 1)
                    # Expand environment variables
                    path_params_dict[key.strip()] = expand_env_vars(value.strip())
        
        # Auto-apply security from schema if available and no auth provided
        if not auth:
            parser_for_security = SchemaParser()
            security_schemes = parser_for_security.get_security_schemes(schema)
            security_requirements = parser_for_security.get_security_requirements(schema)
            
            # If security is defined in schema, try to get from environment
            if security_schemes and security_requirements:
                for req in security_requirements:
                    for scheme_name, _ in req.items():
                        if scheme_name in security_schemes:
                            scheme = security_schemes[scheme_name]
                            scheme_type = scheme.get('type', '')
                            
                            # Try to get token from environment
                            env_var_name = f"{scheme_name.upper()}_TOKEN" if scheme_type == 'http' else f"{scheme_name.upper()}_API_KEY"
                            token = os.getenv(env_var_name) or os.getenv('API_TOKEN') or os.getenv('API_KEY')
                            
                            if token:
                                if scheme_type == 'http' and scheme.get('scheme') == 'bearer':
                                    auth_handler.parse_auth_string(f"bearer={token}")
                                elif scheme_type == 'apiKey':
                                    location = scheme.get('in', 'header')
                                    name = scheme.get('name', 'X-API-Key')
                                    auth_handler.parse_auth_string(f"apikey={name}:{token}:{location}")
                                break
        
        # Override base URL if provided
        if base_url:
            schema['servers'] = [{'url': base_url}]
        else:
            # Check if schema has a valid base URL, if not, default to localhost
            parser_for_url = SchemaParser()
            existing_base_url = parser_for_url.get_base_url(schema)
            # Check if base URL is empty or whitespace-only
            if not existing_base_url or not existing_base_url.strip():
                schema['servers'] = [{'url': 'http://localhost:8000'}]
        
        # Verify base URL is set (final check before initializing tester)
        parser_verify = SchemaParser()
        final_base_url = parser_verify.get_base_url(schema)
        if not final_base_url or not final_base_url.strip():
            schema['servers'] = [{'url': 'http://localhost:8000'}]
        
        # Initialize tester
        tester = APITester(
            schema=schema,
            auth_handler=auth_handler,
            timeout=timeout,
            parallel=parallel,
            verbose=verbose,
            path_params=path_params_dict
        )
        
        # Count endpoints for progress
        parser = SchemaParser()
        paths = parser.get_paths(schema)
        endpoint_count = 0
        for path_item in paths.values():
            if isinstance(path_item, dict):
                methods = ['get', 'post', 'put', 'delete', 'patch', 'head', 'options']
                endpoint_count += sum(1 for method in methods if method in path_item)
        
        # Run tests with progress indicator
        console = Console()
        if not parallel and endpoint_count > 3:  # Show progress for sequential execution with multiple endpoints
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=console,
                transient=True
            ) as progress:
                task = progress.add_task("[cyan]Testing endpoints...", total=endpoint_count)
                results = tester.run_tests(progress=progress, task=task)
        else:
            results = tester.run_tests()
        
        # Generate report
        reporter = Reporter()
        
        if format == 'console':
            reporter.print_console_report(results, verbose)
            
            # Show path parameter warnings if any
            if tester.default_path_param_warnings:
                console.print()
                console.print("[yellow]⚠ Path Parameter Warnings:[/yellow]")
                for warning in tester.default_path_param_warnings:
                    console.print(f"  [dim]{warning}[/dim]")
                console.print("[dim]Tip: Use --path-params to provide custom values (e.g., --path-params id=123,petId=abc)[/dim]")
        elif format == 'html':
            output_path = output or 'api_test_report.html'
            reporter.generate_html_report(results, output_path, schema)
            click.echo(click.style(f"\n✓ Report saved: {output_path}", fg="green"))
        elif format == 'json':
            output_path = output or 'api_test_report.json'
            reporter.generate_json_report(results, output_path)
            click.echo(click.style(f"\n✓ Report saved: {output_path}", fg="green"))
        elif format == 'csv':
            output_path = output or 'api_test_report.csv'
            reporter.generate_csv_report(results, output_path)
            click.echo(click.style(f"\n✓ Report saved: {output_path}", fg="green"))
        
        # Exit with appropriate code
        if results.has_failures():
            sys.exit(1)
        else:
            sys.exit(0)
            
    except FileNotFoundError:
        click.echo(click.style(f"✗ Error: Schema file not found: {schema_file}", fg="red"), err=True)
        sys.exit(1)
    except Exception as e:
        if verbose:
            import traceback
            click.echo(click.style(f"✗ Error: {str(e)}", fg="red"), err=True)
            click.echo(traceback.format_exc(), err=True)
        else:
            click.echo(click.style(f"✗ Error: {str(e)}", fg="red"), err=True)
            click.echo("Run with --verbose for more details", err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

