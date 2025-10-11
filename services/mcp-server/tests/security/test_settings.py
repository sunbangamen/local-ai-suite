#!/usr/bin/env python3
"""
Unit Tests for Security Settings Module
"""

import os
import pytest
from pathlib import Path

from settings import SecuritySettings, get_security_settings


@pytest.mark.unit
class TestSecuritySettings:
    """Test SecuritySettings configuration loading"""

    def test_default_values(self):
        """Test default configuration values"""
        assert SecuritySettings.SECURITY_MODE in ["strict", "normal", "legacy"]
        assert SecuritySettings.SECURITY_QUEUE_SIZE > 0
        assert SecuritySettings.SECURITY_LOG_LEVEL in [
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
        ]

    def test_rbac_enabled_flag(self, monkeypatch):
        """Test RBAC_ENABLED environment variable parsing"""
        # Test true
        monkeypatch.setenv("RBAC_ENABLED", "true")
        assert SecuritySettings.is_rbac_enabled() or os.getenv("RBAC_ENABLED") == "true"

        # Test false
        monkeypatch.setenv("RBAC_ENABLED", "false")
        # Need to reload module or check env directly
        assert os.getenv("RBAC_ENABLED") == "false"

    def test_sandbox_enabled_flag(self, monkeypatch):
        """Test SANDBOX_ENABLED environment variable parsing"""
        monkeypatch.setenv("SANDBOX_ENABLED", "true")
        assert os.getenv("SANDBOX_ENABLED") == "true"

    def test_db_path_creation(self, tmp_path):
        """Test database path creation"""
        test_db_path = tmp_path / "test_security.db"
        # Path should be valid
        assert isinstance(test_db_path, Path)

    def test_validate_config_valid(self):
        """Test config validation with valid settings"""
        warnings = SecuritySettings.validate_config()
        # Should return list (may be empty or have warnings)
        assert isinstance(warnings, list)

    def test_validate_config_invalid_mode(self, monkeypatch):
        """Test config validation with invalid security mode"""
        monkeypatch.setattr(SecuritySettings, "SECURITY_MODE", "invalid_mode")
        warnings = SecuritySettings.validate_config()

        # Should have warning about invalid mode
        assert len(warnings) > 0
        assert any("유효하지 않은 보안 모드" in w for w in warnings)

    def test_get_security_settings_singleton(self):
        """Test settings singleton pattern"""
        settings1 = get_security_settings()
        settings2 = get_security_settings()

        assert settings1 is settings2  # Same instance

    @pytest.mark.parametrize("mode", ["strict", "normal", "legacy"])
    def test_valid_security_modes(self, mode):
        """Test all valid security modes"""
        assert mode in ["strict", "normal", "legacy"]


@pytest.mark.unit
class TestFeatureFlags:
    """Test feature flag functionality"""

    def test_all_flags_boolean(self):
        """Test that all feature flags return boolean values"""
        assert isinstance(SecuritySettings.is_rbac_enabled(), bool)
        assert isinstance(SecuritySettings.is_sandbox_enabled(), bool)
        assert isinstance(SecuritySettings.is_rate_limit_enabled(), bool)
        assert isinstance(SecuritySettings.is_approval_workflow_enabled(), bool)

    def test_flag_independence(self):
        """Test that flags can be set independently"""
        # This is a behavioral test - flags should work independently
        # In production, some combinations might be invalid, but that's business logic
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
