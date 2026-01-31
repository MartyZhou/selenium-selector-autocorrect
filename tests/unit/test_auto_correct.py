"""Unit tests for auto_correct module."""

import pytest
from selenium_selector_autocorrect.auto_correct import SelectorAutoCorrect, get_auto_correct


class TestSelectorAutoCorrect:
    """Test SelectorAutoCorrect class."""

    def test_initialization_enabled(self):
        """SelectorAutoCorrect initializes with enabled state."""
        auto_correct = SelectorAutoCorrect(enabled=True)
        assert auto_correct.enabled is True

    def test_initialization_disabled(self):
        """SelectorAutoCorrect initializes with disabled state."""
        auto_correct = SelectorAutoCorrect(enabled=False)
        assert auto_correct.enabled is False

    def test_cache_management(self):
        """SelectorAutoCorrect manages cache correctly."""
        auto_correct = SelectorAutoCorrect()
        auto_correct.clear_cache()
        # Should not raise any exception
        assert True


class TestAutoCorrectModule:
    """Test module-level functions."""

    def test_get_auto_correct_singleton(self):
        """get_auto_correct returns singleton instance."""
        instance1 = get_auto_correct()
        instance2 = get_auto_correct()
        assert instance1 is instance2
