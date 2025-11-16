"""Temporal worker for music sync workflows and activities."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from temporalio.client import Client, TLSConfig
from temporalio.worker import Worker

from config.settings import settings
from workflows.music_sync_workflow import MusicSyncWorkflow
from activities.spotify_search import search_spotify
from activities.fuzzy_matcher import fuzzy_match_tracks
from activities.ai_disambiguator import ai_disambiguate_track
from activities.playlist_manager import add_track_to_playlist, verify_track_added


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_temporal_client() -> Client:
    """Create and connect to Temporal client.

    Returns:
        Connected Temporal client

    Raises:
        Exception: If connection fails
    """
    logger.info(f"Connecting to Temporal at {settings.temporal_host}")

    # Prepare connection parameters
    connect_params = {
        "target_host": settings.temporal_host,
        "namespace": settings.temporal_namespace,
    }

    # Add TLS config for Temporal Cloud
    if settings.is_temporal_cloud:
        tls_config = settings.temporal_tls_config
        if tls_config:
            logger.info("Using TLS configuration for Temporal Cloud")
            connect_params["tls"] = TLSConfig(
                client_cert=tls_config["client_cert"],
                client_private_key=tls_config["client_private_key"],
            )

    # Connect
    client = await Client.connect(**connect_params)
    logger.info("✓ Connected to Temporal")

    return client


async def run_worker():
    """Run the Temporal worker.

    This worker:
    - Registers workflows and activities
    - Polls task queues for work
    - Executes workflow and activity code
    """
    # Create Temporal client
    client = await create_temporal_client()

    # Create thread pool for activities
    activity_executor = ThreadPoolExecutor(max_workers=settings.max_concurrent_activities)

    # Configure and start worker
    worker = Worker(
        client,
        task_queue=settings.task_queue_name,
        workflows=[MusicSyncWorkflow],
        activities=[
            search_spotify,
            fuzzy_match_tracks,
            ai_disambiguate_track,
            add_track_to_playlist,
            verify_track_added,
        ],
        activity_executor=activity_executor,
        max_concurrent_workflow_tasks=settings.max_concurrent_workflows,
        max_concurrent_activities=settings.max_concurrent_activities,
        max_activities_per_second=settings.max_activities_per_second,
    )

    logger.info(
        f"Starting worker on task queue '{settings.task_queue_name}' with:\n"
        f"  - Max concurrent workflows: {settings.max_concurrent_workflows}\n"
        f"  - Max concurrent activities: {settings.max_concurrent_activities}\n"
        f"  - Max activities per second: {settings.max_activities_per_second}"
    )

    # Run worker
    try:
        await worker.run()
    except KeyboardInterrupt:
        logger.info("Worker shutdown requested")
    except Exception as e:
        logger.error(f"Worker error: {e}", exc_info=True)
        raise
    finally:
        activity_executor.shutdown(wait=True)
        logger.info("Worker stopped")


def main():
    """Main entry point for the worker."""
    logger.info("=" * 60)
    logger.info("Apple Music to Spotify Sync - Temporal Worker")
    logger.info("=" * 60)

    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
