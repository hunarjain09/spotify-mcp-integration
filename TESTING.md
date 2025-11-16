# Testing Guide

This guide explains how to run and write tests for the Spotify MCP Integration project.

## Table of Contents

1. [Overview](#overview)
2. [Test Structure](#test-structure)
3. [Running Tests](#running-tests)
4. [Test Coverage](#test-coverage)
5. [Writing Tests](#writing-tests)
6. [Test Categories](#test-categories)
7. [Continuous Integration](#continuous-integration)
8. [Best Practices](#best-practices)

## Overview

The project uses **pytest** as the testing framework with the following key tools:

- **pytest** - Testing framework
- **pytest-asyncio** - Async test support
- **pytest-cov** - Code coverage reporting
- **pytest-mock** - Mocking utilities
- **pytest-httpx** - HTTP mocking for API tests
- **faker** - Test data generation
- **freezegun** - Time manipulation in tests

### Test Philosophy

- **Comprehensive Coverage**: All components have corresponding tests
- **Fast Execution**: Unit tests run in < 1 second, full suite in < 30 seconds
- **Isolated Tests**: Each test is independent and can run in any order
- **Real-world Scenarios**: Tests cover both happy paths and edge cases

## Test Structure

```
tests/
├── conftest.py                    # Shared fixtures and configuration
├── unit/                          # Unit tests (individual components)
│   ├── test_data_models.py       # Data model tests
│   ├── test_api_models.py        # API request/response model tests
│   ├── test_settings.py          # Configuration tests
│   └── test_fuzzy_matcher.py     # Fuzzy matching algorithm tests
├── integration/                   # Integration tests (multiple components)
│   ├── test_api_endpoints.py     # FastAPI endpoint tests
│   └── test_spotify_search.py    # Spotify search activity tests
└── pytest.ini                     # Pytest configuration

```

## Running Tests

### Prerequisites

1. Ensure you're in the virtual environment:
   ```bash
   source venv/bin/activate  # macOS/Linux
   # or
   venv\Scripts\activate  # Windows
   ```

2. Install test dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Run All Tests

```bash
pytest
```

### Run Specific Test Categories

Run only unit tests:
```bash
pytest tests/unit/
```

Run only integration tests:
```bash
pytest tests/integration/
```

Run tests by marker:
```bash
pytest -m unit           # Unit tests
pytest -m integration    # Integration tests
pytest -m "not slow"     # Skip slow tests
```

### Run Specific Test Files

```bash
pytest tests/unit/test_data_models.py
pytest tests/integration/test_api_endpoints.py
```

### Run Specific Test Functions

```bash
pytest tests/unit/test_data_models.py::TestSongMetadata::test_create_with_all_fields
pytest tests/integration/test_api_endpoints.py::TestSyncEndpoint::test_sync_song_success
```

### Run with Verbose Output

```bash
pytest -v                # Verbose
pytest -vv               # Extra verbose
pytest -s                # Show print statements
```

### Run Tests in Parallel

For faster execution (requires pytest-xdist):

```bash
pip install pytest-xdist
pytest -n auto           # Use all CPU cores
pytest -n 4              # Use 4 workers
```

## Test Coverage

### Generate Coverage Report

Run tests with coverage:
```bash
pytest --cov
```

Generate detailed HTML report:
```bash
pytest --cov --cov-report=html
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

### Coverage Requirements

The project maintains **80%+ code coverage** as configured in `pytest.ini`:

```ini
--cov-fail-under=80
```

Tests will fail if coverage drops below this threshold.

### View Coverage by File

```bash
pytest --cov --cov-report=term-missing
```

Example output:
```
Name                                    Stmts   Miss  Cover   Missing
---------------------------------------------------------------------
models/data_models.py                     153      5    97%   45-47, 89
api/models.py                             164      8    95%   102-105
activities/fuzzy_matcher.py               147      3    98%   78-80
config/settings.py                         72      2    97%   65-66
---------------------------------------------------------------------
TOTAL                                    1234     42    97%
```

### Exclude from Coverage

Some files are excluded from coverage (see `pytest.ini`):
- Test files themselves
- `__pycache__` directories
- Virtual environment
- Setup scripts

## Writing Tests

### Test File Naming

- Unit tests: `test_<module_name>.py`
- Integration tests: `test_<component>_<action>.py`
- Test classes: `Test<ComponentName>`
- Test functions: `test_<what_it_tests>`

### Basic Test Structure

```python
"""Tests for the component."""

import pytest
from your.module import YourClass


class TestYourClass:
    """Tests for YourClass."""

    def test_basic_functionality(self):
        """Test basic functionality works as expected."""
        # Arrange
        obj = YourClass()

        # Act
        result = obj.method()

        # Assert
        assert result == expected_value

    def test_error_handling(self):
        """Test that errors are handled correctly."""
        obj = YourClass()

        with pytest.raises(ValueError):
            obj.method_that_raises()
```

### Using Fixtures

Fixtures are reusable test components defined in `conftest.py`:

```python
def test_with_sample_data(sample_song_metadata, sample_spotify_track):
    """Test using fixtures from conftest.py."""
    # sample_song_metadata and sample_spotify_track are automatically provided
    assert sample_song_metadata.title == "Bohemian Rhapsody"
    assert sample_spotify_track.track_id == "7tFiyTwD0nx5a1eklYtX2J"
```

### Available Fixtures

#### Data Fixtures
- `sample_song_metadata` - Complete song metadata
- `sample_song_metadata_no_isrc` - Song metadata without ISRC
- `sample_spotify_track` - Single Spotify track result
- `sample_spotify_tracks` - List of Spotify tracks
- `sample_match_result` - Fuzzy match result
- `sample_workflow_input` - Workflow input
- `sample_workflow_result` - Workflow result
- `sample_api_request` - API request model

#### Mock Fixtures
- `mock_mcp_client` - Mocked MCP client
- `mock_spotify_client` - Mocked Spotipy client
- `mock_openai_client` - Mocked OpenAI client
- `mock_temporal_client` - Mocked Temporal client
- `mock_langchain_llm` - Mocked LangChain LLM

#### Factory Fixtures
- `make_song_metadata()` - Create custom song metadata
- `make_spotify_track()` - Create custom Spotify track

#### Environment Fixtures
- `test_env` - Auto-applied test environment setup
- `temp_env()` - Temporarily modify environment variables

### Async Tests

Use `@pytest.mark.asyncio` for async functions:

```python
import pytest


class TestAsyncFunction:
    @pytest.mark.asyncio
    async def test_async_operation(self):
        """Test an async operation."""
        result = await async_function()
        assert result is not None
```

### Mocking

#### Mock External API Calls

```python
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
@patch("module.get_spotify_client")
async def test_with_mocked_spotify(mock_get_client):
    """Test with mocked Spotify API."""
    # Setup mock
    mock_client = AsyncMock()
    mock_client.search.return_value = {"tracks": []}
    mock_get_client.return_value = mock_client

    # Run test
    result = await function_that_uses_spotify()

    # Verify
    assert result == expected
    mock_client.search.assert_called_once()
```

#### Mock Environment Variables

```python
def test_with_custom_env(temp_env):
    """Test with custom environment variables."""
    temp_env(
        SPOTIFY_CLIENT_ID="test_id",
        OPENAI_API_KEY="test_key",
    )

    from config.settings import Settings
    settings = Settings()

    assert settings.spotify_client_id == "test_id"
```

### Parametrized Tests

Test multiple scenarios with one test function:

```python
@pytest.mark.parametrize(
    "threshold,expected_match",
    [
        (0.5, True),   # Low threshold - should match
        (0.9, False),  # High threshold - shouldn't match
        (1.0, False),  # Perfect threshold - shouldn't match
    ],
)
def test_different_thresholds(threshold, expected_match):
    """Test matching with different thresholds."""
    result = fuzzy_match(track, threshold)
    assert result.is_match == expected_match
```

## Test Categories

### Unit Tests (`@pytest.mark.unit`)

Test individual components in isolation:

**What to test:**
- Data model validation
- Helper functions
- Configuration loading
- Algorithm correctness

**Example:**
```python
@pytest.mark.unit
def test_song_metadata_to_search_query():
    """Test search query generation."""
    song = SongMetadata(
        title="Bohemian Rhapsody",
        artist="Queen",
        album="A Night at the Opera",
    )

    query = song.to_search_query()

    assert query == "track:Bohemian Rhapsody artist:Queen album:A Night at the Opera"
```

### Integration Tests (`@pytest.mark.integration`)

Test multiple components working together:

**What to test:**
- API endpoints with mocked Temporal
- Activities with mocked external APIs
- Database operations
- MCP client/server communication

**Example:**
```python
@pytest.mark.integration
def test_sync_endpoint(client, mock_temporal_client):
    """Test full sync endpoint flow."""
    response = client.post("/api/v1/sync", json={
        "track_name": "Test Song",
        "artist": "Test Artist",
        "playlist_id": "37i9dQZF1DXcBWIGoYBM5M",
    })

    assert response.status_code == 202
    assert "workflow_id" in response.json()
    mock_temporal_client.start_workflow.assert_called_once()
```

### Workflow Tests (`@pytest.mark.workflow`)

Test Temporal workflows:

```python
@pytest.mark.workflow
async def test_music_sync_workflow(mock_temporal_client):
    """Test complete workflow execution."""
    # Setup test environment for Temporal
    from temporalio.testing import WorkflowEnvironment

    async with WorkflowEnvironment() as env:
        # Test workflow logic
        pass
```

### End-to-End Tests (`@pytest.mark.e2e`)

Test complete user flows (may require running services):

```python
@pytest.mark.e2e
@pytest.mark.slow
async def test_full_sync_flow():
    """Test complete sync from API to playlist."""
    # This would test with real services running
    pass
```

## Test Data Best Practices

### Use Realistic Data

```python
# Good
song = SongMetadata(
    title="Bohemian Rhapsody",
    artist="Queen",
    album="A Night at the Opera",
    duration_ms=354000,
    isrc="GBUM71029604",
)

# Bad
song = SongMetadata(
    title="Test",
    artist="Test",
)
```

### Test Edge Cases

```python
def test_empty_search_results():
    """Test handling of empty results."""
    result = fuzzy_match(song, [])
    assert result.is_match is False

def test_very_long_track_name():
    """Test handling of unusually long track names."""
    song = SongMetadata(
        title="x" * 500,  # Very long title
        artist="Artist",
    )
    # Should handle gracefully
```

### Test Boundary Conditions

```python
@pytest.mark.parametrize("threshold", [0.0, 0.5, 1.0])
def test_threshold_boundaries(threshold):
    """Test threshold boundary values."""
    workflow_input = WorkflowInput(
        song_metadata=song,
        playlist_id="test",
        user_id="user",
        match_threshold=threshold,
    )
    assert 0.0 <= workflow_input.match_threshold <= 1.0
```

## Continuous Integration

### GitHub Actions Workflow

The project includes a CI/CD pipeline that runs on every push:

```yaml
# .github/workflows/test.yml
name: Tests

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
      - run: pytest --cov --cov-report=xml
      - uses: codecov/codecov-action@v2
```

### Pre-commit Hooks

Install pre-commit hooks to run tests before committing:

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install
```

## Best Practices

### DO's

✅ **Write tests first** (TDD) when adding new features
✅ **Keep tests independent** - each test should work in isolation
✅ **Use descriptive test names** - explain what is being tested
✅ **Test both success and failure paths**
✅ **Mock external dependencies** (APIs, databases)
✅ **Use fixtures** for common test data
✅ **Assert specific values** rather than just "is not None"
✅ **Clean up after tests** (though pytest usually handles this)

### DON'Ts

❌ **Don't test implementation details** - test behavior
❌ **Don't make tests depend on each other**
❌ **Don't use sleep()** - use proper async/await or mocking
❌ **Don't test third-party libraries** - assume they work
❌ **Don't commit failing tests**
❌ **Don't skip tests without a good reason**
❌ **Don't hardcode credentials** - use environment variables

### Example: Good vs Bad Tests

**Bad Test:**
```python
def test_stuff():
    """Test stuff."""  # Vague name
    x = function()
    assert x  # What are we testing?
```

**Good Test:**
```python
def test_fuzzy_match_returns_highest_scoring_track(
    sample_song_metadata,
    sample_spotify_tracks
):
    """Test that fuzzy matching returns the track with highest combined score."""
    result = fuzzy_match(sample_song_metadata, sample_spotify_tracks, threshold=0.85)

    assert result.is_match is True
    assert result.confidence_score > 0.85
    assert result.matched_track.track_id == "7tFiyTwD0nx5a1eklYtX2J"
```

## Debugging Failed Tests

### Run with Debug Output

```bash
pytest -vv -s --tb=long
```

### Run Single Test with Debugging

```bash
pytest tests/unit/test_data_models.py::TestSongMetadata::test_create_with_all_fields -vv -s
```

### Use Python Debugger

Add breakpoint in test:
```python
def test_something():
    """Test something."""
    result = function()
    breakpoint()  # Python 3.7+
    assert result == expected
```

Run with debugger:
```bash
pytest --pdb
```

### Check Test Logs

Tests run with `LOG_LEVEL=ERROR` by default. To see more logs:

```python
def test_with_debug_logs(caplog):
    """Test with debug logging."""
    import logging
    caplog.set_level(logging.DEBUG)

    result = function()

    # Check logs
    assert "Expected log message" in caplog.text
```

## Performance Testing

### Measure Test Execution Time

```bash
pytest --durations=10  # Show 10 slowest tests
```

### Profile Tests

```bash
pip install pytest-profiling
pytest --profile
```

## Additional Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest-asyncio Guide](https://pytest-asyncio.readthedocs.io/)
- [Testing FastAPI Applications](https://fastapi.tiangolo.com/tutorial/testing/)
- [Temporal Testing Documentation](https://docs.temporal.io/develop/python/testing)

## Getting Help

If you have questions about testing:

1. Check this guide
2. Look at existing tests for examples
3. Read the pytest documentation
4. Ask in the project's GitHub Discussions
5. Open an issue with the `testing` label
