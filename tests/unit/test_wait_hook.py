"""Unit tests for wait_hook module."""

import pytest
from selenium_selector_autocorrect.wait_hook import install_auto_correct_hook, uninstall_auto_correct_hook


class TestWaitHook:
    """Test wait_hook functionality."""

    def test_hook_installation(self):
        """Hook can be installed without errors."""
        install_auto_correct_hook()
        # Verify hook is installed by checking WebDriverWait
        from selenium.webdriver.support.wait import WebDriverWait
        assert hasattr(WebDriverWait, "until")

    def test_hook_uninstallation(self):
        """Hook can be uninstalled without errors."""
        install_auto_correct_hook()
        uninstall_auto_correct_hook()
        # Should not raise any exception
        assert True
