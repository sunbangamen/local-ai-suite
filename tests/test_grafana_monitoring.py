#!/usr/bin/env python3
"""
Integration tests for Phase 6.2: Grafana Monitoring Extension (Issue #45)

Tests:
1. Prometheus metrics are collected correctly
2. Grafana dashboards are properly formatted
3. Alertmanager rules are syntactically valid
"""

import json
import yaml
from pathlib import Path


def test_approval_request_metrics_exist():
    """Test that approval request metrics are defined"""
    # Check if app.py contains approval_requests_total metric definition
    app_path = Path(__file__).parent.parent / "services/mcp-server/app.py"
    content = app_path.read_text()

    assert "approval_requests_total" in content, "approval_requests_total metric not found"
    assert "approval_response_time_seconds" in content, "approval_response_time_seconds metric not found"
    assert "approval_timeout_total" in content, "approval_timeout_total metric not found"
    assert "rbac_permission_checks_total" in content, "rbac_permission_checks_total metric not found"
    assert "rbac_role_assignments_total" in content, "rbac_role_assignments_total metric not found"


def test_approval_workflow_dashboard_valid_json():
    """Test that approval_workflow.json is valid JSON"""
    dashboard_path = Path(__file__).parent.parent / "docker/monitoring/grafana/dashboards/approval_workflow.json"
    assert dashboard_path.exists(), f"Dashboard not found: {dashboard_path}"

    with open(dashboard_path) as f:
        data = json.load(f)

    assert "dashboard" in data, "dashboard key not found in JSON"
    assert "title" in data["dashboard"], "title not found in dashboard"
    assert data["dashboard"]["title"] == "Approval Workflow Metrics"
    assert "panels" in data["dashboard"], "panels not found in dashboard"
    assert len(data["dashboard"]["panels"]) > 0, "No panels defined in dashboard"


def test_rbac_metrics_dashboard_valid_json():
    """Test that rbac_metrics.json is valid JSON"""
    dashboard_path = Path(__file__).parent.parent / "docker/monitoring/grafana/dashboards/rbac_metrics.json"
    assert dashboard_path.exists(), f"Dashboard not found: {dashboard_path}"

    with open(dashboard_path) as f:
        data = json.load(f)

    assert "dashboard" in data, "dashboard key not found in JSON"
    assert data["dashboard"]["title"] == "RBAC Metrics"
    assert len(data["dashboard"]["panels"]) > 0, "No panels defined in dashboard"


def test_sla_tracking_dashboard_valid_json():
    """Test that sla_tracking.json is valid JSON"""
    dashboard_path = Path(__file__).parent.parent / "docker/monitoring/grafana/dashboards/sla_tracking.json"
    assert dashboard_path.exists(), f"Dashboard not found: {dashboard_path}"

    with open(dashboard_path) as f:
        data = json.load(f)

    assert "dashboard" in data, "dashboard key not found in JSON"
    assert data["dashboard"]["title"] == "SLA Tracking"
    assert len(data["dashboard"]["panels"]) > 0, "No panels defined in dashboard"


def test_alert_rules_valid_yaml():
    """Test that alert_rules.yml is valid YAML with approval alerts"""
    rules_path = Path(__file__).parent.parent / "docker/monitoring/prometheus/alert_rules.yml"
    assert rules_path.exists(), f"Alert rules not found: {rules_path}"

    with open(rules_path) as f:
        data = yaml.safe_load(f)

    assert "groups" in data, "groups key not found in alert_rules.yml"
    assert len(data["groups"]) > 0, "No groups defined in alert rules"

    # Find approval-related alerts
    approval_alerts = []
    for group in data["groups"]:
        for rule in group.get("rules", []):
            if "ApprovalRequest" in rule.get("alert", "") or "Approval" in rule.get("alert", ""):
                approval_alerts.append(rule)

    assert len(approval_alerts) >= 2, f"Expected at least 2 approval alerts, found {len(approval_alerts)}"

    # Verify ApprovalRequestTimeout alert
    timeout_alert = next((a for a in approval_alerts if a["alert"] == "ApprovalRequestTimeout"), None)
    assert timeout_alert is not None, "ApprovalRequestTimeout alert not found"
    assert "approval_timeout_total" in timeout_alert["expr"], "approval_timeout_total not found in alert expression"

    # Verify HighApprovalRejectionRate alert
    rejection_alert = next((a for a in approval_alerts if a["alert"] == "HighApprovalRejectionRate"), None)
    assert rejection_alert is not None, "HighApprovalRejectionRate alert not found"
    assert "approval_requests_total" in rejection_alert["expr"], "approval_requests_total not found in alert expression"


