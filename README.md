# API Tester CLI

> Automate OpenAPI/Swagger API testing from the command line. Test your entire API in seconds.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🎯 What This Does

Automatically tests your OpenAPI/Swagger API:
- ✅ Validates schema format
- ✅ Tests all endpoints
- ✅ Validates responses match schema
- ✅ Checks status codes
- ✅ Tests authentication flows
- ✅ Generates reports (HTML, JSON, CSV)
- ✅ Local test history & baseline tracking
- ✅ Secure token caching

## 🚀 Quick Start

```bash
# Install
pip install apitest-cli

# Try demo (no setup needed)
apitest --demo

# Test your API
apitest schema.yaml

# With authentication
apitest schema.yaml --auth bearer=$TOKEN

# Store results & cache token
apitest schema.yaml --store-results --use-cached-token --auth bearer=$TOKEN
```

---

## 📚 Installation

```bash
pip install apitest-cli
```

**Verify:** `apitest --version`

## 💻 Usage

### Basic Testing

```bash
# Test schema
apitest schema.yaml

# Preview tests (no requests)
apitest schema.yaml --dry-run

# HTML report
apitest schema.yaml --format html --output report.html
```

### Authentication

```bash
# Bearer token
apitest schema.yaml --auth bearer=$TOKEN

# API key (header)
apitest schema.yaml --auth apikey=X-API-Key:$API_KEY

# API key (query)
apitest schema.yaml --auth apikey=api_key:$API_KEY:query

# Custom header
apitest schema.yaml --auth header=Authorization:Custom $TOKEN
```

**💡 Tip:** Use environment variables for security:
```bash
export API_TOKEN="your-token-here"
apitest schema.yaml --auth bearer=$API_TOKEN
```

Auto-detects tokens from schema security requirements using env vars (`API_TOKEN`, `API_KEY`, or `{SCHEME_NAME}_TOKEN`).

### OAuth 2.0 Authentication

API Tester CLI supports OAuth 2.0 flows for APIs that require OAuth authentication. Tokens are automatically fetched, cached securely, and refreshed when needed.

#### Client Credentials Flow

Best for server-to-server authentication (no user interaction):

```yaml
# In ~/.apitest/config.yaml or .apitest.yaml
profiles:
  oauth-api:
    base_url: https://api.example.com
    auth:
      type: oauth2
      grant_type: client_credentials
      token_url: https://auth.example.com/oauth/token
      client_id: $OAUTH_CLIENT_ID
      client_secret: $OAUTH_CLIENT_SECRET
      scope: read write  # Optional
```

**Usage:**
```bash
# Set credentials
export OAUTH_CLIENT_ID="your-client-id"
export OAUTH_CLIENT_SECRET="your-client-secret"

# Use profile
apitest schema.yaml --profile oauth-api

# With token caching (recommended)
apitest schema.yaml --profile oauth-api --use-cached-token
```

#### Password Grant Flow

For APIs that support username/password authentication:

```yaml
profiles:
  oauth-password-api:
    base_url: https://api.example.com
    auth:
      type: oauth2
      grant_type: password
      token_url: https://auth.example.com/oauth/token
      client_id: $OAUTH_CLIENT_ID
      client_secret: $OAUTH_CLIENT_SECRET
      username: $OAUTH_USERNAME
      password: $OAUTH_PASSWORD
      scope: read write  # Optional
```

**Usage:**
```bash
export OAUTH_CLIENT_ID="your-client-id"
export OAUTH_CLIENT_SECRET="your-client-secret"
export OAUTH_USERNAME="your-username"
export OAUTH_PASSWORD="your-password"

apitest schema.yaml --profile oauth-password-api --use-cached-token
```

#### Token Caching Behavior

- **Automatic caching**: Tokens are stored securely in your system keyring (macOS Keychain, Windows Credential Manager, Linux Secret Service)
- **Automatic refresh**: If a refresh token is available, expired tokens are automatically refreshed
- **Fallback**: If refresh fails, a new token is fetched automatically
- **Cache key**: Based on `grant_type`, `token_url`, `client_id`, and `scope` (ensures separate tokens for different configurations)

