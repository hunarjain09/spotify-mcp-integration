# Quick Start: Load Testing for Raspberry Pi Sizing

This guide will help you quickly run load tests to determine which Raspberry Pi model you need.

## 🚀 Quick Start (5 minutes)

### Step 1: Install Dependencies

```bash
# From project root
cd /home/user/spotify-mcp-integration
uv sync --extra loadtest
```

### Step 2: Start the API Server

In a **separate terminal**:

```bash
cd /home/user/spotify-mcp-integration
./run.sh
```

Wait for the message: "Uvicorn running on http://0.0.0.0:8000"

### Step 3: Run Load Tests

In your **original terminal**:

```bash
cd load_tests
chmod +x run_load_tests.sh generate_raspberry_pi_report.py
./run_load_tests.sh
```

Select option **6** (All tests) or just press Enter.

### Step 4: Get Recommendations

After tests complete:

```bash
python3 generate_raspberry_pi_report.py
```

This will display a detailed report with Raspberry Pi recommendations!

## 📊 What Gets Tested

The test suite will:
1. **Baseline** - Measure idle resource usage (30 seconds)
2. **Light Load** - Simulate 5 concurrent users (60 seconds)
3. **Medium Load** - Simulate 20 concurrent users (120 seconds)
4. **Heavy Load** - Simulate 50 concurrent users (120 seconds)

Total time: ~6-7 minutes

## 📈 Understanding Results

After tests complete, you'll see:
- Peak CPU usage during tests
- Peak memory usage during tests
- Recommended Raspberry Pi models
- Cost vs performance trade-offs

### Example Output

```
🎯 RECOMMENDED MODELS (Best Match):

#1 - Raspberry Pi 5 (8GB) [✓]
  Price:        $80
  RAM:          8192 MB
  CPU:          4 cores @ 2.4 GHz
  Headroom:     6500 MB RAM available
  Overall Score: 85.2/100
  Notes:        Latest model with maximum RAM. Best overall choice.
```

## 🎯 Quick Recommendations (if you skip testing)

Based on typical usage:

- **Personal use (1-5 songs/day)**
  → Raspberry Pi 4 (2GB) - $45

- **Regular use (10-20 songs/day)**
  → Raspberry Pi 4 (4GB) - $55

- **Heavy use (50+ songs/day)**
  → Raspberry Pi 5 (8GB) - $80

## ⚠️ Important Notes

1. **API Server Must Be Running**
   - The tests will fail if the server isn't started
   - Check with: `curl http://localhost:8000/api/v1/health`

2. **Real API Keys Required**
   - Tests use actual Spotify/Claude APIs
   - Set up your `.env` file first
   - See main README for setup instructions

3. **Internet Connection**
   - Tests require stable internet
   - API calls go to Spotify/Claude servers

4. **Rate Limits**
   - Respect API rate limits
   - Heavy tests may hit limits
   - Wait a few minutes between test runs

## 🔧 Troubleshooting

### "API is not running"
```bash
# Start the API server first
cd ..
./run.sh
```

### "locust: command not found"
```bash
# Install dependencies
cd ..
uv sync --extra loadtest
```

### "Permission denied"
```bash
# Make scripts executable
chmod +x run_load_tests.sh generate_raspberry_pi_report.py
```

### High failure rate in results
- Check API credentials in `.env`
- Verify Spotify/Claude API keys are valid
- Check for rate limit errors in API logs

## 📁 Where Are Results?

All results are saved to `load_test_results/`:
- `baseline_measurement.json` - Idle state
- `light_load_*/` - Light load test results
- `medium_load_*/` - Medium load test results
- `heavy_load_*/` - Heavy load test results
- `raspberry_pi_recommendation.txt` - Final report

## 🎓 Advanced Usage

See the full [README.md](README.md) for:
- Custom test scenarios
- Manual Locust execution
- Result interpretation
- Configuration options

## 💡 Next Steps

After getting recommendations:

1. **Review the report** - Check memory and CPU headroom
2. **Consider future growth** - Will usage increase?
3. **Check your budget** - Balance cost vs performance
4. **Purchase hardware** - Order your Raspberry Pi!
5. **Deploy** - Follow deployment guide in main README

## 🆘 Need Help?

- Full documentation: [README.md](README.md)
- Main project README: [../README.md](../README.md)
- Open an issue on GitHub
