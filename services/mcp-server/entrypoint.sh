#!/bin/bash
set -e

# Configure git for the runtime user (may be different from build-time root)
git config --global user.name "MCP Server" || true
git config --global user.email "mcp@local-ai-suite.local" || true
git config --global --add safe.directory /mnt/workspace || true
git config --global --add safe.directory /mnt/workspace/.git-main || true
git config --global --add safe.directory /mnt/e/local-ai-suite || true
git config --global --add safe.directory '*' || true

# Execute the main command
exec "$@"
