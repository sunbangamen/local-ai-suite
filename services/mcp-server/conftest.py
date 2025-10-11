# Pytest configuration for MCP Server tests

import sys
from pathlib import Path

# Add service root to Python path for imports
service_root = Path(__file__).parent
sys.path.insert(0, str(service_root))

# Tell pytest to ignore __init__.py in service root
collect_ignore = ["__init__.py"]
collect_ignore_glob = ["__init__.py"]
