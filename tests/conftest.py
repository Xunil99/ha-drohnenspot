"""Test-Setup.

Macht die reinen Logik-Module (`spotfinder`, `dipul`) ohne Home-Assistant
importierbar, indem das Integrationsverzeichnis direkt auf den Pfad gelegt
wird. So laufen die Kern-Tests mit reinem `pytest` (ohne HA/aiohttp).
"""
from __future__ import annotations

import sys
from pathlib import Path

_INTEGRATION = Path(__file__).parent.parent / "custom_components" / "drohnenspot"
sys.path.insert(0, str(_INTEGRATION))
