"""
Executors module for standalone (non-Temporal) workflow execution.

This module provides an alternative execution path for workflows that don't
require Temporal's infrastructure. See standalone_executor.py for details.
"""

from executors.standalone_executor import (
    run_standalone_workflow,
    get_workflow_progress,
    get_workflow_state,
)

__all__ = [
    "run_standalone_workflow",
    "get_workflow_progress",
    "get_workflow_state",
]