**Benefits:**
- ✅ No need to manually fetch tokens
- ✅ Tokens persist across sessions
- ✅ Automatic expiration handling
- ✅ Secure storage (never in plain text)

#### OAuth Troubleshooting

**Error: "OAuth token request failed"**
- Verify `token_url` is correct and accessible
- Check `client_id` and `client_secret` are valid
- Ensure network connectivity to token endpoint
- Check if scope is required and correctly specified

**Error: "OAuth configuration incomplete"**
- Ensure all required fields are present in config:
  - `type: oauth2`
  - `grant_type: client_credentials` or `password`
  - `token_url`
  - `client_id`
  - `client_secret`
- For password grant, also require `username` and `password`

**Error: "invalid_client" or "401 Unauthorized"**
- Verify client credentials are correct
- Check if client is active/enabled in OAuth provider
- Verify token URL matches provider's endpoint

**Token not refreshing**
- Check if provider returns `refresh_token` in response
- Verify refresh token hasn't expired
- Some providers don't support refresh tokens for client_credentials flow

**Environment variables not expanding**
- Use `$VAR` syntax (not `${VAR}` in config files)
- Ensure variables are exported before running: `export OAUTH_CLIENT_ID="value"`
- Check variable names match exactly (case-sensitive)

**Example with GitHub OAuth:**
```yaml
profiles:
  github-api:
    base_url: https://api.github.com
    auth:
      type: oauth2
      grant_type: client_credentials
      token_url: https://github.com/login/oauth/access_token
      client_id: $GITHUB_CLIENT_ID
      client_secret: $GITHUB_CLIENT_SECRET
```

### Profiles (Multiple Environments)

```bash
# Create config file
apitest --init-config

# List profiles
apitest --list-profiles

# Use profile
apitest schema.yaml --profile production
```

**Config File** (`~/.apitest/config.yaml` or `.apitest.yaml`):
```yaml
profiles:
  production:
    base_url: https://api.example.com
    auth: bearer=$PROD_TOKEN
    timeout: 30
  
  staging:
    base_url: https://staging.api.example.com
    auth: bearer=$STAGING_TOKEN
  
  multi-auth:
    base_url: https://api.example.com
    # Tries each auth in sequence if previous fails
    auth:
      - bearer=$ADMIN_TOKEN
      - bearer=$USER_TOKEN
```

**Priority:** CLI flags > Profile > Schema > Defaults

### Test History & Token Caching

```bash
# Store test results locally (for baseline tracking & learning)
apitest schema.yaml --store-results

# Cache & reuse tokens (stored securely in system keyring)
apitest schema.yaml --use-cached-token --auth bearer=$TOKEN

# Both together
apitest schema.yaml --store-results --use-cached-token --auth bearer=$TOKEN
```

**Features:**
- Test results saved to `~/.apitest/data.db` (local SQLite)
- Tokens stored in system keyring (macOS Keychain / Windows Credential Manager / Linux Secret Service)
- Automatic baseline tracking (first successful test becomes baseline)
- All data stored locally - never sent to external servers

### Advanced Options

```bash
# Path parameters
apitest schema.yaml --path-params id=123,petId=abc

# Parallel execution
apitest schema.yaml --parallel

# Custom timeout
apitest schema.yaml --timeout 60

# Output formats
apitest schema.yaml --format json --output results.json
apitest schema.yaml --format csv --output results.csv
apitest schema.yaml --format html --output report.html

# Verbose output
apitest schema.yaml --verbose
```

## 📊 Example Output

