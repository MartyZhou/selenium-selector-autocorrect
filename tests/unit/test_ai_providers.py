"""Unit tests for AI providers."""

import pytest
from selenium_selector_autocorrect.ai_providers import AIProvider, LocalAIProvider


class TestAIProvider:
    """Test AIProvider abstract class."""

    def test_cannot_instantiate_abstract_class(self):
        """AIProvider is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            AIProvider()


class TestLocalAIProvider:
    """Test LocalAIProvider implementation."""

    def test_provider_initialization(self):
        """LocalAIProvider initializes with default URL."""
        provider = LocalAIProvider()
        assert provider.base_url == "http://localhost:8765"

    def test_provider_custom_url(self):
        """LocalAIProvider accepts custom base URL."""
        custom_url = "http://custom-ai:9000"
        provider = LocalAIProvider(base_url=custom_url)
        assert provider.base_url == custom_url

    def test_is_available_returns_boolean(self):
        """is_available returns boolean value."""
        provider = LocalAIProvider()
        result = provider.is_available()
        assert isinstance(result, bool)