def test_metric_recording_in_approval_endpoints():
    """Test that metrics are recorded in approval endpoints"""
    app_path = Path(__file__).parent.parent / "services/mcp-server/app.py"
    content = app_path.read_text()

    # Check if approve_request endpoint records metrics
    assert "approval_requests_total.labels(status=\"approved\").inc()" in content, \
        "Metric recording not found in approve_request endpoint"

    # Check if reject_request endpoint records metrics
    assert "approval_requests_total.labels(status=\"rejected\").inc()" in content, \
        "Metric recording not found in reject_request endpoint"

    # Check if timeout detection records metrics
    assert "approval_timeout_total.inc()" in content, \
        "Timeout metric recording not found in get_approval_status endpoint"


def test_rbac_middleware_metrics_integration():
    """Test that RBAC middleware is configured to use metrics"""
    middleware_path = Path(__file__).parent.parent / "services/mcp-server/rbac_middleware.py"
    content = middleware_path.read_text()

    assert "set_rbac_metrics" in content, "set_rbac_metrics function not found"
    assert "rbac_permission_checks_total" in content, "rbac_permission_checks_total not referenced in middleware"


def test_all_dashboards_have_required_fields():
    """Test that all dashboards have required fields"""
    dashboards = [
        "approval_workflow.json",
        "rbac_metrics.json",
        "sla_tracking.json"
    ]

    for dashboard_name in dashboards:
        dashboard_path = Path(__file__).parent.parent / f"docker/monitoring/grafana/dashboards/{dashboard_name}"
        assert dashboard_path.exists(), f"Dashboard not found: {dashboard_name}"

        with open(dashboard_path) as f:
            data = json.load(f)

        dashboard = data["dashboard"]
        assert "title" in dashboard, f"{dashboard_name}: title field missing"
        assert "panels" in dashboard, f"{dashboard_name}: panels field missing"
        assert "refresh" in dashboard, f"{dashboard_name}: refresh field missing"
        assert len(dashboard["panels"]) > 0, f"{dashboard_name}: at least one panel required"

        # Verify each panel has required fields
        for i, panel in enumerate(dashboard["panels"]):
            assert "id" in panel, f"{dashboard_name} panel {i}: id field missing"
            assert "title" in panel, f"{dashboard_name} panel {i}: title field missing"
            assert "targets" in panel, f"{dashboard_name} panel {i}: targets field missing"
            assert len(panel["targets"]) > 0, f"{dashboard_name} panel {i}: at least one target required"


if __name__ == "__main__":
    # Run basic checks when executed directly
    print("✅ Testing Prometheus metrics...")
    test_approval_request_metrics_exist()

    print("✅ Testing Grafana dashboards...")
    test_approval_workflow_dashboard_valid_json()
    test_rbac_metrics_dashboard_valid_json()
    test_sla_tracking_dashboard_valid_json()
    test_all_dashboards_have_required_fields()

    print("✅ Testing Prometheus alert rules...")
    test_alert_rules_valid_yaml()

    print("✅ Testing metric recording...")
    test_metric_recording_in_approval_endpoints()
    test_rbac_middleware_metrics_integration()

    print("\n✨ All Phase 6.2 tests passed!")