```
🔍 API Tester CLI v1.0.0
Testing 12 endpoint(s) from schema.yaml

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ GET    /pets          200 OK (124ms)
✓ POST   /pets          201 Created (89ms)
✗ GET    /pets/{id}     404 Not Found (Expected: 200)
⚠ PUT    /pets/{id}     Response schema mismatch
✓ DELETE /pets/{id}     204 No Content (45ms)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 Results: 10/12 passed (83% success rate)
⏱  Total time: 3.2s
✓ Test results saved to local database
```

## 📖 Command Reference

### All Options

| Option | Short | Description |
|--------|-------|-------------|
| `--base-url` | `-u` | Override base URL |
| `--auth` | `-a` | Auth: `bearer=$TOKEN`, `apikey=X-API-Key:$KEY`, etc. |
| `--path-params` | | Path params: `id=123,petId=abc` |
| `--profile` | | Use profile from config |
| `--config` | `-c` | Config file path |
| `--list-profiles` | | List available profiles |
| `--init-config` | | Create example config file |
| `--demo` | | Run demo against Petstore API |
| `--dry-run` | | Preview tests without running |
| `--validate-schema` | | Validate schema only |
| `--validate-auth` | | Validate auth format only |
| `--summary-only` | | Show summary only (CI/CD) |
| `--store-results` | | Save results to local database |
| `--use-cached-token` | | Use/cache tokens from keyring |
| `--format` | `-f` | Output: `console`, `html`, `json`, `csv` |
| `--output` | `-o` | Output file path |
| `--parallel` | `-p` | Run tests in parallel |
| `--verbose` | `-v` | Verbose output |
| `--timeout` | `-t` | Request timeout (default: 30s) |
| `--version` | | Show version |

## 🎯 Common Workflows

### CI/CD Integration
```bash
# Exit code: 0 if all pass, 1 if any fail
apitest schema.yaml --summary-only --format json --output results.json
```

### Health Monitoring
```bash
# Scheduled health checks
apitest schema.yaml --store-results --format json --output health.json
```

### Development Testing
```bash
# Local server
apitest schema.yaml --base-url http://localhost:8000 --verbose

# Preview before running
apitest schema.yaml --dry-run
```

## 🔧 Requirements

- **Python**: 3.8+
- **Schema**: OpenAPI 3.0 or Swagger 2.0 (YAML/JSON)
- **Platform**: Windows, macOS, Linux

## 🆚 Why Use This?

✅ One-command API testing  
✅ CI/CD ready (exit codes, JSON output)  
✅ No rate limits  
✅ Lightweight & fast  
✅ Free (MIT License)  
✅ Local storage & token caching  
✅ Beautiful HTML reports

## 🐛 Troubleshooting

**"command not found: apitest"**
```bash
python -m apitest.cli --version
pip install --user apitest-cli
```

**Schema validation failed**
- Validate at [editor.swagger.io](https://editor.swagger.io)
- Check required fields: `openapi`, `info`, `paths`

**Connection/timeout errors**
```bash
# Increase timeout
apitest schema.yaml --timeout 60

# Check URL
apitest schema.yaml --base-url https://api.example.com --verbose
```

**Debug mode**
```bash
apitest schema.yaml --verbose
```

**OAuth errors**
- Check token endpoint is accessible: `curl https://auth.example.com/oauth/token`
- Verify credentials with OAuth provider
- Use `--verbose` to see detailed OAuth flow logs
- Check token cache: tokens stored in system keyring (use keyring CLI tools to inspect)

## 🤝 Contributing

Contributions welcome! Please feel free to submit a Pull Request.

## 📝 License

MIT License - see LICENSE file for details

## 💬 Support

- **Issues**: [GitHub Issues](https://github.com/i-akshat-jain/API-Tester-CLI/issues)
- **Email**: akshatjain1502@gmail.com

## 📚 Resources

- **Examples**: See `examples/` directory
- **Changelog**: [CHANGELOG.md](CHANGELOG.md)
- **Integration Tests**: See [tests/README_INTEGRATION_TESTS.md](tests/README_INTEGRATION_TESTS.md) for OAuth integration testing guide

---

**Made with ❤️ for developers who hate repetitive manual testing**
