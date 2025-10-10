#!/bin/bash
# Run Approval Workflow Integration Tests (Issue #16)

set -e

echo "======================================"
echo "Approval Workflow Integration Tests"
echo "Issue #16"
echo "======================================"
echo ""

# Check if pytest is installed
if ! python3 -c "import pytest" 2>/dev/null; then
    echo "Installing test dependencies..."
    pip install pytest pytest-asyncio
fi

# Run tests
echo "Running approval workflow tests..."
echo ""

cd "$(dirname "$0")"

# Run all approval workflow tests
pytest tests/test_approval_workflow.py \
    -v \
    -s \
    --tb=short \
    --color=yes \
    -m "not performance" \
    2>&1 | tee test_results.log

# Run performance test separately
echo ""
echo "======================================"
echo "Running performance test..."
echo "======================================"
pytest tests/test_approval_workflow.py::test_performance_bulk_approvals \
    -v \
    -s \
    --tb=short \
    --color=yes \
    2>&1 | tee -a test_results.log

echo ""
echo "======================================"
echo "Test Results Summary"
echo "======================================"
echo "Full log saved to: test_results.log"
echo ""
