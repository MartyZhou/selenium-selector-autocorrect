"""WebDriverWait integration hook for selector auto-correction."""

import logging
import time
from typing import Any, Callable, Optional, Tuple, TypeVar, Union, cast

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.wait import WebDriverWait

from .auto_correct import get_auto_correct
from .correction_tracker import record_correction

logger = logging.getLogger(__name__)

T = TypeVar("T")
DriverType = Union[WebDriver, WebElement]

_original_until: Callable[..., Any] = WebDriverWait.until


def _patched_until(self: WebDriverWait, method: Callable[[WebDriver], T], message: str = "") -> T:
    """Patched until method with auto-correct support."""
    screen: Optional[str] = None
    stacktrace: Optional[str] = None

    end_time = time.monotonic() + self._timeout
    while True:
        try:
            value = method(self._driver)
            if value:
                # Check if we should suggest a better selector for the found element
                auto_correct = get_auto_correct()
                if auto_correct.suggest_better_selectors and isinstance(value, WebElement):
                    locator = _extract_locator_from_method(method)
                    if locator:
                        by, value_str = locator
                        suggest_driver: WebDriver
                        if isinstance(self._driver, WebElement):
                            suggest_driver = self._driver.parent  # type: ignore[attr-defined]
                        else:
                            suggest_driver = self._driver
                        
                        better_suggestion = auto_correct.suggest_better_selector(
                            suggest_driver, by, value_str, value
                        )
                        if better_suggestion:
                            better_by, better_value = better_suggestion
                            logger.info(f"[AUTO-SUGGEST] Found element with {by}='{value_str[:50]}...'")
                            logger.info(f"[AUTO-SUGGEST] Suggested better selector: {better_by}='{better_value}'")
                return value
        except self._ignored_exceptions as exc:
            screen = getattr(exc, "screen", None)
            stacktrace = getattr(exc, "stacktrace", None)
        if time.monotonic() > end_time:
            break
        time.sleep(self._poll)

    auto_correct = get_auto_correct()
    if auto_correct.enabled:
        locator = _extract_locator_from_method(method)
        if locator:
            by, value_str = locator
            logger.warning(
                f"[AUTO-CORRECT] Timeout waiting for element {by}='{value_str[:80]}...' - attempting auto-correction"
            )

            driver: WebDriver
            if isinstance(self._driver, WebElement):
                driver = self._driver.parent  # type: ignore[attr-defined]
            else:
                driver = self._driver

            suggestion = auto_correct.suggest_selector(
                driver,
                failed_by=by,
                failed_value=value_str,
                error_message=message or f"Timeout waiting for element with {by}={value_str}",
            )

            if suggestion:
                suggested_by, suggested_value = suggestion
                logger.warning(f"[AUTO-CORRECT] Trying suggested selector: {suggested_by}='{suggested_value}'")

                corrected_method = _create_corrected_method(method, suggested_by, suggested_value)
                if corrected_method:
                    try:
                        result = corrected_method(self._driver)
                        if result:
                            logger.warning(f"[AUTO-CORRECT] SUCCESS! Element found with corrected selector")
                            record_correction(
                                original_by=by,
                                original_value=value_str,
                                corrected_by=suggested_by,
                                corrected_value=suggested_value,
                                success=True,
                            )
                            return cast(T, result)
                    except Exception as e:
                        logger.warning(f"[AUTO-CORRECT] Suggested selector also failed: {e}")

    raise TimeoutException(message, screen, stacktrace)


def _extract_locator_from_method(method: Callable[..., Any]) -> Optional[Tuple[str, str]]:
    """Extract locator tuple (by, value) from an expected_conditions method."""
    try:
        if hasattr(method, "locator"):
            locator: Tuple[str, str] = method.locator
            logger.debug(f"[AUTO-CORRECT] Found locator attribute: {locator}")
            return locator

        if hasattr(method, "__closure__") and method.__closure__:
            for cell in method.__closure__:
                cell_contents = cell.cell_contents
                logger.debug(f"[AUTO-CORRECT] Checking closure cell: {type(cell_contents)} = {cell_contents}")
                if isinstance(cell_contents, tuple) and len(cell_contents) == 2:
                    first, second = cell_contents
                    if isinstance(first, str) and isinstance(second, str):
                        logger.debug(f"[AUTO-CORRECT] Extracted locator from closure: {cell_contents}")
                        return (first, second)
        logger.warning(f"[AUTO-CORRECT] Could not extract locator from method: {method}")
    except Exception as e:
        logger.exception(f"[AUTO-CORRECT] Error extracting locator: {e}")
    return None


def _create_corrected_method(
    original_method: Callable[..., Any],
    new_by: str,
    new_value: str
) -> Optional[Callable[[WebDriver], Any]]:
    """Create a new expected condition method with corrected locator."""
    try:
        from selenium.webdriver.support import expected_conditions as EC
        
        method_name = None
        if hasattr(original_method, '__qualname__'):
            qualname = original_method.__qualname__
            if '.<locals>._predicate' in qualname:
                method_name = qualname.split('.<locals>._predicate')[0]
        
        if not method_name:
            method_name = original_method.__class__.__name__
        
        method_map = {
            "visibility_of_element_located": EC.visibility_of_element_located,
            "presence_of_element_located": EC.presence_of_element_located,
            "element_to_be_clickable": EC.element_to_be_clickable,
            "invisibility_of_element_located": EC.invisibility_of_element_located,
        }
        
        ec_method = method_map.get(method_name, EC.visibility_of_element_located)
        return ec_method((new_by, new_value))
        
    except Exception as e:
        logger.exception(f"[AUTO-CORRECT] Error creating corrected method: {e}")
        return None


def install_auto_correct_hook() -> None:
    """Install the auto-correct hook into WebDriverWait."""
    WebDriverWait.until = _patched_until  # type: ignore[method-assign,assignment]
    logger.info("[AUTO-CORRECT] Hook installed into WebDriverWait")


def uninstall_auto_correct_hook() -> None:
    """Remove the auto-correct hook from WebDriverWait."""
    WebDriverWait.until = _original_until  # type: ignore[method-assign]
    logger.info("[AUTO-CORRECT] Hook removed from WebDriverWait")
