"""Puts batch/ on sys.path so tests can `import indicators`, `import labels`, etc. the same
flat way run_daily.py does — the batch/ scripts aren't a package (no __init__.py), they're
meant to run with batch/ itself as the working directory / on sys.path.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "batch"))
