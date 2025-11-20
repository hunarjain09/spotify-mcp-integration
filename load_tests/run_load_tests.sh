#!/bin/bash

# Load Testing Script for Spotify MCP Integration
# This script runs various load test scenarios and generates reports

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
API_HOST="${API_HOST:-http://localhost:8000}"
RESULTS_DIR="load_test_results"

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}Spotify MCP Load Testing Suite${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo "API Host: $API_HOST"
echo "Results Directory: $RESULTS_DIR"
echo ""

# Create results directory
mkdir -p "$RESULTS_DIR"

# Function to check if API is running
check_api() {
    echo -e "${YELLOW}Checking if API is running...${NC}"
    if curl -s "$API_HOST/api/v1/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ API is running${NC}"
        return 0
    else
        echo -e "${RED}✗ API is not running at $API_HOST${NC}"
        echo "Please start the API server first with: ./run.sh"
        exit 1
    fi
}

# Function to run a load test
run_test() {
    local test_name=$1
    local users=$2
    local spawn_rate=$3
    local duration=$4
    local user_class=${5:-SpotifyMCPUser}

    echo ""
    echo -e "${GREEN}======================================${NC}"
    echo -e "${GREEN}Running: $test_name${NC}"
    echo -e "${GREEN}======================================${NC}"
    echo "Users: $users"
    echo "Spawn Rate: $spawn_rate per second"
    echo "Duration: $duration seconds"
    echo "User Class: $user_class"
    echo ""

    local output_dir="$RESULTS_DIR/${test_name}_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$output_dir"

    # Run locust in headless mode
    locust \
        -f locustfile.py \
        --headless \
        --users "$users" \
        --spawn-rate "$spawn_rate" \
        --run-time "${duration}s" \
        --host "$API_HOST" \
        --html "$output_dir/report.html" \
        --csv "$output_dir/stats" \
        --user "$user_class" \
        2>&1 | tee "$output_dir/console.log"

    echo ""
    echo -e "${GREEN}✓ Test completed. Results saved to: $output_dir${NC}"
    echo ""
}

# Function to measure baseline (idle) resource usage
measure_baseline() {
    echo ""
    echo -e "${GREEN}======================================${NC}"
    echo -e "${GREEN}Measuring Baseline (Idle State)${NC}"
    echo -e "${GREEN}======================================${NC}"
    echo ""

    python3 - <<'EOF'
import psutil
import time
import json

print("Measuring baseline resource usage for 30 seconds...")
measurements = []

for i in range(30):
    # Get system stats
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()

    # Get API process stats
    api_processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline') or []
            cmdline_str = ' '.join(cmdline)
            if 'uvicorn' in cmdline_str or 'app_agent' in cmdline_str:
                api_processes.append({
                    'pid': proc.info['pid'],
                    'cpu_percent': proc.cpu_percent(),
                    'memory_mb': proc.memory_info().rss / 1024 / 1024,
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    measurements.append({
        'timestamp': time.time(),
        'system_cpu_percent': cpu_percent,
        'system_memory_mb': memory.used / 1024 / 1024,
        'system_memory_percent': memory.percent,
        'api_processes': api_processes
    })

    if (i + 1) % 10 == 0:
        print(f"  {i + 1}/30 seconds...")

# Calculate averages
avg_cpu = sum(m['system_cpu_percent'] for m in measurements) / len(measurements)
avg_memory = sum(m['system_memory_mb'] for m in measurements) / len(measurements)
avg_memory_pct = sum(m['system_memory_percent'] for m in measurements) / len(measurements)

api_cpu_values = []
api_memory_values = []
for m in measurements:
    for proc in m['api_processes']:
        api_cpu_values.append(proc['cpu_percent'])
        api_memory_values.append(proc['memory_mb'])

print("\nBaseline Results:")
print(f"  System CPU: {avg_cpu:.1f}%")
print(f"  System Memory: {avg_memory:.1f} MB ({avg_memory_pct:.1f}%)")

if api_cpu_values:
    print(f"  API Process CPU: {sum(api_cpu_values)/len(api_cpu_values):.1f}%")
if api_memory_values:
    print(f"  API Process Memory: {sum(api_memory_values)/len(api_memory_values):.1f} MB")

# Save to file
with open('load_test_results/baseline_measurement.json', 'w') as f:
    json.dump({
        'measurements': measurements,
        'summary': {
            'avg_system_cpu': avg_cpu,
            'avg_system_memory_mb': avg_memory,
            'avg_system_memory_percent': avg_memory_pct,
            'avg_api_cpu': sum(api_cpu_values)/len(api_cpu_values) if api_cpu_values else 0,
            'avg_api_memory_mb': sum(api_memory_values)/len(api_memory_values) if api_memory_values else 0,
        }
    }, f, indent=2)

print("\nBaseline measurement saved to: load_test_results/baseline_measurement.json")
EOF

    echo ""
    echo -e "${GREEN}✓ Baseline measurement completed${NC}"
    echo ""
}

# Main execution
main() {
    # Check if API is running
    check_api

    # Ask user what tests to run
    echo "Available test scenarios:"
    echo "  1) Baseline measurement only (idle state)"
    echo "  2) Light load test (5 users)"
    echo "  3) Medium load test (20 users)"
    echo "  4) Heavy load test (50 users)"
    echo "  5) Progressive load test (5 -> 20 -> 50 users)"
    echo "  6) All tests"
    echo ""
    read -p "Select test scenario (1-6) [default: 6]: " scenario
    scenario=${scenario:-6}

    case $scenario in
        1)
            measure_baseline
            ;;
        2)
            measure_baseline
            run_test "light_load" 5 1 60 "LightLoadUser"
            ;;
        3)
            measure_baseline
            run_test "medium_load" 20 2 120 "MediumLoadUser"
            ;;
        4)
            measure_baseline
            run_test "heavy_load" 50 5 120 "HeavyLoadUser"
            ;;
        5)
            measure_baseline
            run_test "light_load" 5 1 60 "LightLoadUser"
            sleep 10
            run_test "medium_load" 20 2 120 "MediumLoadUser"
            sleep 10
            run_test "heavy_load" 50 5 120 "HeavyLoadUser"
            ;;
        6)
            measure_baseline
            run_test "light_load" 5 1 60 "LightLoadUser"
            sleep 10
            run_test "medium_load" 20 2 120 "MediumLoadUser"
            sleep 10
            run_test "heavy_load" 50 5 120 "HeavyLoadUser"
            ;;
        *)
            echo "Invalid option"
            exit 1
            ;;
    esac

    echo ""
    echo -e "${GREEN}======================================${NC}"
    echo -e "${GREEN}All Tests Completed!${NC}"
    echo -e "${GREEN}======================================${NC}"
    echo ""
    echo "Results are available in: $RESULTS_DIR/"
    echo ""
    echo "To view HTML reports:"
    echo "  Open $RESULTS_DIR/*/report.html in a browser"
    echo ""
    echo "Next steps:"
    echo "  1. Review the HTML reports for request statistics"
    echo "  2. Check console.log files for resource usage"
    echo "  3. Analyze JSON files for detailed measurements"
    echo "  4. Run generate_raspberry_pi_report.py for recommendations"
    echo ""
}

# Change to the load_tests directory
cd "$(dirname "$0")"

# Run main
main
