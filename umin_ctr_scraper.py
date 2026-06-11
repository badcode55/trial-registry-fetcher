#!/usr/bin/env python3

"""Backward-compatible entrypoint for the UMIN-CTR scraper.

New code should prefer:
    python -m trial_registry.cli "<query>"
"""

from __future__ import annotations

from trial_registry.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
