"""Core selector auto-correction functionality for Selenium WebDriver."""

import json
import logging
import os
import re
from typing import Any, Dict, Optional, Tuple

from .ai_providers import get_provider

logger = logging.getLogger(__name__)


class SelectorAutoCorrect:
    """Auto-corrects element selectors by analyzing the page and requesting AI suggestions.
    
    Args:
        enabled: Whether auto-correction is enabled
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._provider = None
        self._correction_cache: Dict[str, str] = {}
        self._suggestion_cache: Dict[str, str] = {}
        self.suggest_better_selectors = os.environ.get("SELENIUM_SUGGEST_BETTER", "0").lower() in ("1", "true", "yes")
        self._confidence_threshold = 50
        self._cache_enabled = True

    @property
    def provider(self):
        if self._provider is None:
            self._provider = get_provider()
        return self._provider

    def set_provider(self, provider) -> None:
        self._provider = provider

    def is_service_available(self) -> bool:
        if not self.enabled:
            return False
        provider = self.provider
        return provider is not None and provider.is_available()

    def get_visible_elements_summary(self, driver) -> str:
        try:
            script = """
            function getElementSummary() {
                const selectors = ['input', 'button', 'a', 'select', 'textarea',
                    '[role="button"]', '[role="link"]', '[data-testid]', '[data-test]', '[id]', '[name]'];
                const elements = [];
                selectors.forEach(selector => {
                    document.querySelectorAll(selector).forEach(el => {
                        if (el.offsetParent !== null) {
                            const info = {
                                tag: el.tagName.toLowerCase(),
                                id: el.id || null,
                                name: el.getAttribute('name') || null,
                                class: el.className || null,
                                type: el.getAttribute('type') || null,
                                text: (el.innerText || '').substring(0, 50),
                                placeholder: el.getAttribute('placeholder') || null,
                                ariaLabel: el.getAttribute('aria-label') || null,
                                dataTestId: el.getAttribute('data-testid') || el.getAttribute('data-test') || null,
                                role: el.getAttribute('role') || null
                            };
                            if (info.id || info.name || info.dataTestId || info.text || info.ariaLabel) {
                                elements.push(info);
                            }
                        }
                    });
                });
                const seen = new Set();
                return elements.filter(el => {
                    const key = JSON.stringify(el);
                    if (seen.has(key)) return false;
                    seen.add(key);
                    return true;
                }).slice(0, 100);
            }
            return JSON.stringify(getElementSummary());
            """
            result = driver.execute_script(script)
            return result if result else "[]"
        except Exception as e:
            logger.warning(f"Failed to get element summary: {e}")
            return "[]"

    def suggest_selector(self, driver, failed_by: str, failed_value: str, error_message: str = "") -> Optional[Tuple[str, str]]:
        if not self.enabled or not self.is_service_available():
            return None

        cache_key = f"{failed_by}:{failed_value}"
        if self._cache_enabled and cache_key in self._correction_cache:
            logger.info(f"[AUTO-CORRECT] Using cached correction for {failed_value[:50]}")
            return self._parse_selector_suggestion(self._correction_cache[cache_key])

        try:
            elements_summary = self.get_visible_elements_summary(driver)
            current_url = driver.current_url

            system_prompt = """You are an expert at fixing Selenium element selectors.
When given a failed selector and available elements, suggest a working alternative.
ONLY respond with a JSON object containing:
- "by": the selector strategy ("css selector", "xpath", "id", "name", etc.)
- "value": the selector value
- "confidence": a number 0-100
- "reason": brief explanation

If no good alternative exists, respond with:
{"by": null, "value": null, "confidence": 0, "reason": "No suitable alternative found"}"""

            user_prompt = f"""The following selector failed:
- Strategy: {failed_by}
- Value: {failed_value}
- URL: {current_url}
- Error: {error_message}

Available Elements:
```json
{elements_summary}
```

