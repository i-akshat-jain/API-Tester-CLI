# Changelog

All notable changes to API Tester CLI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-12-XX

### Added
- Initial release of API Tester CLI
- OpenAPI 3.0 and Swagger 2.0 schema parsing
- Automatic endpoint testing from OpenAPI schemas
- Response schema validation using JSON Schema
- Status code validation
- Multiple authentication methods:
  - Bearer token authentication
  - API key authentication (header and query parameter)
  - Custom header authentication
  - Environment variable support for tokens
  - Multiple authentication fallback support
- Path parameter handling with custom values
- Multiple report formats:
  - Beautiful console output with Rich
  - HTML reports with detailed breakdowns
  - JSON reports for programmatic access
  - CSV reports for spreadsheet analysis
- Profile support for multiple environments/apps
- Configuration file support (`.apitest.yaml` or `~/.apitest/config.yaml`)
- Parallel test execution
- Verbose mode for detailed debugging
- Demo mode (`--demo` flag) to test public APIs instantly
- Dry-run mode (`--dry-run`) to preview tests without executing
- Schema validation mode (`--validate-schema`)
- Auth validation mode (`--validate-auth`)
- Summary-only mode (`--summary-only`) for CI/CD pipelines
- CI/CD friendly exit codes (0 for success, 1 for failures)
- Comprehensive error messages with helpful context
- Auto-detection of security schemes from OpenAPI schema
- Support for all HTTP methods (GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS)
- Custom timeout configuration
- Base URL override support

### Documentation
- Comprehensive README with quick start guide
- Examples directory with sample OpenAPI schemas
- Configuration examples
- Troubleshooting guide

### Tests
- Unit tests for core functionality
- Schema parser tests
- Validator tests
- Authentication handler tests

[1.0.0]: https://github.com/i-akshat-jain/API-Tester-CLI/releases/tag/v1.0.0
