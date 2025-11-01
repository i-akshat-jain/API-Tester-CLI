# API Tester CLI

> Automate OpenAPI/Swagger API testing from the command line. Test your entire API in seconds.

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

## 🚀 Quick Start

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

1. **Get an OpenAPI Schema** - If you don't have one:
   - Look for "Download OpenAPI spec" in your API docs
   - Use the examples in `examples/` directory
   - Generate one from your API framework

2. **Run Your First Test:**
   ```bash
   # Basic test
   apitest examples/simple-api.yaml
   
   # With HTML report
   apitest examples/simple-api.yaml --format html --output my-report.html
   ```

3. **Test Your Own API:**
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
apitest schema.yaml --auth bearer=$API_TOKEN
apitest schema.yaml --auth bearer=${API_TOKEN}
```

**Auto-Detection from Schema:** If your OpenAPI schema defines security requirements, the tool will automatically try to use tokens from environment variables (`API_TOKEN`, `API_KEY`, or `{SCHEME_NAME}_TOKEN`).

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
```

### 3. Test Third-Party API Integrations
```bash
apitest third-party-api.yaml --auth bearer=$API_TOKEN
```
Verify third-party APIs are working correctly.

### 4. Monitor API Health
```bash
# Run as scheduled job
apitest production-api.yaml --format json --output health-check.json
```
Regular health checks with exportable results.

### 5. Testing After Code Changes
```bash
apitest schema.yaml --format html --output test-results.html
```

### 6. Testing Multiple Environments
```bash
# Staging
apitest schema.yaml --base-url https://staging.api.com

# Production
apitest schema.yaml --base-url https://api.com --auth bearer=$PROD_TOKEN
```

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

## 🚀 Roadmap

- [ ] OAuth 2.0 flow support
- [ ] GraphQL schema support
- [ ] Custom test assertions
- [ ] Performance benchmarking
- [ ] Integration with CI/CD platforms

---

**Made with ❤️ for developers who hate repetitive manual testing**
