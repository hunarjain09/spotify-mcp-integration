#!/usr/bin/env python3
"""
Generate Raspberry Pi recommendations based on load test results
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass


@dataclass
class RaspberryPiModel:
    """Raspberry Pi model specifications"""
    name: str
    cpu_cores: int
    cpu_ghz: float
    ram_mb: int
    price_usd: int
    notes: str


# Current Raspberry Pi models (as of 2024)
RASPBERRY_PI_MODELS = [
    RaspberryPiModel(
        name="Raspberry Pi Zero 2 W",
        cpu_cores=4,
        cpu_ghz=1.0,
        ram_mb=512,
        price_usd=15,
        notes="Ultra-compact, WiFi built-in. Good for very light loads."
    ),
    RaspberryPiModel(
        name="Raspberry Pi 4 Model B (2GB)",
        cpu_cores=4,
        cpu_ghz=1.8,
        ram_mb=2048,
        price_usd=45,
        notes="Good balance of performance and cost."
    ),
    RaspberryPiModel(
        name="Raspberry Pi 4 Model B (4GB)",
        cpu_cores=4,
        cpu_ghz=1.8,
        ram_mb=4096,
        price_usd=55,
        notes="Recommended for moderate loads with room to grow."
    ),
    RaspberryPiModel(
        name="Raspberry Pi 4 Model B (8GB)",
        cpu_cores=4,
        cpu_ghz=1.8,
        ram_mb=8192,
        price_usd=75,
        notes="Best for heavy loads and future-proofing."
    ),
    RaspberryPiModel(
        name="Raspberry Pi 5 (4GB)",
        cpu_cores=4,
        cpu_ghz=2.4,
        ram_mb=4096,
        price_usd=60,
        notes="Latest model with significant performance improvements."
    ),
    RaspberryPiModel(
        name="Raspberry Pi 5 (8GB)",
        cpu_cores=4,
        cpu_ghz=2.4,
        ram_mb=8192,
        price_usd=80,
        notes="Latest model with maximum RAM. Best overall choice."
    ),
]


def find_latest_results() -> Dict[str, Path]:
    """Find the latest test result files"""
    results_dir = Path("load_test_results")

    if not results_dir.exists():
        print("Error: load_test_results directory not found")
        print("Please run load tests first using: ./run_load_tests.sh")
        sys.exit(1)

    results = {}

    # Find baseline measurement
    baseline_file = results_dir / "baseline_measurement.json"
    if baseline_file.exists():
        results['baseline'] = baseline_file

    # Find test result directories
    for test_type in ['light_load', 'medium_load', 'heavy_load']:
        # Find directories matching pattern
        matching_dirs = sorted(
            results_dir.glob(f"{test_type}_*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        if matching_dirs:
            # Get the most recent one
            test_dir = matching_dirs[0]

            # Look for JSON files with measurements
            json_files = list(test_dir.glob("*.json"))
            if json_files:
                results[test_type] = json_files[0]

    return results


def load_test_results(file_path: Path) -> Dict[str, Any]:
    """Load test results from JSON file"""
    with open(file_path, 'r') as f:
        return json.load(f)


def analyze_results(results: Dict[str, Path]) -> Dict[str, Any]:
    """Analyze load test results"""
    analysis = {}

    for test_type, file_path in results.items():
        data = load_test_results(file_path)

        if test_type == 'baseline':
            summary = data.get('summary', {})
            analysis[test_type] = {
                'cpu_percent': summary.get('avg_system_cpu', 0),
                'memory_mb': summary.get('avg_system_memory_mb', 0),
                'api_cpu_percent': summary.get('avg_api_cpu', 0),
                'api_memory_mb': summary.get('avg_api_memory_mb', 0),
            }
        else:
            stats = data.get('stats', {})
            analysis[test_type] = {
                'cpu_percent': stats.get('system_cpu', {}).get('max', 0),
                'memory_mb': stats.get('system_memory_mb', {}).get('max', 0),
                'api_cpu_percent': stats.get('api_process_cpu', {}).get('max', 0),
                'api_memory_mb': stats.get('api_process_memory_mb', {}).get('max', 0),
            }

    return analysis


def recommend_raspberry_pi(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate Raspberry Pi recommendations based on analysis"""

    # Determine requirements based on heaviest load tested
    max_memory_mb = 0
    max_cpu_percent = 0

    for test_type, metrics in analysis.items():
        if test_type == 'baseline':
            continue
        max_memory_mb = max(max_memory_mb, metrics.get('memory_mb', 0))
        max_cpu_percent = max(max_cpu_percent, metrics.get('cpu_percent', 0))

    # If no load tests, use baseline
    if max_memory_mb == 0:
        baseline = analysis.get('baseline', {})
        max_memory_mb = baseline.get('memory_mb', 256)
        max_cpu_percent = baseline.get('cpu_percent', 5)

    # Add safety margin (50% for memory, 30% for CPU)
    recommended_memory_mb = max_memory_mb * 1.5
    recommended_cpu_percent = max_cpu_percent * 1.3

    # Score each model
    recommendations = []

    for model in RASPBERRY_PI_MODELS:
        # Check if model meets requirements
        memory_ok = model.ram_mb >= recommended_memory_mb
        cpu_ok = True  # All modern RPis should handle the CPU load

        # Calculate fit score (0-100)
        memory_score = min(100, (model.ram_mb / recommended_memory_mb) * 100)

        # Price score (inverse - lower price is better)
        max_price = max(m.price_usd for m in RASPBERRY_PI_MODELS)
        price_score = 100 - ((model.price_usd / max_price) * 100)

        # Performance score (based on CPU speed and cores)
        max_ghz = max(m.cpu_ghz for m in RASPBERRY_PI_MODELS)
        performance_score = (model.cpu_ghz / max_ghz) * 100

        # Overall score (weighted average)
        overall_score = (
            memory_score * 0.5 +
            price_score * 0.2 +
            performance_score * 0.3
        )

        recommendation = {
            'model': model,
            'memory_ok': memory_ok,
            'cpu_ok': cpu_ok,
            'fits_requirements': memory_ok and cpu_ok,
            'memory_score': memory_score,
            'price_score': price_score,
            'performance_score': performance_score,
            'overall_score': overall_score,
            'headroom_mb': model.ram_mb - recommended_memory_mb,
        }

        recommendations.append(recommendation)

    # Sort by overall score (descending)
    recommendations.sort(key=lambda x: x['overall_score'], reverse=True)

    return recommendations


