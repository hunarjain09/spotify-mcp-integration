"""
Load testing for Spotify MCP Integration API
Uses Locust for load generation and tracks resource usage
"""

import json
import random
import time
from typing import Any, Dict, List

from locust import HttpUser, task, between, events
import psutil

# Sample song data for testing
SAMPLE_SONGS = [
    {
        "title": "Blinding Lights",
        "artist": "The Weeknd",
        "album": "After Hours",
        "duration": 200,
        "isrc": "USUG12000123"
    },
    {
        "title": "Shape of You",
        "artist": "Ed Sheeran",
        "album": "÷ (Divide)",
        "duration": 233,
        "isrc": "GBAHS1700133"
    },
    {
        "title": "Someone Like You",
        "artist": "Adele",
        "album": "21",
        "duration": 285,
        "isrc": "GBBKS1000172"
    },
    {
        "title": "Uptown Funk",
        "artist": "Mark Ronson ft. Bruno Mars",
        "album": "Uptown Special",
        "duration": 269,
        "isrc": "GBARL1400208"
    },
    {
        "title": "Bohemian Rhapsody",
        "artist": "Queen",
        "album": "A Night at the Opera",
        "duration": 354,
        "isrc": "GBUM71029604"
    },
    {
        "title": "Hotel California",
        "artist": "Eagles",
        "album": "Hotel California",
        "duration": 391,
        "isrc": "USEE10001713"
    },
    {
        "title": "Billie Jean",
        "artist": "Michael Jackson",
        "album": "Thriller",
        "duration": 294,
        "isrc": "USEE10800015"
    },
    {
        "title": "Sweet Child O' Mine",
        "artist": "Guns N' Roses",
        "album": "Appetite for Destruction",
        "duration": 356,
        "isrc": "USGF18764851"
    },
    {
        "title": "Rolling in the Deep",
        "artist": "Adele",
        "album": "21",
        "duration": 228,
        "isrc": "GBBKS1000188"
    },
    {
        "title": "Stairway to Heaven",
        "artist": "Led Zeppelin",
        "album": "Led Zeppelin IV",
        "duration": 482,
        "isrc": "USRC17100010"
    },
    {
        "title": "Smells Like Teen Spirit",
        "artist": "Nirvana",
        "album": "Nevermind",
        "duration": 301,
        "isrc": "USGF19463401"
    },
    {
        "title": "Wonderwall",
        "artist": "Oasis",
        "album": "(What's the Story) Morning Glory?",
        "duration": 258,
        "isrc": "GBAYE9500429"
    },
]


