"""Correction tracker for recording and applying selector fixes."""

import json
import logging
import os
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict

import requests

logger = logging.getLogger(__name__)


class CorrectionRecord(TypedDict, total=False):
    """Type definition for a correction record."""
    original_by: str
    original_value: str
    corrected_by: str
    corrected_value: str
    success: bool
    test_file: Optional[str]
    test_line: Optional[int]
    timestamp: str


class ApplyCorrectionsResult(TypedDict):
    """Type definition for apply_all_corrections result."""
    total: int
    success: int
    failed: int
    details: List[Dict[str, Any]]


class CorrectionTracker:
    """Tracks selector corrections and manages test file updates."""

    def __init__(self) -> None:
        self._corrections: List[CorrectionRecord] = []
        self._local_ai_url: str = os.environ.get("LOCAL_AI_API_URL", "http://localhost:8765")
        self._auto_update_enabled: bool = os.environ.get("SELENIUM_AUTO_UPDATE_TESTS", "0").lower() in ("1", "true", "yes")

    def record_correction(
        self,
        original_by: str,
        original_value: str,
        corrected_by: str,
        corrected_value: str,
        success: bool = True,
        test_file: Optional[str] = None,
        test_line: Optional[int] = None
    ) -> None:
        if test_file is None or test_line is None:
            # Extract from stack trace, prioritizing actual test files
            for frame in traceback.extract_stack():
                filename = frame.filename.replace('\\', '/')
                filename_lower = filename.lower()
                # Skip selenium packages, pytest, and our autocorrect packages
                # Be specific to avoid skipping directories with "selenium" in the name
                if ('/selenium/' in filename_lower or 
                    '\\selenium\\' in filename or
                    '/site-packages/selenium/' in filename_lower or
                    '/pytest' in filename_lower or
                    '/_pytest' in filename_lower or
                    '/selenium_selector_autocorrect/' in filename_lower or
                    '\\selenium_selector_autocorrect\\' in filename):
                    continue
                # Prioritize test files, then page objects, then ui_client
                if ('test_library' in filename or
                    'test_' in filename or
                    'page_factory' in filename_lower or
                    'ui_client' in filename_lower):
                    test_file = filename
                    test_line = frame.lineno
                    # Don't break - keep looking for test files specifically
                    if 'test_' in filename or 'test_library' in filename:
                        break

        correction: CorrectionRecord = {
            "original_by": original_by,
            "original_value": original_value,
            "corrected_by": corrected_by,
            "corrected_value": corrected_value,
            "success": success,
            "test_file": test_file,
            "test_line": test_line,
            "timestamp": datetime.now().isoformat()
        }
        self._corrections.append(correction)

        try:
            logger.info(f"[CORRECTION TRACKED] {original_by}='{original_value[:30]}...' -> {corrected_by}='{corrected_value[:30]}...'")
            if test_file:
                logger.info(f"[CORRECTION SOURCE] File: {test_file}, Line: {test_line}")
        except Exception:
            pass

        if self._auto_update_enabled and success and test_file:
            logger.info(f"[AUTO-UPDATE] Attempting to update {test_file}...")
            self._auto_update_test_file(correction)

    def get_corrections(self) -> List[CorrectionRecord]:
        return self._corrections.copy()

    def get_successful_corrections(self) -> List[CorrectionRecord]:
        return [c for c in self._corrections if c.get("success", False)]

    def clear_corrections(self) -> None:
        self._corrections.clear()

    def _auto_update_test_file(self, correction: CorrectionRecord) -> None:
        try:
            test_file = correction.get("test_file")
            if not test_file:
                return
            result = self.update_test_file_via_service(
                test_file,
                correction["original_by"],
                correction["original_value"],
                correction["corrected_by"],
                correction["corrected_value"]
            )
            if result.get("success"):
                logger.info(f"[AUTO-UPDATE] Successfully updated {test_file}")
            else:
                logger.warning(f"[AUTO-UPDATE] Failed to update {test_file}: {result.get('errors', [])}")
        except Exception as e:
            logger.warning(f"[AUTO-UPDATE] Error updating test file: {e}")

    def update_test_file_via_service(
        self,
        file_path: str,
        original_by: str,
        original_value: str,
        corrected_by: str,
        corrected_value: str
    ) -> Dict[str, Any]:
        try:
            read_url = f"{self._local_ai_url}/v1/workspace/files/read"
            read_response = requests.post(read_url, json={"filePath": file_path}, timeout=30)
            read_response.raise_for_status()
            file_content = read_response.json()

            if not file_content.get("success"):
                return {"success": False, "errors": ["Could not read file"]}

            content = file_content.get("content", "")
            old_patterns = [
                f'"{original_value}"',
                f"'{original_value}'",
            ]

            found_pattern = None
            new_pattern = None
            for old_pattern in old_patterns:
                if old_pattern in content:
                    found_pattern = old_pattern
                    new_pattern = f'"{corrected_value}"' if old_pattern.startswith('"') else f"'{corrected_value}'"
                    break

            if not found_pattern:
                return {"success": False, "errors": [f"Could not find selector: {original_value[:50]}..."]}

            edit_url = f"{self._local_ai_url}/v1/workspace/files/edit"
            edit_response = requests.post(
                edit_url,
                json={"filePath": file_path, "oldString": found_pattern, "newString": new_pattern},
                timeout=30
            )
            edit_response.raise_for_status()
            result: Dict[str, Any] = edit_response.json()
            return result
        except requests.exceptions.ConnectionError:
            logger.warning(f"[LOCAL AI SERVICE] Not available at {self._local_ai_url}")
            return {"success": False, "errors": ["Local AI service not available"]}
        except Exception as e:
            logger.warning(f"[UPDATE ERROR] {e}")
            return {"success": False, "errors": [str(e)]}

    def export_corrections_report(self, output_file: str = "selector_corrections.json") -> None:
        with open(output_file, "w") as f:
            json.dump({
                "corrections": self._corrections,
                "summary": {
                    "total": len(self._corrections),
                    "successful": len(self.get_successful_corrections()),
                    "generated_at": datetime.now().isoformat()
                }
            }, f, indent=2)
        logger.info(f"[CORRECTIONS REPORT] Exported to {output_file}")

    def apply_all_corrections_to_files(self) -> ApplyCorrectionsResult:
        results: ApplyCorrectionsResult = {"total": 0, "success": 0, "failed": 0, "details": []}
        for correction in self.get_successful_corrections():
            test_file = correction.get("test_file")
            if not test_file:
                continue
            results["total"] += 1
            result = self.update_test_file_via_service(
                test_file,
                correction["original_by"],
                correction["original_value"],
                correction["corrected_by"],
                correction["corrected_value"]
            )
            if result.get("success"):
                results["success"] += 1
            else:
                results["failed"] += 1
            results["details"].append({
                "file": test_file,
                "original": correction["original_value"][:50],
                "corrected": correction["corrected_value"][:50],
                "result": result
            })
        logger.info(f"[APPLIED CORRECTIONS] {results['success']}/{results['total']} successful")
        return results


_correction_tracker: Optional[CorrectionTracker] = None


def get_correction_tracker() -> CorrectionTracker:
    """Get the global CorrectionTracker instance."""
    global _correction_tracker
    if _correction_tracker is None:
        _correction_tracker = CorrectionTracker()
    return _correction_tracker


def record_correction(
    original_by: str,
    original_value: str,
    corrected_by: str,
    corrected_value: str,
    success: bool = True
) -> None:
    """Record a selector correction."""
    get_correction_tracker().record_correction(
        original_by, original_value, corrected_by, corrected_value, success
    )


def apply_corrections_to_test_files() -> ApplyCorrectionsResult:
    """Apply all successful corrections to their source test files."""
    return get_correction_tracker().apply_all_corrections_to_files()


def export_corrections_report(output_file: str = "selector_corrections.json") -> None:
    """Export corrections report to JSON file."""
    get_correction_tracker().export_corrections_report(output_file)
