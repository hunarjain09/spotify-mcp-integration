"""
Heavy load test configuration
Uses minimal wait times between requests to simulate heavy usage
"""

from locust import between
from locust_common import SpotifyMCPUser


class HeavyLoadUser(SpotifyMCPUser):
    """Heavy load: minimal wait times"""
    wait_time = between(0.5, 2)
