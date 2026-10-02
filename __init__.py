"""Hermes managed Git entry point; native implementation lives in the adapter."""

import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from adapters.hermes.plugin import register

__all__ = ["register"]