class ResourceMonitor:
    """Monitor CPU and memory usage during load tests"""

    def __init__(self):
        self.process = psutil.Process()
        self.measurements: List[Dict[str, Any]] = []
        self.monitoring = False

    def start_monitoring(self):
        """Start resource monitoring"""
        self.monitoring = True
        self.measurements = []

    def record_measurement(self):
        """Record current resource usage"""
        if not self.monitoring:
            return

        try:
            # Get system-wide stats
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()

            # Try to get process-specific stats (for the API server)
            # This will capture the main process, but note that FastAPI might spawn workers
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
                            'threads': proc.num_threads()
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            measurement = {
                'timestamp': time.time(),
                'system_cpu_percent': cpu_percent,
                'system_memory_used_mb': memory.used / 1024 / 1024,
                'system_memory_percent': memory.percent,
                'system_memory_available_mb': memory.available / 1024 / 1024,
                'api_processes': api_processes
            }

            self.measurements.append(measurement)

        except Exception as e:
            print(f"Error recording measurement: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Calculate statistics from measurements"""
        if not self.measurements:
            return {}

        # Extract metrics
        cpu_values = [m['system_cpu_percent'] for m in self.measurements]
        memory_values = [m['system_memory_used_mb'] for m in self.measurements]
        memory_percent_values = [m['system_memory_percent'] for m in self.measurements]

        # Calculate API process stats
        api_cpu_values = []
        api_memory_values = []
        api_thread_values = []

        for m in self.measurements:
            for proc in m.get('api_processes', []):
                api_cpu_values.append(proc['cpu_percent'])
                api_memory_values.append(proc['memory_mb'])
                api_thread_values.append(proc['threads'])

        stats = {
            'measurement_count': len(self.measurements),
            'duration_seconds': self.measurements[-1]['timestamp'] - self.measurements[0]['timestamp'],
            'system_cpu': {
                'min': min(cpu_values),
                'max': max(cpu_values),
                'avg': sum(cpu_values) / len(cpu_values),
            },
            'system_memory_mb': {
                'min': min(memory_values),
                'max': max(memory_values),
                'avg': sum(memory_values) / len(memory_values),
            },
            'system_memory_percent': {
                'min': min(memory_percent_values),
                'max': max(memory_percent_values),
                'avg': sum(memory_percent_values) / len(memory_percent_values),
            }
        }

        if api_cpu_values:
            stats['api_process_cpu'] = {
                'min': min(api_cpu_values),
                'max': max(api_cpu_values),
                'avg': sum(api_cpu_values) / len(api_cpu_values),
            }

        if api_memory_values:
            stats['api_process_memory_mb'] = {
                'min': min(api_memory_values),
                'max': max(api_memory_values),
                'avg': sum(api_memory_values) / len(api_memory_values),
            }

        if api_thread_values:
            stats['api_process_threads'] = {
                'min': min(api_thread_values),
                'max': max(api_thread_values),
                'avg': sum(api_thread_values) / len(api_thread_values),
            }

        return stats


# Global resource monitor
resource_monitor = ResourceMonitor()


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts"""
    print("Starting resource monitoring...")
    resource_monitor.start_monitoring()


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops"""
    print("\n" + "="*80)
    print("RESOURCE USAGE STATISTICS")
    print("="*80)

    stats = resource_monitor.get_stats()

    if stats:
        print(f"\nMonitoring Duration: {stats['duration_seconds']:.1f} seconds")
        print(f"Measurements Taken: {stats['measurement_count']}")

        print(f"\nSystem CPU Usage:")
        print(f"  Min: {stats['system_cpu']['min']:.1f}%")
        print(f"  Max: {stats['system_cpu']['max']:.1f}%")
        print(f"  Avg: {stats['system_cpu']['avg']:.1f}%")

        print(f"\nSystem Memory Usage:")
        print(f"  Min: {stats['system_memory_mb']['min']:.1f} MB ({stats['system_memory_percent']['min']:.1f}%)")
        print(f"  Max: {stats['system_memory_mb']['max']:.1f} MB ({stats['system_memory_percent']['max']:.1f}%)")
        print(f"  Avg: {stats['system_memory_mb']['avg']:.1f} MB ({stats['system_memory_percent']['avg']:.1f}%)")

        if 'api_process_cpu' in stats:
            print(f"\nAPI Process CPU Usage:")
            print(f"  Min: {stats['api_process_cpu']['min']:.1f}%")
            print(f"  Max: {stats['api_process_cpu']['max']:.1f}%")
            print(f"  Avg: {stats['api_process_cpu']['avg']:.1f}%")

        if 'api_process_memory_mb' in stats:
            print(f"\nAPI Process Memory Usage:")
            print(f"  Min: {stats['api_process_memory_mb']['min']:.1f} MB")
            print(f"  Max: {stats['api_process_memory_mb']['max']:.1f} MB")
            print(f"  Avg: {stats['api_process_memory_mb']['avg']:.1f} MB")

        if 'api_process_threads' in stats:
            print(f"\nAPI Process Threads:")
            print(f"  Min: {stats['api_process_threads']['min']:.0f}")
            print(f"  Max: {stats['api_process_threads']['max']:.0f}")
            print(f"  Avg: {stats['api_process_threads']['avg']:.1f}")

        # Save detailed stats to file
        output_file = f"load_test_results_{int(time.time())}.json"
        with open(output_file, 'w') as f:
            json.dump({
                'stats': stats,
                'measurements': resource_monitor.measurements
            }, f, indent=2)
        print(f"\nDetailed results saved to: {output_file}")

    print("="*80 + "\n")


class SpotifyMCPUser(HttpUser):
    """Simulates a user syncing songs from Apple Music to Spotify"""

    # Wait between 1-5 seconds between tasks (simulates real user behavior)
    wait_time = between(1, 5)

    def on_start(self):
        """Called when a simulated user starts"""
        # Check if the API is healthy
        response = self.client.get("/api/v1/health")
        if response.status_code != 200:
            print(f"WARNING: API health check failed: {response.status_code}")

    @task(10)
    def sync_song(self):
        """Sync a random song to Spotify (most common task)"""
        # Record resource usage
        resource_monitor.record_measurement()

        # Pick a random song
        song = random.choice(SAMPLE_SONGS)

        # Make sync request
        with self.client.post(
            "/api/v1/sync",
            json=song,
            catch_response=True
        ) as response:
            if response.status_code == 202:
                # Success - extract workflow ID
                data = response.json()
                workflow_id = data.get('workflow_id')
                response.success()

                # Optionally check status after a delay
                # (Commenting out to avoid overloading the status endpoint)
                # time.sleep(2)
                # self.check_status(workflow_id)
            else:
                response.failure(f"Failed to sync song: {response.status_code}")

    @task(3)
    def check_random_status(self):
        """Check status of a workflow (less common)"""
        # Record resource usage
        resource_monitor.record_measurement()

        # Generate a random workflow ID (most will return 404, which is expected)
        workflow_id = f"test-{random.randint(1000, 9999)}"

        with self.client.get(
            f"/api/v1/sync/{workflow_id}",
            catch_response=True
        ) as response:
            if response.status_code in [200, 404]:
                # Both are acceptable
                response.success()
            else:
                response.failure(f"Unexpected status code: {response.status_code}")

    @task(1)
    def health_check(self):
        """Perform health check (least common)"""
        # Record resource usage
        resource_monitor.record_measurement()

        with self.client.get("/api/v1/health", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")


class LightLoadUser(SpotifyMCPUser):
    """Light load: longer wait times between requests"""
    wait_time = between(5, 10)


class MediumLoadUser(SpotifyMCPUser):
    """Medium load: moderate wait times"""
    wait_time = between(2, 5)


class HeavyLoadUser(SpotifyMCPUser):
    """Heavy load: minimal wait times"""
    wait_time = between(0.5, 2)
