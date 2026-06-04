"""Pytest configuration: make the package importable without installation.

Adds the project root (the directory containing the ``report_generation``
package) to ``sys.path`` so tests can ``import report_generation`` directly when
running ``python -m pytest`` from the project directory.
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