def print_report(analysis: Dict[str, Any], recommendations: List[Dict[str, Any]]):
    """Print the recommendation report"""

    print("\n" + "="*80)
    print("RASPBERRY PI RECOMMENDATION REPORT")
    print("Spotify MCP Integration Load Test Analysis")
    print("="*80)

    # Print test results summary
    print("\n📊 LOAD TEST RESULTS SUMMARY")
    print("-" * 80)

    for test_type in ['baseline', 'light_load', 'medium_load', 'heavy_load']:
        if test_type not in analysis:
            continue

        metrics = analysis[test_type]
        print(f"\n{test_type.replace('_', ' ').title()}:")
        print(f"  System CPU:    {metrics.get('cpu_percent', 0):.1f}%")
        print(f"  System Memory: {metrics.get('memory_mb', 0):.1f} MB")

        if metrics.get('api_cpu_percent', 0) > 0:
            print(f"  API CPU:       {metrics.get('api_cpu_percent', 0):.1f}%")
        if metrics.get('api_memory_mb', 0) > 0:
            print(f"  API Memory:    {metrics.get('api_memory_mb', 0):.1f} MB")

    # Calculate peak usage
    peak_memory = max(
        (metrics.get('memory_mb', 0) for metrics in analysis.values()),
        default=0
    )
    peak_cpu = max(
        (metrics.get('cpu_percent', 0) for metrics in analysis.values()),
        default=0
    )

    print(f"\n{'Peak Usage:'}")
    print(f"  CPU:    {peak_cpu:.1f}%")
    print(f"  Memory: {peak_memory:.1f} MB")

    # Recommended specs with safety margin
    recommended_memory = peak_memory * 1.5
    print(f"\n{'Recommended Minimum (with 50% safety margin):'}")
    print(f"  Memory: {recommended_memory:.1f} MB")

    # Print recommendations
    print("\n" + "="*80)
    print("🎯 RASPBERRY PI RECOMMENDATIONS")
    print("="*80)

    # Show top 3 recommendations
    print("\n✅ RECOMMENDED MODELS (Best Match):")
    print("-" * 80)

    for i, rec in enumerate(recommendations[:3], 1):
        model = rec['model']
        fits = "✓" if rec['fits_requirements'] else "✗"

        print(f"\n#{i} - {model.name} [{fits}]")
        print(f"  Price:        ${model.price_usd}")
        print(f"  RAM:          {model.ram_mb} MB")
        print(f"  CPU:          {model.cpu_cores} cores @ {model.cpu_ghz} GHz")
        print(f"  Headroom:     {rec['headroom_mb']:.0f} MB RAM available")
        print(f"  Overall Score: {rec['overall_score']:.1f}/100")
        print(f"  Notes:        {model.notes}")

    # Show models that don't fit
    unsuitable = [r for r in recommendations if not r['fits_requirements']]

    if unsuitable:
        print("\n❌ NOT RECOMMENDED (Insufficient Resources):")
        print("-" * 80)

        for rec in unsuitable:
            model = rec['model']
            print(f"\n{model.name}")
            print(f"  RAM:     {model.ram_mb} MB (need {recommended_memory:.0f} MB)")
            print(f"  Reason:  Insufficient memory")

    # Final recommendation
    print("\n" + "="*80)
    print("💡 FINAL RECOMMENDATION")
    print("="*80)

    best = recommendations[0]
    model = best['model']

    print(f"\nBased on your load testing results, we recommend:")
    print(f"\n  🎯 {model.name}")
    print(f"\n  This model provides:")
    print(f"    • {model.ram_mb} MB RAM ({best['headroom_mb']:.0f} MB headroom)")
    print(f"    • {model.cpu_cores} cores @ {model.cpu_ghz} GHz")
    print(f"    • ${model.price_usd} price point")
    print(f"\n  {model.notes}")

    # Additional notes
    print("\n" + "="*80)
    print("📝 ADDITIONAL NOTES")
    print("="*80)
    print("""
1. These recommendations are based on the load tests performed.
   Your actual usage may vary depending on:
   - Number of concurrent users
   - Frequency of song syncs
   - Claude AI API response times
   - Spotify API rate limits

2. Consider future growth:
   - If you expect usage to grow, choose a model with more headroom
   - The 8GB models provide significant headroom for future expansion

3. Operating System overhead:
   - The measurements include OS overhead
   - Raspberry Pi OS Lite is recommended for headless operation
   - Consider disabling unnecessary services to free up resources

4. Cooling:
   - Under sustained load, consider adding a heatsink or fan
   - Raspberry Pi 5 includes active cooling options

5. Storage:
   - Use a fast microSD card (Class 10/UHS-I minimum)
   - Consider USB SSD for better performance

6. Network:
   - Wired Ethernet is more reliable than WiFi for servers
   - Raspberry Pi 4/5 have Gigabit Ethernet

7. Power Supply:
   - Use the official Raspberry Pi power supply
   - Inadequate power can cause stability issues
""")

    print("="*80)
    print("\n")


def main():
    """Main entry point"""
    print("Analyzing load test results...")

    # Find latest results
    results = find_latest_results()

    if not results:
        print("\nNo load test results found!")
        print("Please run load tests first using: ./run_load_tests.sh")
        sys.exit(1)

    print(f"Found {len(results)} test result(s)")

    # Analyze results
    analysis = analyze_results(results)

    # Generate recommendations
    recommendations = recommend_raspberry_pi(analysis)

    # Print report
    print_report(analysis, recommendations)

    # Save report to file
    report_file = Path("load_test_results") / "raspberry_pi_recommendation.txt"

    # Redirect stdout to file
    import io
    from contextlib import redirect_stdout

    f = io.StringIO()
    with redirect_stdout(f):
        print_report(analysis, recommendations)

    with open(report_file, 'w') as file:
        file.write(f.getvalue())

    print(f"Report saved to: {report_file}")


if __name__ == '__main__':
    main()
