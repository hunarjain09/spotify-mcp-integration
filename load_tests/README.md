# Load Testing for Spotify MCP Integration

This directory contains load testing tools to measure CPU and memory requirements for running the Spotify MCP Integration on a Raspberry Pi.

## Overview

The load testing suite includes:
- **Locust-based load generation** - Simulates concurrent users syncing songs
- **Resource monitoring** - Tracks CPU and memory usage during tests
- **Automated test scenarios** - Light, medium, and heavy load tests
- **Raspberry Pi recommendations** - Analysis and model recommendations

## Prerequisites

1. Install load testing dependencies:
   ```bash
   cd ..  # Go to project root
   uv sync --extra loadtest
   ```

2. Ensure the API server is running:
   ```bash
   ./run.sh
   ```

## Running Load Tests

### Quick Start (All Tests)

```bash
cd load_tests
chmod +x run_load_tests.sh
./run_load_tests.sh
```

This will:
1. Measure baseline (idle) resource usage
2. Run light load test (5 concurrent users)
3. Run medium load test (20 concurrent users)
4. Run heavy load test (50 concurrent users)
5. Generate HTML reports and resource measurements

### Individual Test Scenarios

Run specific tests by selecting from the menu:

```bash
./run_load_tests.sh
# Select option 1-6 when prompted
```

Options:
- **1** - Baseline measurement only
- **2** - Light load (5 users)
- **3** - Medium load (20 users)
- **4** - Heavy load (50 users)
- **5** - Progressive load (all three)
- **6** - All tests (default)

### Custom Load Tests

Run Locust directly for custom scenarios:

```bash
# Custom user count and duration
locust -f locustfile.py \
    --headless \
    --users 10 \
    --spawn-rate 2 \
    --run-time 60s \
    --host http://localhost:8000

# Interactive web UI
locust -f locustfile.py --host http://localhost:8000
# Then open http://localhost:8089
```

## Analyzing Results

### Generate Raspberry Pi Recommendations

After running load tests:

```bash
python3 generate_raspberry_pi_report.py
```

This will:
- Analyze all load test results
- Calculate peak CPU and memory usage
- Compare against Raspberry Pi models
- Provide specific model recommendations
- Save report to `load_test_results/raspberry_pi_recommendation.txt`

### View HTML Reports

Open the HTML reports in a browser:

```bash
# Example for light load test
xdg-open load_test_results/light_load_*/report.html
```

The HTML reports show:
- Request statistics (throughput, latency)
- Success/failure rates
- Response time percentiles
- Request timeline charts

### Review JSON Data

Detailed measurements are saved as JSON:

```bash
# View baseline measurement
cat load_test_results/baseline_measurement.json | jq

# View test results
cat load_test_results/light_load_*/load_test_results_*.json | jq
```

## Test Results Structure

```
load_test_results/
├── baseline_measurement.json          # Idle state measurements
├── light_load_YYYYMMDD_HHMMSS/       # Light load test
│   ├── report.html                    # Locust HTML report
│   ├── stats.csv                      # CSV statistics
│   ├── console.log                    # Console output
│   └── load_test_results_*.json      # Resource measurements
├── medium_load_YYYYMMDD_HHMMSS/      # Medium load test
│   └── ...
├── heavy_load_YYYYMMDD_HHMMSS/       # Heavy load test
│   └── ...
└── raspberry_pi_recommendation.txt    # Final recommendations
```

## Understanding the Tests

### User Classes

The load tests simulate three types of users:

1. **LightLoadUser** - Wait 5-10s between requests
   - Simulates occasional usage
   - Good for baseline performance

2. **MediumLoadUser** - Wait 2-5s between requests
   - Simulates regular usage
   - Typical home user scenario

3. **HeavyLoadUser** - Wait 0.5-2s between requests
   - Simulates intensive usage
   - Stress test scenario

### User Tasks

Each simulated user performs:
- **Sync song** (70% of requests) - POST /api/v1/sync
- **Check status** (20% of requests) - GET /api/v1/sync/{id}
- **Health check** (10% of requests) - GET /api/v1/health

### Resource Monitoring

During tests, the system monitors:
- **System-wide CPU usage** - Overall CPU utilization
- **System-wide memory usage** - Total RAM consumption
- **API process CPU** - CPU used by the API server
- **API process memory** - RAM used by the API server
- **Thread count** - Number of active threads

## Interpreting Results

### CPU Usage

- **< 25%** - Excellent, plenty of headroom
- **25-50%** - Good, normal operation
- **50-75%** - Moderate, consider headroom
- **> 75%** - High, may need more powerful hardware

### Memory Usage

Look at peak memory usage and add 50% safety margin:
- **Peak = 400 MB** → Recommend 600+ MB available
- **Peak = 800 MB** → Recommend 1200+ MB (2GB model)
- **Peak = 1500 MB** → Recommend 2250+ MB (4GB model)

### Response Times

From Locust HTML reports:
- **Median < 2s** - Excellent responsiveness
- **Median 2-5s** - Good for background sync
- **Median > 5s** - May feel slow to users
- **P95 < 10s** - Acceptable for most use cases

## Tips for Accurate Testing

1. **Run multiple times** - Results can vary, run 2-3 times
2. **Close other applications** - Isolate the API server
3. **Use production settings** - Test with real API keys
4. **Monitor network** - Ensure stable internet connection
5. **Check API rate limits** - Spotify/Claude have rate limits

## Troubleshooting

### API Not Running

```bash
Error: API is not running at http://localhost:8000
```

**Solution**: Start the API server first:
```bash
cd ..
./run.sh
```

### High Failure Rate

If many requests fail (see HTML report):
- Check API logs for errors
- Verify Spotify/Claude API credentials
- Check rate limit headers
- Reduce user count or spawn rate

### Out of Memory

If system runs out of memory during tests:
- Reduce number of concurrent users
- Shorten test duration
- Close other applications
- This indicates you need more RAM!

### Locust Not Found

```bash
locust: command not found
```

**Solution**: Install dependencies:
```bash
cd ..
uv sync --extra loadtest
```

## Configuration

### Environment Variables

```bash
# Change API host (default: http://localhost:8000)
export API_HOST=http://192.168.1.100:8000
./run_load_tests.sh
```

### Modify Test Duration

Edit `run_load_tests.sh`:
```bash
# Change duration from 60s to 300s
run_test "light_load" 5 1 300 "LightLoadUser"
```

### Add Custom Songs

Edit `locustfile.py` and add to `SAMPLE_SONGS`:
```python
SAMPLE_SONGS.append({
    "title": "Your Song",
    "artist": "Artist Name",
    "album": "Album Name",
    "duration": 180,
    "isrc": "USABC1234567"
})
```

## Next Steps

After load testing:

1. **Review recommendations** - Check Raspberry Pi model suggestions
2. **Consider usage patterns** - Will usage grow over time?
3. **Factor in cost** - Balance performance vs budget
4. **Plan for headroom** - Leave room for OS and other services
5. **Test on actual hardware** - If possible, test on target Raspberry Pi

## Support

For issues or questions:
- Check the main project README
- Review Locust documentation: https://docs.locust.io
- Open an issue on GitHub
