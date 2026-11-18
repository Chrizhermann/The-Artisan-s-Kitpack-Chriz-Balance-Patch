"""Keep shared fixture imports available in both unittest discovery modes."""

from pathlib import Path
import sys


fixture_directory = str(Path(__file__).resolve().parent)
if fixture_directory not in sys.path:
    sys.path.insert(0, fixture_directory)