Suggest a working selector. Respond with ONLY a JSON object."""

            logger.info(f"[AUTO-CORRECT] Requesting selector suggestion for: {failed_value[:50]}...")
            response = self.provider.suggest_selector(system_prompt, user_prompt)

            if response:
                suggestion = self._parse_selector_suggestion(response)
                if suggestion and self._cache_enabled:
                    self._correction_cache[cache_key] = response
                return suggestion
            else:
                if self.provider and not self.provider.is_available():
                    logger.info("[AUTO-CORRECT] Service unavailable, auto-correction disabled for this session")
                    self.enabled = False
        except Exception as e:
            logger.warning(f"[AUTO-CORRECT] Failed to get suggestion: {e}")
        return None

    def suggest_better_selector(self, driver, current_by: str, current_value: str, element) -> Optional[Tuple[str, str]]:
        if not self.suggest_better_selectors or not self.enabled or not self.is_service_available():
            return None

        if current_by in ("id", "name") or (current_by == "css selector" and "[data-testid=" in current_value):
            return None

        cache_key = f"{current_by}:{current_value}"
        if self._cache_enabled and cache_key in self._suggestion_cache:
            cached = self._suggestion_cache[cache_key]
            if cached == "OPTIMAL":
                return None
            return self._parse_selector_suggestion(cached)

        try:
            element_info = self._get_element_info(element)
            elements_summary = self.get_visible_elements_summary(driver)

            system_prompt = """You are an expert at improving Selenium element selectors.
Suggest a better selector ONLY if the current one is fragile.
Preference: data-testid > id > name > css class > xpath

Respond with JSON: {"by": ..., "value": ..., "confidence": ..., "reason": ...}
If current is optimal: {"by": null, "value": null, "confidence": 100, "reason": "Current selector is optimal"}"""

            user_prompt = f"""Current Selector: {current_by}='{current_value}'
Element attributes: {json.dumps(element_info, indent=2)}
Available Elements:
```json
{elements_summary}
```"""

            response = self.provider.suggest_selector(system_prompt, user_prompt)
            if response:
                suggestion = self._parse_selector_suggestion(response)
                if suggestion:
                    if self._cache_enabled:
                        self._suggestion_cache[cache_key] = response
                    return suggestion
                else:
                    if self._cache_enabled:
                        self._suggestion_cache[cache_key] = "OPTIMAL"
        except Exception as e:
            logger.debug(f"[SUGGEST] Failed to get better selector: {e}")
        return None

    def _get_element_info(self, element) -> Dict[str, Any]:
        try:
            info = {
                "tag": element.tag_name,
                "id": element.get_attribute("id"),
                "name": element.get_attribute("name"),
                "class": element.get_attribute("class"),
                "data-testid": element.get_attribute("data-testid") or element.get_attribute("data-test"),
                "aria-label": element.get_attribute("aria-label"),
            }
            return {k: v for k, v in info.items() if v}
        except Exception:
            return {}

    def _parse_selector_suggestion(self, content: str) -> Optional[Tuple[str, str]]:
        try:
            json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                by = data.get("by")
                value = data.get("value")
                confidence = data.get("confidence", 0)
                reason = data.get("reason", "")

                if by and value and confidence >= self._confidence_threshold:
                    logger.info(f"[AUTO-CORRECT] Suggested selector (confidence: {confidence}%)")
                    logger.info(f"   Strategy: {by}")
                    logger.info(f"   Value: {value}")
                    logger.info(f"   Reason: {reason}")
                    return (by, value)
                elif reason:
                    logger.info(f"[AUTO-CORRECT] No good suggestion - {reason}")
        except json.JSONDecodeError as e:
            logger.warning(f"[AUTO-CORRECT] Failed to parse JSON: {e}")
        except Exception as e:
            logger.warning(f"[AUTO-CORRECT] Error parsing suggestion: {e}")
        return None

    def clear_cache(self):
        self._correction_cache.clear()
        self._suggestion_cache.clear()


_auto_correct_instance: Optional[SelectorAutoCorrect] = None


def get_auto_correct() -> SelectorAutoCorrect:
    """Get the global SelectorAutoCorrect instance."""
    global _auto_correct_instance
    if _auto_correct_instance is None:
        enabled = os.environ.get("SELENIUM_AUTO_CORRECT", "1").lower() in ("1", "true", "yes")
        _auto_correct_instance = SelectorAutoCorrect(enabled=enabled)
    return _auto_correct_instance


def set_auto_correct_enabled(enabled: bool):
    """Enable or disable auto-correction globally."""
    get_auto_correct().enabled = enabled


def configure_auto_correct(provider=None, enabled: bool = True, suggest_better: bool = False):
    """Configure auto-correction settings."""
    auto_correct = get_auto_correct()
    auto_correct.enabled = enabled
    auto_correct.suggest_better_selectors = suggest_better
    if provider:
        auto_correct.set_provider(provider)
