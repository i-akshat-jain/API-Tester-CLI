# API Tester CLI

> Automate OpenAPI/Swagger API testing from the command line. Test your entire API in seconds.

> **Note**: This is the full documentation version. A concise version is available on [PyPI](https://pypi.org/project/apitest-cli/).

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🎯 What This Does

**API Tester CLI** reads your OpenAPI/Swagger schema file and automatically:

- ✅ Validates the schema is correctly formatted
- ✅ Tests each endpoint is reachable
- ✅ Validates response structure matches schema
- ✅ Checks status codes match documentation
- ✅ Tests authentication flows
- ✅ Generates detailed test reports (HTML, JSON, CSV)

Stop manually clicking through Postman collections. One command tests everything.

## 🚀 First 30 Seconds

Get your first API test running in under 30 seconds:

```bash
# 1. Install
pip install apitest-cli

# 2. Test a public API (no setup needed!)
apitest --demo

# 3. Test your own API
apitest your-api.yaml
```

That's it! The `--demo` flag runs a test against the public Petstore API so you can see it in action immediately.

---

## 📚 Quick Start Guide

### Installation

**Quick Install:**
```bash
pip install apitest-cli
```

**Development Install (from source):**
```bash
# Clone the repository
git clone https://github.com/i-akshat-jain/API-Tester-CLI
cd apitest-cli

# Install in development mode
pip install -e .

# Or install dependencies only
pip install -r requirements.txt
```

**Verify Installation:**
```bash
apitest --version
# Should output: apitest-cli, version 1.0.0
```

### Basic Usage

```bash
# Test an API from its OpenAPI schema
apitest schema.yaml
```

That's it! You'll see a beautiful console output with test results.

**Get Started in 3 Steps:**

1. **Try the Demo** (no setup needed):
   ```bash
   apitest --demo
   ```
   This tests the public Petstore API so you can see how it works!

2. **Get an OpenAPI Schema** - If you don't have one:
   - Look for "Download OpenAPI spec" in your API docs
   - Use the examples in `examples/` directory
   - Generate one from your API framework

3. **Run Your First Test:**
   ```bash
   # Basic test
   apitest examples/simple-api.yaml
   
   # Preview what would be tested (without making requests)
   apitest examples/simple-api.yaml --dry-run
   
   # With HTML report
   apitest examples/simple-api.yaml --format html --output my-report.html
   ```

4. **Test Your Own API:**
   ```bash
   apitest my-api-schema.yaml --auth bearer=your_token_here
   ```

### With Authentication

```bash
# Bearer token
apitest schema.yaml --auth bearer=your_token_here

# API key (header)
apitest schema.yaml --auth apikey=X-API-Key:your_key_here

# API key (query parameter)
apitest schema.yaml --auth apikey=api_key:your_key_here:query

# Custom header
apitest schema.yaml --auth header=Authorization:Custom token123

# Using environment variables (prevents tokens in command history)
# Set token first: export API_TOKEN="your-token-here"
apitest schema.yaml --auth bearer=$API_TOKEN
apitest schema.yaml --auth bearer=${API_TOKEN}

# Or inline (but environment variables are preferred for security)
apitest schema.yaml --auth bearer=your-token-here
```

**⚠️ Security Note:** For short-lived tokens and production use, always use environment variables (like Postman) instead of hardcoding tokens. Set them before running:
```bash
export API_TOKEN="your-token-here"
export PROD_TOKEN="your-production-token"
```

**Auto-Detection from Schema:** If your OpenAPI schema defines security requirements, the tool will automatically try to use tokens from environment variables (`API_TOKEN`, `API_KEY`, or `{SCHEME_NAME}_TOKEN`).

### Using Profiles (Multiple Apps/Environments)

For real-world projects with multiple apps, environments, or authentication setups, use **profiles** to keep your configurations clean and organized.

**Quick Start with Profiles:**

```bash
# 1. Set up environment variables (like Postman)
export PROD_TOKEN="your-production-token"
export STAGING_TOKEN="your-staging-token"

# 2. Create a config file with example profiles
apitest --init-config

# 3. Edit ~/.apitest/config.yaml with your profiles (use $ENV_VAR syntax)
# 4. List available profiles
apitest --list-profiles

# 5. Use a profile (tokens loaded from environment)
apitest schema.yaml --profile production
```

**💡 Tip:** Use a `.env` file (see `.env.example`) and load it with `source .env` or tools like `direnv` for easier token management.

**Config File Locations:**

The tool looks for config files in this order (first found wins):
1. `.apitest.yaml` in your current project directory (project-specific)
2. `~/.apitest/config.yaml` (user-specific, global)

**Example Config File** (`~/.apitest/config.yaml` or `.apitest.yaml`):

```yaml
profiles:
  production:
    description: Production API
    base_url: https://api.example.com
    # ⚠️ Always use environment variables for tokens (never hardcode!)
    # Set tokens before running: export PROD_TOKEN="your-token-here"
    auth: bearer=$PROD_TOKEN
    timeout: 30
    path_params:
      user_id: "123"
      account_id: "456"

  staging:
    description: Staging API
    base_url: https://staging.api.example.com
    auth: bearer=$STAGING_TOKEN
    timeout: 30

  local:
    description: Local development
    base_url: http://localhost:8000
    auth: bearer=$LOCAL_TOKEN

  app1:
    description: First API Service
    base_url: https://api1.example.com
    auth: apikey=X-API-Key:$APP1_KEY

  app2:
    description: Second API Service
    base_url: https://api2.example.com
    auth: bearer=$APP2_TOKEN
    path_params:
      tenant_id: "my-tenant"

  multi-auth:
    description: API with multiple auth methods (tries each in sequence)
    base_url: https://api.example.com
    # If first auth fails with 401/403, automatically tries next one
    auth:
      - bearer=$ADMIN_TOKEN   # Try admin token first
      - bearer=$USER_TOKEN    # Fallback to user token
      - bearer=$GUEST_TOKEN   # Fallback to guest token
```

**Setting Up Environment Variables:**

Like Postman, tokens should be stored in environment variables, not hardcoded in config files:

```bash
# Set tokens as environment variables (recommended)
export PROD_TOKEN="your-production-token"
export STAGING_TOKEN="your-staging-token"
export ADMIN_TOKEN="your-admin-token"
export USER_TOKEN="your-user-token"

# Or use a .env file (if using a tool like direnv or source)
# .env file:
# PROD_TOKEN=your-production-token
# STAGING_TOKEN=your-staging-token

# Then load it:
source .env
```

**Using Profiles:**

```bash
# Use a profile (tokens come from environment variables)
apitest schema.yaml --profile production

# Profile with CLI overrides (CLI flags take precedence)
apitest schema.yaml --profile staging --base-url https://custom-url.com

# Use a project-specific config file
apitest schema.yaml --profile local --config .apitest.yaml

# List all available profiles
apitest --list-profiles
```

**Profile Priority:** CLI flags override profile settings:
1. CLI flags (highest priority)
2. Profile settings
3. Schema auto-detection
4. Defaults (lowest priority)

This allows you to quickly override any profile setting when needed:
```bash
# Use production profile but with a different token
apitest schema.yaml --profile production --auth bearer=$OVERRIDE_TOKEN
```

**Multiple Authentication Methods (Like Django authentication_classes):**

You can specify multiple authentication methods in a profile. The tool will try each one in sequence if the previous one fails with 401 (Unauthorized) or 403 (Forbidden):

```yaml
profiles:
  multi-auth:
    description: API with multiple auth methods
    base_url: https://api.example.com
    # All tokens from environment variables (set: export ADMIN_TOKEN="...", etc.)
    auth:
      - bearer=$ADMIN_TOKEN   # Tried first
      - bearer=$USER_TOKEN    # Tried if admin fails
      - bearer=$GUEST_TOKEN   # Tried if user fails
```

**⚠️ Security Best Practice:** Never hardcode tokens in config files. Always use environment variables (like Postman) to:
- Keep tokens out of version control
- Easily rotate short-lived tokens
- Share configs without exposing secrets
- Use different tokens per environment

**How it works:**
- Each endpoint test tries the first auth method
- If it gets 401/403, automatically tries the next auth method
- Stops as soon as one succeeds (returns any status other than 401/403)
- Only tries next auth on authentication errors, not other errors (timeout, connection, etc.)
- In verbose mode, you'll see messages like: `Auth attempt 1 failed with 403, trying next auth...`

This is perfect for testing APIs where different endpoints require different permission levels, or when you want to test with multiple user roles.

### Generate HTML Report

```bash
apitest schema.yaml --format html --output report.html
```

### Path Parameters

By default, the tool generates test values for path parameters (like `{id}` or `{petId}`). You can provide custom values:

```bash
# Provide specific path parameter values
apitest schema.yaml --path-params id=123,petId=abc123

# Use environment variables
apitest schema.yaml --path-params id=$POST_ID,userId=${USER_ID}

# Note: If you don't provide values, you'll see warnings about default values
```

### Advanced Options

```bash
# Override base URL
apitest schema.yaml --base-url https://api.production.com

# Run tests in parallel
apitest schema.yaml --parallel

# Verbose output
apitest schema.yaml --verbose

# Custom timeout
apitest schema.yaml --timeout 60

# JSON output
apitest schema.yaml --format json --output results.json

# CSV output
apitest schema.yaml --format csv --output results.csv

# Combine multiple options
apitest schema.yaml --auth bearer=$TOKEN --path-params id=123 --parallel --format html
```

## 📊 Example Output

```
🔍 API Tester v1.0
============================================================

📊 Found 12 endpoints to test

Testing Endpoints:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ GET    /pets          200 OK (124ms)
✓ POST   /pets          201 Created (89ms)
✗ GET    /pets/{id}     404 Not Found (Expected: 200)
⚠ PUT    /pets/{id}     Response schema mismatch
✓ DELETE /pets/{id}     204 No Content (45ms)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 Results: 10/12 passed (83% success rate)
⏱  Total time: 3.2s
```

## 📖 Detailed Documentation

### Command-Line Options

| Option | Short | Description |
|--------|-------|-------------|
| `--base-url` | `-u` | Override base URL from schema |
| `--auth` | `-a` | Authentication string (supports `$ENV_VAR`) |
| `--path-params` | | Path parameters as `key=value,key2=value2` (supports `$ENV_VAR`) |
| `--profile` | | Use a profile from config file (e.g., `--profile production`) |
| `--config` | `-c` | Path to config file (default: `~/.apitest/config.yaml` or `.apitest.yaml`) |
| `--list-profiles` | | List available profiles and exit |
| `--init-config` | | Create example config file and exit |
| `--demo` | | Run demo test against public Petstore API (no schema file needed) |
| `--dry-run` | | Show what would be tested without making HTTP requests |
| `--validate-schema` | | Validate schema file only (do not run tests) |
| `--validate-auth` | | Validate auth format only (do not run tests) |
| `--summary-only` | | Show only summary statistics (useful for CI/CD) |
| `--format` | `-f` | Output format: `console`, `html`, `json`, `csv` |
| `--output` | `-o` | Output file path (for html/json/csv) |
| `--parallel` | `-p` | Run tests in parallel |
| `--verbose` | `-v` | Verbose output with details |
| `--timeout` | `-t` | Request timeout in seconds (default: 30) |
| `--version` | | Show version number |

### Authentication Formats

**Bearer Token:**
```bash
--auth bearer=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**API Key (Header):**
```bash
--auth apikey=X-API-Key:your_api_key_here
```

**API Key (Query Parameter):**
```bash
--auth apikey=api_key:your_api_key_here:query
```

**Custom Header:**
```bash
--auth header=Authorization:Basic base64encoded
```

### Report Formats

#### HTML Report
Beautiful, shareable HTML report with:
- Summary dashboard
- Endpoint-by-endpoint breakdown
- Color-coded results
- Response times and status codes

```bash
apitest schema.yaml --format html --output report.html
```

#### JSON Report
Machine-readable JSON output:
```json
{
  "summary": {
    "total": 12,
    "passed": 10,
    "failed": 2,
    "success_rate": 83.33,
    "total_time_seconds": 3.2
  },
  "results": [...]
}
```

#### CSV Report
Spreadsheet-friendly CSV output:
```bash
apitest schema.yaml --format csv --output results.csv
```

## 🎯 Use Cases & Common Workflows

### 1. Validate API Documentation Matches Reality
```bash
# Validate schema without running tests
apitest api-schema.yaml --validate-schema

# Run full test suite
apitest api-schema.yaml --format html
```
Ensures your OpenAPI docs accurately reflect your API.

### 2. Test After Deployments / CI/CD Pipeline
```bash
# Staging environment
apitest schema.yaml --base-url https://staging.api.com

# Production with auth
apitest schema.yaml --base-url https://api.com --auth bearer=$PROD_TOKEN

# Exit code is 0 if all pass, 1 if any fail (perfect for CI/CD)
apitest schema.yaml --format json --output results.json

# Summary-only output for CI/CD (just pass/fail counts)
apitest schema.yaml --summary-only
```

### 3. Preview Tests Before Running
```bash
# See what would be tested without making requests
apitest schema.yaml --dry-run
```

### 4. Validate Authentication Format
```bash
# Test your auth format is correct before running full tests
apitest schema.yaml --validate-auth --auth bearer=$TOKEN
```

### 5. Test Third-Party API Integrations
```bash
apitest third-party-api.yaml --auth bearer=$API_TOKEN
```
Verify third-party APIs are working correctly.

### 6. Monitor API Health
```bash
# Run as scheduled job
apitest production-api.yaml --format json --output health-check.json
```
Regular health checks with exportable results.

### 7. Testing After Code Changes
```bash
apitest schema.yaml --format html --output test-results.html
```

### 8. Testing Multiple Environments (Using Profiles)
```bash
# Set up profiles in ~/.apitest/config.yaml
apitest --init-config

# Test different environments easily
apitest schema.yaml --profile staging
apitest schema.yaml --profile production
apitest schema.yaml --profile local

# Or use CLI flags (if you prefer)
apitest schema.yaml --base-url https://staging.api.com --auth bearer=$STAGING_TOKEN
apitest schema.yaml --base-url https://api.com --auth bearer=$PROD_TOKEN
```

## 🎯 Common Patterns

### Test Local Development Server
```bash
apitest schema.yaml --base-url http://localhost:8000
```

### Test with Self-Signed SSL Certificate
Note: Currently, the tool uses the default SSL verification. For self-signed certificates, you may need to set the `REQUESTS_CA_BUNDLE` environment variable or modify the requests library settings. This is a security feature to prevent man-in-the-middle attacks.

### Test Only Specific Paths (Filtering)
Currently, the tool tests all endpoints in the schema. To test only specific paths, you can:
1. Create a filtered schema file with only the paths you want to test
2. Use schema editing tools to generate a subset

Future versions may include path filtering options like `--path-filter "/api/v1/users/*"`.

### Test Only Specific HTTP Methods
Currently, all HTTP methods defined in the schema are tested. To test only specific methods:
1. Create a filtered schema file
2. Modify the OpenAPI schema to include only the methods you want

Future versions may include method filtering like `--methods get,post`.

## 📁 Example Schemas

We've included example OpenAPI schemas in the `examples/` directory:

- `petstore.yaml` - Complete Petstore API example
- `simple-api.yaml` - Minimal API example
- `api-with-auth.yaml` - API with authentication example

## 🔧 Requirements

- **Python**: 3.8 or higher
- **Schema Format**: OpenAPI 3.0 or Swagger 2.0 (YAML or JSON)
- **Platform**: Cross-platform (Windows, macOS, Linux)

### Dependencies

- `click>=8.0.0` - CLI framework
- `requests>=2.28.0` - HTTP requests
- `pyyaml>=6.0` - YAML parsing
- `jsonschema>=4.0.0` - JSON validation
- `rich>=13.0.0` - Beautiful console output

## 🆚 Comparison with Other Tools

| Feature | API Tester CLI | Postman Free | curl scripts |
|---------|---------------|--------------|--------------|
| One-command testing | ✅ | ❌ | ❌ |
| Schema validation | ✅ | Limited | ❌ |
| CI/CD ready | ✅ | Paid only | Manual |
| No rate limits | ✅ | ❌ | ✅ |
| Lightweight | ✅ | ❌ | ✅ |
| HTML reports | ✅ | Paid only | ❌ |
| Authentication | ✅ | ✅ | Manual |
| Parallel execution | ✅ | Paid | Manual |

## 🐛 Troubleshooting

### Installation Issues

**"command not found: apitest"**
- Make sure pip install directory is in your PATH
- Try: `python -m apitest.cli --version`
- On macOS/Linux: `pip install --user apitest-cli`
- Use a virtual environment: `python -m venv venv && source venv/bin/activate`

**Import Errors**
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check Python version: `python --version` (requires 3.8+)

**Permission Errors**
- Use `pip install --user apitest-cli` instead
- Or use a virtual environment

### Runtime Issues

**"Schema validation failed"**
- Ensure your OpenAPI file is valid YAML or JSON
- Check that required fields (`openapi`, `info`, `paths`) are present
- Validate your schema at [editor.swagger.io](https://editor.swagger.io)

**"Connection error"**
- Verify the base URL in your schema or use `--base-url`
- Check network connectivity
- Ensure the API server is running

**"Timeout"**
- Increase timeout: `--timeout 60`
- Check if API is responding slowly
- Consider using `--parallel` for faster execution

**Authentication Issues**
- Verify your auth token is valid
- Check auth format matches: `bearer=TOKEN` or `apikey=KEY:VALUE`
- Use `--verbose` to see request headers

**Debugging Failed Tests**
```bash
# Get detailed output
apitest schema.yaml --verbose
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📝 License

MIT License - see LICENSE file for details

## 💬 Support

- **Issues**: [GitHub Issues](https://github.com/i-akshat-jain/API-Tester-CLI/issues)
- **Email**: akshatjain1502@gmail.com

## 📚 Additional Resources

- **Changelog**: See [CHANGELOG.md](CHANGELOG.md) for version history
- **Examples**: Check the `examples/` directory for sample OpenAPI schemas
- **Full Documentation**: All documentation is in this README - your single source of truth!
- **Issues**: Found a bug or have a feature request? [Open an issue](https://github.com/i-akshat-jain/API-Tester-CLI/issues)
- **Contributing**: Contributions welcome! Please feel free to submit a Pull Request.

## 🚀 Roadmap

- [ ] OAuth 2.0 flow support
- [ ] GraphQL schema support
- [ ] Custom test assertions
- [ ] Performance benchmarking
- [ ] Integration with CI/CD platforms

---

**Made with ❤️ for developers who hate repetitive manual testing**
