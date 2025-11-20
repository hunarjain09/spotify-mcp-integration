"""
Light load test configuration
Uses longer wait times between requests to simulate light usage
"""

from locust import between
from locust_common import SpotifyMCPUser


class LightLoadUser(SpotifyMCPUser):
    """Light load: longer wait times between requests"""
    wait_time = between(5, 10)
