# Wyoming Polyglot Proxy Tests

Comprehensive test suite for the Wyoming Polyglot Proxy add-on.

## Running Tests

### Install Dependencies

```bash
cd /gfontana/Dev/projects/personal/ai-ml/smart-talk/wyoming-proxy-addon
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Run All Tests

```bash
pytest
```

### Run Specific Test Categories

```bash
# Only unit tests (fast, no I/O)
pytest -m unit

# Only integration tests (mocked I/O)
pytest -m integration

# Only E2E tests (full flow with mock servers)
pytest -m e2e
```

### Run Specific Test Files

```bash
# Language detection tests
pytest tests/unit/test_language_detection.py -v

# Voice selection tests
pytest tests/unit/test_voice_selection.py -v

# TTS proxy integration tests
pytest tests/integration/test_tts_proxy.py -v

# Full TTS flow E2E tests
pytest tests/e2e/test_full_tts_flow.py -v
```

### Run with Coverage

```bash
# Generate coverage report
pytest --cov=src --cov-report=html --cov-report=term-missing

# View HTML report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Run Tests in Verbose Mode

```bash
pytest -v
```

### Run Tests with Output

```bash
# Show print statements
pytest -s

# Show all output
pytest -vv -s
```

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── unit/                    # Unit tests (15-20 tests)
│   ├── test_language_detection.py
│   ├── test_voice_selection.py
│   └── test_config.py
├── integration/             # Integration tests (5-8 tests)
│   ├── test_stt_proxy.py
│   └── test_tts_proxy.py
└── e2e/                     # E2E tests (2-3 tests)
    └── test_full_tts_flow.py
```

## Test Categories

### Unit Tests (`-m unit`)
- Fast (milliseconds)
- No network I/O
- Test individual functions
- Language detection logic
- Voice selection logic
- Configuration loading

### Integration Tests (`-m integration`)
- Moderate speed (< 1 second each)
- Mocked network I/O
- Test component interactions
- Proxy forwarding behavior
- Event modification logic

### E2E Tests (`-m e2e`)
- Slower (1-5 seconds each)
- Mock Wyoming servers
- Full pipeline tests
- Real network communication (localhost)
- End-to-end flow verification

## Coverage Goals

- **Overall**: ≥80%
- **src/tts_proxy.py**: ≥90% (core logic)
- **src/stt_proxy.py**: ≥80% (forwarding)
- **src/config.py**: ≥90% (simple config)

## Fixtures

Key fixtures available in all tests (defined in `conftest.py`):

- `voice_mapping`: Standard language→voice mapping
- `mock_config`: Mock configuration file
- `unused_tcp_port`: Get available TCP port
- `mock_wyoming_server`: Mock Wyoming server
- `mock_stream_reader`: Mock StreamReader
- `mock_stream_writer`: Mock StreamWriter

## Debugging Tests

### Run Single Test

```bash
pytest tests/unit/test_language_detection.py::test_detect_spanish -v
```

### Drop into Debugger on Failure

```bash
pytest --pdb
```

### Show Warnings

```bash
pytest -v --tb=short -W default
```

## Continuous Integration

Tests are designed to run in CI environments:

```yaml
# Example: GitHub Actions
- name: Run tests
  run: |
    pip install -r requirements.txt
    pip install -r requirements-dev.txt
    pytest --cov=src --cov-report=xml

- name: Upload coverage
  uses: codecov/codecov-action@v3
```

## Writing New Tests

### Unit Test Template

```python
import pytest
from src.module import MyClass

@pytest.mark.unit
def test_my_function(voice_mapping):
    \"\"\"Test description.\"\"\"
    obj = MyClass(voice_mapping)
    result = obj.my_function("input")
    assert result == "expected"
```

### Integration Test Template

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.integration
@pytest.mark.asyncio
async def test_my_async_function(mock_stream_reader, mock_stream_writer):
    \"\"\"Test description.\"\"\"
    # Setup mocks
    # Call function
    # Assert behavior
```

### E2E Test Template

```python
import pytest
import asyncio

@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_full_flow(voice_mapping, unused_tcp_port):
    \"\"\"Test description.\"\"\"
    # Create mock server
    # Start proxy
    # Send requests
    # Verify responses
    # Cleanup
```

## Troubleshooting

### Tests Hang

- E2E tests may timeout if servers don't start
- Check for unclosed connections
- Ensure `@pytest.mark.timeout(5)` is set on E2E tests

### Import Errors

```bash
# Ensure src/ is in Python path
export PYTHONPATH=/gfontana/Dev/projects/personal/ai-ml/smart-talk/wyoming-proxy-addon:$PYTHONPATH
pytest
```

### Async Test Failures

- Ensure `@pytest.mark.asyncio` decorator is present
- Check `pytest.ini` has `asyncio_mode = auto`
- Verify pytest-asyncio is installed

### Coverage Not Generated

```bash
# Ensure pytest-cov is installed
pip install pytest-cov

# Run with coverage explicitly
pytest --cov=src
```

## Performance Benchmarking

```bash
# Show slowest 10 tests
pytest --durations=10

# Profile tests
pytest --profile
```

## Best Practices

1. **Keep unit tests fast** - No I/O, no network, no async (when possible)
2. **Use fixtures** - Reuse common setup via conftest.py
3. **Test one thing** - Each test should verify one behavior
4. **Clear test names** - `test_what_when_expected`
5. **Cleanup resources** - Close connections, cancel tasks
6. **Use markers** - Tag tests appropriately (unit/integration/e2e)
7. **Mock external dependencies** - Don't rely on real Whisper/Piper
8. **Verify, don't just exercise** - Assert expected outcomes

## Getting Help

- Check pytest documentation: https://docs.pytest.org/
- Wyoming protocol docs: https://github.com/rhasspy/wyoming
- pytest-asyncio docs: https://pytest-asyncio.readthedocs.io/
