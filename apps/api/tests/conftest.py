"""Shared test configuration for the single-package API suite.

Runs execute in background tasks; with no fixture pacing the runtime settles each run before
the HTTP response (``WorkspaceRuntime._settle_if_synchronous``) so tests stay deterministic.
"""
import os

os.environ.setdefault("FIXTURE_STEP_DELAY_MS", "0")
