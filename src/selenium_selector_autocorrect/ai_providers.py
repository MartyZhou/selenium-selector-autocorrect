"""AI provider for selector auto-correction using local AI service."""

import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


class AIProvider(ABC):
    """Abstract base class for AI providers."""

    @abstractmethod
    def suggest_selector(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Request a selector suggestion from the AI service.
        
        Args:
            system_prompt: System-level instructions for the AI
            user_prompt: User query with failed selector and page context
            
        Returns:
            JSON string with suggestion or None if failed
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available and operational."""
        pass


class LocalAIProvider(AIProvider):
    """AI provider using local AI service with OpenAI-compatible API.
    
    Args:
        base_url: URL of the local AI service. If None, reads from
                  LOCAL_AI_API_URL environment variable (default: http://localhost:8765)
    """

    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url: str = base_url or os.environ.get("LOCAL_AI_API_URL", "http://localhost:8765")
        self._available: Optional[bool] = None
    
    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            url = f"{self.base_url}/v1/chat/completions"
            payload = {"messages": [{"role": "user", "content": "test"}], "max_tokens": 1}
            
            logger.debug(f"[AI-REQUEST] POST {url}")
            logger.debug(f"[AI-REQUEST] Payload: {payload}")
            
            response = requests.post(url, json=payload, timeout=30)
            
            logger.debug(f"[AI-RESPONSE] Status: {response.status_code}")
            logger.debug(f"[AI-RESPONSE] Headers: {dict(response.headers)}")
            logger.debug(f"[AI-RESPONSE] Body length: {len(response.text)} chars")
            if response.text:
                logger.debug(f"[AI-RESPONSE] Body preview: {response.text[:500]}")
            
            self._available = response.status_code in (200, 400)
        except Exception as e:
            logger.info(f"Local AI service not available at {self.base_url}: {e}")
            logger.debug(f"[AI-ERROR] Exception details: {type(e).__name__}: {str(e)}")
            self._available = False
        return self._available
    
    def suggest_selector(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Request a selector suggestion from the local AI service.
        
        Args:
            system_prompt: System message describing the task
            user_prompt: User message with page context and failed selector
            
        Returns:
            AI response text or None if request fails
        """
        try:
            url = f"{self.base_url}/v1/chat/completions"
            payload = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 500
            }
            
            logger.debug(f"[AI-REQUEST] POST {url}")
            logger.debug(f"[AI-REQUEST] System prompt ({len(system_prompt)} chars): {system_prompt[:200]}...")
            logger.debug(f"[AI-REQUEST] User prompt ({len(user_prompt)} chars): {user_prompt[:200]}...")
            logger.debug(f"[AI-REQUEST] Full payload: {payload}")
            
            response = requests.post(url, json=payload, timeout=30)
            
            logger.debug(f"[AI-RESPONSE] Status: {response.status_code}")
            logger.debug(f"[AI-RESPONSE] Headers: {dict(response.headers)}")
            logger.debug(f"[AI-RESPONSE] Body length: {len(response.text)} chars")
            logger.debug(f"[AI-RESPONSE] Full body: {response.text[:2000]}")
            
            response.raise_for_status()
            data: Dict[str, Any] = response.json()
            content: Optional[str] = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            logger.debug(f"[AI-PARSED] Content length: {len(content) if content else 0} chars")
            logger.debug(f"[AI-PARSED] Content preview: {content[:500] if content else 'None'}")
            return content
        except requests.exceptions.HTTPError as e:
            logger.error(f"[AI-ERROR] HTTP Error {e.response.status_code}")
            logger.error(f"[AI-ERROR] Response body: {e.response.text[:1000]}")
            if e.response.status_code == 503:
                logger.info(f"Local AI service unavailable (503). Disabling auto-correction.")
                self._available = False
            else:
                logger.warning(f"Local AI HTTP error: {e}")
            return None
        except Exception as e:
            logger.error(f"[AI-ERROR] Request failed: {type(e).__name__}: {str(e)}")
            logger.debug(f"[AI-ERROR] Exception details: {e}", exc_info=True)
            self._available = False
            return None


def get_provider() -> AIProvider:
    """Get the configured AI provider.
    
    Returns:
        LocalAIProvider instance
    """
    global _provider_instance
    if _provider_instance is None:
        _provider_instance = LocalAIProvider()
    return _provider_instance


def configure_provider(provider: AIProvider) -> None:
    """Set a custom AI provider.
    
    Args:
        provider: Instance of AIProvider to use
    """
    global _provider_instance
    _provider_instance = provider


_provider_instance: Optional[AIProvider] = None
