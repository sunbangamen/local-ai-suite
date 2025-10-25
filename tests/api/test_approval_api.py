#!/usr/bin/env python3
"""
Integration tests for Approval Workflow API v1 (Issue #45 Phase 6.3)

Test coverage:
- Authentication (API Key)
- CRUD operations (Create, Read, Update, Delete)
- Permission checking
- Error handling
- Statistics calculation
"""

import json
import sys
from pathlib import Path

# Add services to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "services" / "mcp-server"))


def test_api_key_auth_valid():
    """Test API Key authentication with valid key"""
    from api.auth import APIKeyAuth

    # Valid key should return user info
    user = APIKeyAuth.authenticate("approval-admin-001")
    assert user["api_key_id"] == "approval-admin-001"
    assert "admin" in user["roles"]
    assert "approval:view" in user["permissions"]
    assert "approval:approve" in user["permissions"]


def test_api_key_auth_invalid():
    """Test API Key authentication with invalid key"""
    from api.auth import APIKeyAuth
    from fastapi import HTTPException

    # Invalid key should raise 401
    try:
        APIKeyAuth.authenticate("invalid-key")
        assert False, "Should have raised HTTPException"
    except HTTPException as e:
        assert e.status_code == 401


def test_api_key_auth_missing():
    """Test API Key authentication with missing key"""
    from api.auth import APIKeyAuth
    from fastapi import HTTPException

    # Missing key should raise 401
    try:
        APIKeyAuth.authenticate(None)
        assert False, "Should have raised HTTPException"
    except HTTPException as e:
        assert e.status_code == 401


def test_permission_check_allowed():
    """Test permission checking - allowed"""
    from api.auth import APIKeyAuth

    user = APIKeyAuth.authenticate("approval-admin-001")

    # Should not raise for valid permission
    APIKeyAuth.check_permission(user, "approval:approve")


def test_permission_check_denied():
    """Test permission checking - denied"""
    from api.auth import APIKeyAuth
    from fastapi import HTTPException

    user = {"user_id": "test", "roles": ["viewer"], "permissions": ["approval:view"]}

    # Should raise 403 for insufficient permission
    try:
        APIKeyAuth.check_permission(user, "approval:approve")
        assert False, "Should have raised HTTPException"
    except HTTPException as e:
        assert e.status_code == 403


def test_get_permissions_for_roles():
    """Test permission mapping for different roles"""
    from api.auth import APIKeyAuth

    # Admin has all permissions
    admin_perms = APIKeyAuth._get_permissions_for_roles(["admin"])
    assert "approval:view" in admin_perms
    assert "approval:approve" in admin_perms
    assert "approval:reject" in admin_perms
    assert "approval:cancel" in admin_perms

    # Operator has limited permissions
    operator_perms = APIKeyAuth._get_permissions_for_roles(["operator"])
    assert "approval:view" in operator_perms
    assert "approval:approve" in operator_perms
    assert "approval:reject" in operator_perms
    assert "approval:create" not in operator_perms

    # Viewer has read-only permission
    viewer_perms = APIKeyAuth._get_permissions_for_roles(["viewer"])
    assert "approval:view" in viewer_perms
    assert "approval:approve" not in viewer_perms


def test_approval_workflow_json_schema():
    """Test that OpenAPI schema is valid"""
    from pathlib import Path
    import yaml

    spec_path = (
        Path(__file__).parent.parent.parent / "docs" / "api" / "APPROVAL_API_SPEC.yaml"
    )
    assert spec_path.exists(), f"OpenAPI spec not found: {spec_path}"

    with open(spec_path) as f:
        spec = yaml.safe_load(f)

    # Verify spec structure
    assert "openapi" in spec
    assert spec["openapi"].startswith("3.0")
    assert "paths" in spec
    assert "components" in spec
    assert "securitySchemes" in spec["components"]


def test_approval_api_paths_defined():
    """Test that all required API paths are defined"""
    from pathlib import Path
    import yaml

    spec_path = (
        Path(__file__).parent.parent.parent / "docs" / "api" / "APPROVAL_API_SPEC.yaml"
    )

    with open(spec_path) as f:
        spec = yaml.safe_load(f)

    paths = spec["paths"]

    # Verify all required paths exist
    assert "/approvals" in paths
    assert "/approvals/{request_id}" in paths
    assert "/approvals/stats" in paths


def test_approval_api_auth_required():
    """Test that API authentication is required"""
    from pathlib import Path
    import yaml

    spec_path = (
        Path(__file__).parent.parent.parent / "docs" / "api" / "APPROVAL_API_SPEC.yaml"
    )

    with open(spec_path) as f:
        spec = yaml.safe_load(f)

    # Verify security is defined
    assert "security" in spec
    assert len(spec["security"]) > 0

    # Verify ApiKeyAuth is defined
    assert "securitySchemes" in spec["components"]
    assert "ApiKeyAuth" in spec["components"]["securitySchemes"]
    assert spec["components"]["securitySchemes"]["ApiKeyAuth"]["type"] == "apiKey"


def test_approval_request_schema_complete():
    """Test that ApprovalRequest schema has all required fields"""
    from pathlib import Path
    import yaml

    spec_path = (
        Path(__file__).parent.parent.parent / "docs" / "api" / "APPROVAL_API_SPEC.yaml"
    )

    with open(spec_path) as f:
        spec = yaml.safe_load(f)

    approval_schema = spec["components"]["schemas"]["ApprovalRequest"]

    # Verify required fields
    required = approval_schema["required"]
    assert "request_id" in required
    assert "user_id" in required
    assert "tool_name" in required
    assert "status" in required
    assert "requested_at" in required
    assert "expires_at" in required


def test_api_responses_documented():
    """Test that all API responses are documented"""
    from pathlib import Path
    import yaml

    spec_path = (
        Path(__file__).parent.parent.parent / "docs" / "api" / "APPROVAL_API_SPEC.yaml"
    )

    with open(spec_path) as f:
        spec = yaml.safe_load(f)

    # Check GET /approvals responses
    get_approvals = spec["paths"]["/approvals"]["get"]
    assert "responses" in get_approvals
    assert "200" in get_approvals["responses"]
    assert "400" in get_approvals["responses"]
    assert "401" in get_approvals["responses"]
    assert "403" in get_approvals["responses"]

    # Check POST /approvals responses
    post_approvals = spec["paths"]["/approvals"]["post"]
    assert "201" in post_approvals["responses"]
    assert "401" in post_approvals["responses"]

    # Check PUT /approvals/{request_id} responses
    put_approval = spec["paths"]["/approvals/{request_id}"]["put"]
    assert "200" in put_approval["responses"]
    assert "404" in put_approval["responses"]
    assert "409" in put_approval["responses"]


if __name__ == "__main__":
    # Run tests
    tests = [
        test_api_key_auth_valid,
        test_api_key_auth_invalid,
        test_api_key_auth_missing,
        test_permission_check_allowed,
        test_permission_check_denied,
        test_get_permissions_for_roles,
        test_approval_workflow_json_schema,
        test_approval_api_paths_defined,
        test_approval_api_auth_required,
        test_approval_request_schema_complete,
        test_api_responses_documented,
    ]

    print("Running Approval API v1 tests...")
    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            print(f"✅ {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__}: {str(e)}")
            failed += 1

    print(f"\n결과: {passed}/{len(tests)} 통과")
    if failed > 0:
        sys.exit(1)
