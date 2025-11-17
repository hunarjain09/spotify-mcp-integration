# Integration Tests

This directory contains integration tests for the Agent SDK implementation.

## Test Files

### Mocked Tests (Run Anywhere - No Dependencies)

These tests use mocked network calls and can run in CI/CD or without any external dependencies:

- **`test_agent_api_mocked.py`** - Mocked API integration test
  - Simulates full API workflow without actual server
  - No Anthropic API calls
  - No Spotify API calls
  - Fast execution (~2 seconds)
  - **Use this for:** CI/CD pipelines, quick validation

- **`test_agent_performance_mocked.py`** - Mocked performance test
  - Simulates Agent SDK execution without dependencies
  - Returns realistic timing data
  - No external API calls required
  - **Use this for:** Performance baseline without hitting APIs

### Real Integration Tests (Require Running Services)

These tests require actual running services and credentials:

- **`test_agent_api_real.py`** - Real API integration test
  - **Requires:**
    - API server running (`./run.sh` or `uvicorn api.app_agent:app`)
    - `ANTHROPIC_API_KEY` in `.env`
    - Spotify authentication (`.cache-spotify`)
  - Makes real Anthropic API calls
  - Makes real Spotify API calls
  - Execution time: ~25-30 seconds
  - **Use this for:** End-to-end validation before deployment

- **`test_agent_performance_real.py`** - Real performance test
  - **Requires:**
    - `ANTHROPIC_API_KEY` in `.env`
    - Spotify authentication (`.cache-spotify`)
    - MCP server dependencies
  - Tests actual Agent SDK performance
  - Measures real Claude + Spotify timing
  - **Use this for:** Performance profiling, optimization

### Other Integration Tests

- **`test_api_endpoints.py`** - API endpoint tests
- **`test_mcp_integration.py`** - MCP server integration tests
- **`test_spotify_search.py`** - Spotify search functionality tests
- **`test_workflow_integration.py`** - Workflow integration tests (deprecated)

## Running Tests

### Quick Validation (Mocked - No Setup Required)

```bash
# Run mocked API test
python tests/integration/test_agent_api_mocked.py

# Run mocked performance test
python tests/integration/test_agent_performance_mocked.py
```

**Expected output:**
```
🎉 Test completed successfully!
✅ All assertions passed!
```

### Full Integration Testing (Requires Setup)

**Step 1: Set up environment**
```bash
# Copy environment template
cp .env.example .env

# Add your keys
# - ANTHROPIC_API_KEY
# - SPOTIFY_CLIENT_ID
# - SPOTIFY_CLIENT_SECRET

# Authenticate with Spotify
python mcp_server/spotify_server.py
# Follow OAuth flow, then Ctrl+C
```

**Step 2: Run API integration test**
```bash
# Terminal 1: Start API server
./run.sh

# Terminal 2: Run test
python tests/integration/test_agent_api_real.py
```

**Expected:** ~25 seconds, successful track match with 99% confidence

**Step 3: Run performance test**
```bash
# Direct execution (no API server needed)
python tests/integration/test_agent_performance_real.py
```

**Expected:** ~23 seconds, performance breakdown

## Using pytest

Run all integration tests:
```bash
# All integration tests
pytest tests/integration/

# Specific test file
pytest tests/integration/test_mcp_integration.py

# With verbose output
pytest tests/integration/ -v

# With coverage
pytest tests/integration/ --cov=api --cov=agent_executor
```

## Test Structure

```
tests/integration/
├── README.md                          # This file
├── test_agent_api_mocked.py          ✅ Mocked (CI-friendly)
├── test_agent_api_real.py            ⚠️ Requires server
├── test_agent_performance_mocked.py  ✅ Mocked (CI-friendly)
├── test_agent_performance_real.py    ⚠️ Requires auth
├── test_api_endpoints.py             🧪 API tests
├── test_mcp_integration.py           🧪 MCP tests
├── test_spotify_search.py            🧪 Spotify tests
└── test_workflow_integration.py      ⚠️ Deprecated
```

## Continuous Integration

For CI/CD pipelines, use mocked tests to avoid requiring secrets and external services:

```yaml
# .github/workflows/test.yml
name: Test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python tests/integration/test_agent_api_mocked.py
      - run: python tests/integration/test_agent_performance_mocked.py
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'httpx'"

Install test dependencies:
```bash
pip install httpx pytest pytest-asyncio
```

### "API server not running"

For `test_agent_api_real.py`:
```bash
# Start the server first
./run.sh
```

### "Anthropic API key invalid"

For real tests:
```bash
# Check .env file
cat .env | grep ANTHROPIC_API_KEY

# Should show: ANTHROPIC_API_KEY=sk-ant-...
```

### "Spotify authentication failed"

Re-authenticate:
```bash
rm .cache-spotify
python mcp_server/spotify_server.py
```

## Best Practices

1. **Use mocked tests for CI/CD** - Fast, no secrets required
2. **Use real tests before deployment** - Validate end-to-end
3. **Run performance tests** - Baseline before optimizations
4. **Don't commit secrets** - Keep `.env` in `.gitignore`

## Related Documentation

- [AGENT_INTEGRATION.md](../../AGENT_INTEGRATION.md) - Agent SDK guide
- [PERFORMANCE_TEST_RESULTS.md](../../PERFORMANCE_TEST_RESULTS.md) - Performance analysis
- [PROJECT_STRUCTURE.md](../../PROJECT_STRUCTURE.md) - Codebase structure
