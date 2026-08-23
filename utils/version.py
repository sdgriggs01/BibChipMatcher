#!/usr/bin/env python3
"""Single source of truth for the application version.

Kept in sync with the ``version`` field in pyproject.toml (verified by
tests/test_version.py) so the GUI's About dialog and the frozen build can
report a version without parsing pyproject.toml at runtime.
"""

from __future__ import annotations

__version__ = '1.0.0'
