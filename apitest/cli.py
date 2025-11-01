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
from apitest.config import ConfigManager
from apitest.utils import expand_env_vars
from apitest import __version__
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.console import Console
from rich.table import Table


@click.command()
@click.argument('schema_file', required=False, type=click.Path(exists=True, readable=True))
@click.option('--base-url', '-u', help='Override base URL from schema')
@click.option('--auth', '-a', help='Authentication. Examples:\n'
              '  bearer=TOKEN\n'
              '  apikey=X-API-Key:value\n'
              '  apikey=key:value:query\n'
              '  header=Authorization:Basic base64\n'
              'Supports $ENV_VAR for tokens.')
@click.option('--path-params', help='Path parameters as comma-separated key=value pairs (e.g., id=123,petId=abc). Supports $ENV_VAR.')
@click.option('--profile', help='Use a profile from config file (e.g., --profile production)')
@click.option('--config', '-c', type=click.Path(), help='Path to config file (default: ~/.apitest/config.yaml or .apitest.yaml)')
@click.option('--format', '-f', type=click.Choice(['console', 'html', 'json', 'csv'], case_sensitive=False), 
              default='console', help='Output format')
@click.option('--output', '-o', type=click.Path(), help='Output file path (for html/json/csv)')
@click.option('--parallel', '-p', is_flag=True, help='Run tests in parallel')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.option('--timeout', '-t', type=int, default=30, help='Request timeout in seconds')
@click.option('--list-profiles', is_flag=True, help='List available profiles and exit')
@click.option('--init-config', is_flag=True, help='Create example config file and exit')
@click.option('--demo', is_flag=True, help='Run demo test against public Petstore API (no schema file needed)')
@click.option('--dry-run', is_flag=True, help='Show what would be tested without making HTTP requests')
@click.option('--validate-schema', is_flag=True, help='Validate schema file only (do not run tests)')
@click.option('--validate-auth', is_flag=True, help='Validate auth format only (do not run tests)')
@click.option('--summary-only', is_flag=True, help='Show only summary statistics (useful for CI/CD)')
@click.version_option(version=__version__)
def main(schema_file: str, base_url: Optional[str], auth: Optional[str], 
         path_params: Optional[str], profile: Optional[str], config: Optional[str],
         format: str, output: Optional[str], 
         parallel: bool, verbose: bool, timeout: int, list_profiles: bool, init_config: bool,
         demo: bool, dry_run: bool, validate_schema: bool, validate_auth: bool, summary_only: bool):
    """
    API Tester CLI - Automate OpenAPI/Swagger API Testing
    
    Reads an OpenAPI schema file and automatically tests all endpoints.
    
    Quick Examples:
    
        apitest schema.yaml                          # Basic test
        apitest schema.yaml --auth bearer=$TOKEN     # With auth
        apitest schema.yaml --profile production     # Using profile
        apitest --demo                               # Run demo test
        apitest --init-config                        # Setup profiles
        apitest schema.yaml --dry-run                # Preview tests
        apitest schema.yaml --validate-schema        # Validate only
    
    Example:
    
        apitest schema.yaml
    
    With authentication:
    
        apitest schema.yaml --auth bearer=your_token_here
    
    Using profiles:
    
        apitest schema.yaml --profile production
    """
    try:
        # Handle init-config flag
        if init_config:
            config_manager = ConfigManager()
            config_path = config_manager.create_default_config()
            click.echo(click.style(f"✓ Created example config file: {config_path}", fg="green"))
            click.echo("\nEdit the file to add your own profiles.")
            click.echo("Then use profiles with: apitest schema.yaml --profile <name>")
            sys.exit(0)
        
        # Handle list-profiles flag
        if list_profiles:
            config_manager = ConfigManager(config_file=Path(config) if config else None)
            profiles = config_manager.list_profiles()
            
            if not profiles:
                click.echo(click.style("No profiles found.", fg="yellow"))
                click.echo("\nTo create a config file with example profiles, run:")
                click.echo("  apitest --init-config")
                click.echo("\nOr create ~/.apitest/config.yaml or .apitest.yaml manually.")
                sys.exit(0)
            
            console = Console()
            console.print("\n[bold]Available Profiles:[/bold]\n")
            for profile_name, profile_obj in profiles.items():
                desc = f" - {profile_obj.description}" if profile_obj.description else ""
                console.print(f"  [cyan]{profile_name}[/cyan]{desc}")
                if profile_obj.base_url:
                    console.print(f"    Base URL: [dim]{profile_obj.base_url}[/dim]")
                if profile_obj.auth:
                    # Handle both single auth and list of auths
                    if isinstance(profile_obj.auth, list):
                        auth_display = f"[{len(profile_obj.auth)} auth methods]"
                        console.print(f"    Auth: [dim]{auth_display}[/dim]")
                        if verbose:
                            for i, auth_item in enumerate(profile_obj.auth, 1):
                                masked = auth_item
                                if '=' in masked:
                                    parts = masked.split('=', 1)
                                    if len(parts[1]) > 10:
                                        masked = f"{parts[0]}=***{parts[1][-4:]}"
                                console.print(f"      {i}. [dim]{masked}[/dim]")
                    else:
                        # Single auth method
                        auth_display = str(profile_obj.auth)
                        if '=' in auth_display:
                            parts = auth_display.split('=', 1)
                            if len(parts[1]) > 10:
                                auth_display = f"{parts[0]}=***{parts[1][-4:]}"
                        console.print(f"    Auth: [dim]{auth_display}[/dim]")
            console.print()
            sys.exit(0)
        
        # Handle --demo flag
        demo_schema_path = None
        if demo:
            # Use the Petstore OpenAPI schema URL
            demo_schema_url = "https://petstore3.swagger.io/api/v3/openapi.json"
            import requests
            import tempfile
            import yaml
            
            console = Console()
            console.print("\n[bold cyan]🎮 Running Demo Test[/bold cyan]")
            console.print(f"[dim]Using Petstore API: {demo_schema_url}[/dim]\n")
            
            try:
                # Download schema
                response = requests.get(demo_schema_url, timeout=10)
                response.raise_for_status()
                demo_schema = response.json()
                
                # Save to temp file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                    yaml.dump(demo_schema, f)
                    demo_schema_path = Path(f.name)
                    schema_file = str(demo_schema_path)
            except Exception as e:
                console.print(f"[red]✗ Error downloading demo schema: {e}[/red]")
                console.print("[yellow]Tip: Check your internet connection and try again.[/yellow]")
                sys.exit(1)
        
        # Schema file is required for testing (unless --demo was used)
        if not schema_file and not demo:
            click.echo(click.style("✗ Error: Schema file is required (unless using --init-config, --list-profiles, or --demo)", fg="red"), err=True)
            click.echo(click.style("Usage: apitest <schema_file> [options]", fg="yellow"), err=True)
            click.echo(click.style("  or:  apitest --demo (run demo test)", fg="yellow"), err=True)
            sys.exit(1)
        
        # Initialize config manager and load profile if specified
        config_manager = ConfigManager(config_file=Path(config) if config else None)
        
        # Load profile settings (CLI flags will override profile settings)
        profile_base_url = None
        profile_auth = None
        profile_path_params = {}
        profile_timeout = None
        
        if profile:
            profile_obj = config_manager.get_profile(profile)
            if not profile_obj:
                available = ", ".join(config_manager.list_profiles().keys())
                click.echo(click.style(f"✗ Profile '{profile}' not found.", fg="red"), err=True)
                if available:
                    click.echo(click.style(f"Available profiles: {available}", fg="yellow"), err=True)
                else:
                    click.echo(click.style("No profiles found. Create a config file first.", fg="yellow"), err=True)
                sys.exit(1)
            
            profile_base_url = profile_obj.base_url
            profile_auth = profile_obj.auth
            profile_path_params = profile_obj.path_params.copy()
            profile_timeout = profile_obj.timeout
            if verbose:
                console = Console()
                console.print(f"[dim]Using profile: [cyan]{profile}[/cyan][/dim]")
        
        # Handle --validate-auth flag
        if validate_auth:
            if not auth and not profile:
                click.echo(click.style("✗ Error: --validate-auth requires --auth or --profile", fg="red"), err=True)
                sys.exit(1)
            
            console = Console()
            console.print("\n[bold cyan]🔐 Validating Authentication Format[/bold cyan]\n")
            
            # Initialize config manager
            config_manager = ConfigManager(config_file=Path(config) if config else None)
            
            # Get auth from CLI or profile
            test_auth = auth
            if not test_auth and profile:
                profile_obj = config_manager.get_profile(profile)
                if profile_obj and profile_obj.auth:
                    test_auth = profile_obj.auth
            
            if not test_auth:
                console.print("[yellow]⚠ No authentication specified[/yellow]")
                sys.exit(0)
            
            # Convert to list if needed
            if isinstance(test_auth, str):
                auth_list = [test_auth]
            elif isinstance(test_auth, list):
                auth_list = test_auth
            else:
                auth_list = []
            
            # Validate each auth method
            all_valid = True
            for i, auth_string in enumerate(auth_list, 1):
                auth_expanded = expand_env_vars(str(auth_string))
                handler = AuthHandler()
                try:
                    handler.parse_auth_string(auth_expanded)
                    auth_type = handler.auth_type
                    if auth_type == 'bearer':
                        token_len = len(handler.token) if handler.token else 0
                        console.print(f"[green]✓[/green] Auth {i}: [cyan]{auth_type}[/cyan] token (length: {token_len} chars)")
                    elif auth_type == 'apikey':
                        location = handler.api_key_location
                        console.print(f"[green]✓[/green] Auth {i}: [cyan]{auth_type}[/cyan] - {handler.api_key_name} (location: {location})")
                    elif auth_type == 'header':
                        header_key = list(handler.custom_headers.keys())[0] if handler.custom_headers else "N/A"
                        console.print(f"[green]✓[/green] Auth {i}: [cyan]{auth_type}[/cyan] - {header_key}")
                except ValueError as e:
                    console.print(f"[red]✗[/red] Auth {i}: Invalid format")
                    console.print(f"[red]  {str(e)}[/red]")
                    all_valid = False
            
            console.print()
            if all_valid:
                console.print("[green]✓ All authentication formats are valid[/green]")
                sys.exit(0)
            else:
                console.print("[red]✗ Some authentication formats are invalid[/red]")
                sys.exit(1)
        
        # Initialize components
        schema_path = Path(schema_file) if schema_file else None
        if demo and demo_schema_path:
            schema_path = demo_schema_path
        
        # Parse schema
        parser = SchemaParser()
        schema = parser.parse(schema_path)
        
        # Validate schema
        validator = SchemaValidator()
        validation_result = validator.validate(schema)
        
        if not validation_result.is_valid:
            console = Console()
            console.print("\n[bold red]✗ Schema validation failed[/bold red]\n")
            
            for error in validation_result.errors:
                console.print(f"[red]  • {error}[/red]")
            
            # Provide helpful context for common errors
            error_text = ' '.join(validation_result.errors)
            if 'paths' in error_text.lower() and 'missing' in error_text.lower():
                console.print()
                console.print("[yellow]💡 Help:[/yellow]")
                console.print("  Your OpenAPI schema must have a 'paths' section defining your API endpoints.")
                console.print()
                console.print("  Example structure:")
                console.print("[dim]    openapi: 3.0.0[/dim]")
                console.print("[dim]    info:[/dim]")
                console.print("[dim]      title: My API[/dim]")
                console.print("[dim]    paths:[/dim]")
                console.print("[dim]      /users:[/dim]")
                console.print("[dim]        get:[/dim]")
                console.print("[dim]          summary: Get users[/dim]")
                console.print()
                console.print("  💡 Tip: Validate your schema at [link]https://editor.swagger.io[/link]")
            elif 'info' in error_text.lower() or 'title' in error_text.lower():
                console.print()
                console.print("[yellow]💡 Help:[/yellow]")
                console.print("  Your OpenAPI schema must have an 'info' section with at least a 'title' field.")
                console.print()
                console.print("  Example:")
                console.print("[dim]    info:[/dim]")
                console.print("[dim]      title: My API[/dim]")
                console.print("[dim]      version: 1.0.0[/dim]")
            
            console.print()
            sys.exit(1)
        
        # Handle --validate-schema flag
        if validate_schema:
            console = Console()
            console.print("\n[bold green]✓ Schema validation passed[/bold green]")
            if validation_result.warnings:
                console.print("\n[yellow]⚠ Warnings:[/yellow]")
                for warning in validation_result.warnings:
                    console.print(f"  • {warning}")
            
            # Count endpoints
            paths = parser.get_paths(schema)
            endpoint_count = 0
            for path_item in paths.values():
                if isinstance(path_item, dict):
                    methods = ['get', 'post', 'put', 'delete', 'patch', 'head', 'options']
                    endpoint_count += sum(1 for method in methods if method in path_item)
            
            console.print(f"\n[cyan]Found {endpoint_count} endpoint(s) in schema[/cyan]")
            console.print("\n[dim]Schema is valid and ready for testing![/dim]")
            console.print("[dim]Run without --validate-schema to execute tests.[/dim]\n")
            sys.exit(0)
        
        # Setup authentication (CLI override > Profile > Schema auto-detect)
        # Support both single auth and list of auths (for multiple attempts)
        auth_handlers = []
        
        # Determine which auth to use (CLI takes precedence)
        final_auth = auth or profile_auth
        if final_auth:
            # Convert to list if it's a single string
            if isinstance(final_auth, str):
                auth_list = [final_auth]
            elif isinstance(final_auth, list):
                auth_list = final_auth
            else:
                auth_list = []
            
            # Create auth handlers for each auth method
            for auth_string in auth_list:
                # Expand environment variables in auth string
                auth_expanded = expand_env_vars(str(auth_string))
                handler = AuthHandler()
                handler.parse_auth_string(auth_expanded)
                auth_handlers.append(handler)
        
        # If no auth from CLI or profile, create empty handler for schema auto-detect
        if not auth_handlers:
            auth_handlers = [AuthHandler()]
        
        # Parse path parameters (merge profile and CLI, CLI takes precedence)
        path_params_dict = profile_path_params.copy()
        if path_params:
            for param in path_params.split(','):
                param = param.strip()
                if '=' in param:
                    key, value = param.split('=', 1)
                    # Expand environment variables
                    path_params_dict[key.strip()] = expand_env_vars(value.strip())
        
        # Auto-apply security from schema if available and no auth provided
        if not final_auth:
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
                                # Create a new handler and add to the list
                                handler = AuthHandler()
                                if scheme_type == 'http' and scheme.get('scheme') == 'bearer':
                                    handler.parse_auth_string(f"bearer={token}")
                                elif scheme_type == 'apiKey':
                                    location = scheme.get('in', 'header')
                                    name = scheme.get('name', 'X-API-Key')
                                    handler.parse_auth_string(f"apikey={name}:{token}:{location}")
                                if handler.auth_type:  # Only add if auth was successfully set
                                    auth_handlers = [handler]
                                break
        
        # Handle base URL (CLI override > Profile > Schema > Default)
        default_base_url = 'http://localhost:8000'
        final_base_url = base_url or profile_base_url
        if final_base_url:
            # Use provided base URL (CLI or profile)
            schema['servers'] = [{'url': final_base_url.strip()}]
        else:
            # Check if schema has a valid base URL
            parser_for_url = SchemaParser()
            existing_base_url = parser_for_url.get_base_url(schema)
            # Check if base URL is empty, whitespace-only, or not a valid full URL
            if not existing_base_url or not existing_base_url.strip() or not existing_base_url.startswith(('http://', 'https://')):
                # Set default base URL
                schema['servers'] = [{'url': default_base_url}]
                if verbose:
                    console = Console()
                    console.print(f"[dim]Using default base URL: {default_base_url} (schema had invalid URL: {schema.get('servers', [{}])[0].get('url', 'N/A') if schema.get('servers') else 'N/A'})[/dim]")
        
        # Final verification - ensure we have a valid base URL (must be full URL starting with http:// or https://)
        parser_verify = SchemaParser()
        final_base_url = parser_verify.get_base_url(schema)
        if not final_base_url or not final_base_url.strip() or not final_base_url.startswith(('http://', 'https://')):
            # Force set default if somehow still invalid
            schema['servers'] = [{'url': default_base_url}]
            if verbose:
                console = Console()
                console.print(f"[yellow]Warning: Base URL was invalid ({final_base_url or 'empty'}), forcing default: {default_base_url}[/yellow]")
        
        # Determine timeout (CLI override > Profile > Default)
        # Note: timeout defaults to 30, so check if profile has a different value
        if profile_timeout is not None:
            final_timeout = timeout if timeout != 30 else profile_timeout
        else:
            final_timeout = timeout
        
        # Initialize tester with auth handlers (supports multiple for retry logic)
        tester = APITester(
            schema=schema,
            auth_handlers=auth_handlers,
            timeout=final_timeout,
            parallel=parallel,
            verbose=verbose,
            path_params=path_params_dict
        )
        
        # Count endpoints for progress and dry-run
        parser = SchemaParser()
        paths = parser.get_paths(schema)
        endpoint_count = 0
        test_cases = []
        for path, path_item in paths.items():
            if isinstance(path_item, dict):
                methods = ['get', 'post', 'put', 'delete', 'patch', 'head', 'options']
                for method in methods:
                    if method in path_item:
                        endpoint_count += 1
                        test_cases.append((method.upper(), path))
        
        console = Console()
        
        # Show welcome message
        console.print()
        console.print(f"[bold cyan]🔍 API Tester CLI v{__version__}[/bold cyan]")
        schema_name = Path(schema_file).name if schema_file else "demo schema"
        console.print(f"[dim]Testing {endpoint_count} endpoint(s) from {schema_name}[/dim]")
        console.print()
        
        # Collect path parameter warnings BEFORE tests run
        # We need to check for path parameters by inspecting the schema
        path_param_warnings = []
        import re
        for path, path_item in paths.items():
            if isinstance(path_item, dict):
                param_matches = re.finditer(r'\{([^}]+)\}', path)
                for match in param_matches:
                    param_name = match.group(1)
                    if param_name not in path_params_dict:
                        path_param_warnings.append((param_name, path))
        
        # Show path parameter warnings BEFORE tests run
        if path_param_warnings:
            console.print("[yellow]⚠ Path Parameter Warning:[/yellow]")
            unique_params = {}
            for param_name, path in path_param_warnings:
                if param_name not in unique_params:
                    unique_params[param_name] = []
                unique_params[param_name].append(path)
            
            for param_name, affected_paths in unique_params.items():
                paths_str = ', '.join(affected_paths[:3])  # Show first 3 paths
                if len(affected_paths) > 3:
                    paths_str += f" (+{len(affected_paths) - 3} more)"
                console.print(f"  [yellow]• Using default for '{param_name}' in: {paths_str}[/yellow]")
            
            console.print()
            console.print("[dim]Tip: Use --path-params to provide custom values (e.g., --path-params id=123,petId=abc)[/dim]")
            console.print()
        
        # Handle --dry-run flag
        if dry_run:
            console.print("[bold cyan]🔍 Dry Run - Preview of tests to be executed:[/bold cyan]\n")
            
            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("#", width=4, justify="right")
            table.add_column("Method", width=8, style="cyan")
            table.add_column("Endpoint", width=50)
            
            for i, (method, path) in enumerate(test_cases, 1):
                table.add_row(str(i), method, path)
            
            console.print(table)
            console.print()
            console.print(f"[dim]Would test {endpoint_count} endpoint(s) against: {final_base_url}[/dim]")
            console.print("[dim]Run without --dry-run to execute tests.[/dim]\n")
            sys.exit(0)
        
        # Run tests with progress indicator
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
            if summary_only:
                # Show only summary
                total = len(results.results)
                passed = len(results.get_passed())
                failed = len(results.get_failed())
                errors = len(results.get_errors())
                success_rate = results.get_success_rate()
                
                if failed > 0 or errors > 0:
                    console.print(f"[red]{passed}/{total} passed ({success_rate:.0f}%)[/red]")
                    sys.exit(1)
                else:
                    console.print(f"[green]{passed}/{total} passed ({success_rate:.0f}%)[/green]")
                    sys.exit(0)
            else:
                reporter.print_console_report(results, verbose)
            
            # Note: Path parameter warnings are now shown BEFORE tests run, not after
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

