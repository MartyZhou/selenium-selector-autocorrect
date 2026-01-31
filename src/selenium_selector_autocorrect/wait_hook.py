"""WebDriverWait integration hook for selector auto-correction."""

import logging
import time
from typing import Callable, Optional

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.wait import WebDriverWait

from .auto_correct import get_auto_correct
from .correction_tracker import record_correction

logger = logging.getLogger(__name__)

_original_until = WebDriverWait.until


def _patched_until(self, method: Callable, message: str = ""):
    """Patched until method with auto-correct support."""
    screen = None
    stacktrace = None

    end_time = time.monotonic() + self._timeout
    while True:
        try:
            value = method(self._driver)
            if value:
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

            driver = self._driver
            if isinstance(driver, WebElement):
                driver = driver.parent

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
                            return result
                    except Exception as e:
                        logger.warning(f"[AUTO-CORRECT] Suggested selector also failed: {e}")

    raise TimeoutException(message, screen, stacktrace)


def _extract_locator_from_method(method: Callable) -> Optional[tuple]:
    """Extract locator tuple (by, value) from an expected_conditions method."""
    try:
        if hasattr(method, "locator"):
            logger.debug(f"[AUTO-CORRECT] Found locator attribute: {method.locator}")
            return method.locator

        if hasattr(method, "__closure__") and method.__closure__:
            for cell in method.__closure__:
                cell_contents = cell.cell_contents
                logger.debug(f"[AUTO-CORRECT] Checking closure cell: {type(cell_contents)} = {cell_contents}")
                if isinstance(cell_contents, tuple) and len(cell_contents) == 2:
                    if isinstance(cell_contents[0], str) and isinstance(cell_contents[1], str):
                        logger.debug(f"[AUTO-CORRECT] Extracted locator from closure: {cell_contents}")
                        return cell_contents
        logger.warning(f"[AUTO-CORRECT] Could not extract locator from method: {method}")
    except Exception as e:
        logger.exception(f"[AUTO-CORRECT] Error extracting locator: {e}")
    return None


def _create_corrected_method(original_method: Callable, new_by: str, new_value: str) -> Optional[Callable]:
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


def install_auto_correct_hook():
    """Install the auto-correct hook into WebDriverWait."""
    WebDriverWait.until = _patched_until
    logger.info("[AUTO-CORRECT] Hook installed into WebDriverWait")


def uninstall_auto_correct_hook():
    """Remove the auto-correct hook from WebDriverWait."""
    WebDriverWait.until = _original_until
    logger.info("[AUTO-CORRECT] Hook removed from WebDriverWait")
