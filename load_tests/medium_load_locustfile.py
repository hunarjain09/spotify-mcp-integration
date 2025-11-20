"""
Medium load test configuration
Uses moderate wait times between requests to simulate medium usage
"""

from locust import between
from locust_common import SpotifyMCPUser


class MediumLoadUser(SpotifyMCPUser):
    """Medium load: moderate wait times"""
    wait_time = between(2, 5)
