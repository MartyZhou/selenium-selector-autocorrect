"""Correction tracker for recording and applying selector fixes."""

import json
import logging
import os
import re
import traceback
from datetime import datetime
from pathlib import Path
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
        # Configurable import pattern - set via environment variable for project-specific structure
        self._import_pattern: str = os.environ.get("SELENIUM_IMPORT_PATTERN", r'from\s+([\w.]+)\s+import')

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
                # Prioritize test files first
                if 'test_' in filename:
                    test_file = filename
                    test_line = frame.lineno
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
            
            # Get all files that need to be updated (test file + referenced files)
            files_to_update = self._find_files_with_selector(
                test_file,
                correction["original_value"]
            )
            
            updated_count = 0
            failed_count = 0
            
            for file_path in files_to_update:
                result = self.update_test_file_via_service(
                    file_path,
                    correction["original_by"],
                    correction["original_value"],
                    correction["corrected_by"],
                    correction["corrected_value"]
                )
                if result.get("success"):
                    updated_count += 1
                    logger.info(f"[AUTO-UPDATE] Successfully updated {file_path}")
                else:
                    failed_count += 1
                    logger.warning(f"[AUTO-UPDATE] Failed to update {file_path}: {result.get('errors', [])}")
            
            if updated_count > 0:
                logger.info(f"[AUTO-UPDATE] Updated {updated_count} file(s), {failed_count} failed")
        except Exception as e:
            logger.warning(f"[AUTO-UPDATE] Error updating test file: {e}")

    def _find_files_with_selector(self, test_file: str, selector_value: str) -> List[str]:
        """Find all files that contain the selector and are used by the test file.
        
        Backward search strategy:
        1. Search for selector text in all Python files (fast workspace grep)
        2. Extract all imports from test file (with recursion for nested imports)
        3. Return only files that contain the selector AND are imported by the test
        
        This is efficient because:
        - Workspace search is very fast (indexed)
        - We only verify imports for files that actually have the selector
        - Typically finds 1-5 files instead of checking 100s
        """
        files_with_selector: List[str] = []
        
        try:
            logger.debug(f"[BACKWARD SEARCH] Searching for selector: {selector_value}")
            
            # Step 1: Search for files containing the selector (fast workspace search)
            # Try different search queries since literal string search may fail with special characters
            workspace_files = []
            search_queries = [
                selector_value,  # Try full selector first
                # Strip common CSS selector wrappers and search for cleaner text
                selector_value.replace('[', '').replace(']', '').replace('"', '').replace("'", '').strip(),
            ]
            
            logger.debug(f"[BACKWARD SEARCH] Will try {len(search_queries)} search queries")
            for i, search_query in enumerate(search_queries):
                logger.debug(f"[BACKWARD SEARCH] Query {i+1}: {search_query[:100]}")
                if search_query and not workspace_files:
                    files = self._workspace_search_for_selector(search_query)
                    if files:
                        workspace_files = files
                        logger.debug(f"[BACKWARD SEARCH] ✓ Found {len(files)} matches with query {i+1}")
                        break
                    else:
                        logger.debug(f"[BACKWARD SEARCH] ✗ No matches with query {i+1}")
            
            logger.info(f"[BACKWARD SEARCH] Workspace search found {len(workspace_files)} file(s)")
            
            if not workspace_files:
                logger.debug(f"[BACKWARD SEARCH] No matches found with workspace search")
                logger.info(f"[AUTO-UPDATE] Found selector in 0 file(s): []")
                return files_with_selector
            
            # Step 2: Extract all imports from test file (with recursion for nested imports)
            all_imports = self._extract_all_imports_from_test(test_file)
            logger.debug(f"[BACKWARD SEARCH] Test file imports {len(all_imports)} files")
            
            # Normalize paths for comparison
            test_file_normalized = os.path.normpath(test_file)
            all_imports_normalized = {os.path.normpath(f) for f in all_imports}
            
            # Step 3: Verify which matched files are actually used by the test
            for file_path in workspace_files:
                file_path_normalized = os.path.normpath(file_path)
                
                # Check if this is the test file itself
                if file_path_normalized == test_file_normalized:
                    logger.debug(f"[BACKWARD SEARCH] ✓ Selector in test file: {file_path}")
                    files_with_selector.append(file_path)
                    continue
                
                # Check if this file is in the imports (direct match)
                if file_path_normalized in all_imports_normalized:
                    logger.debug(f"[BACKWARD SEARCH] ✓ Selector in imported file: {file_path}")
                    files_with_selector.append(file_path)
                    continue
                
                # Check if the file path matches any import by filename
                # (handles different path separators and relative vs absolute paths)
                file_name = os.path.basename(file_path)
                for imported_file in all_imports:
                    if os.path.basename(imported_file) == file_name:
                        # Verify it's the same file by checking if paths end the same way
                        imported_parts = imported_file.replace('\\', '/').split('/')
                        file_parts = file_path.replace('\\', '/').split('/')
                        
                        # Compare the last N parts of the path
                        min_parts = min(len(imported_parts), len(file_parts))
                        if imported_parts[-min_parts:] == file_parts[-min_parts:]:
                            logger.debug(f"[BACKWARD SEARCH] ✓ Selector in imported file: {file_path}")
                            files_with_selector.append(imported_file)  # Use the full path from imports
                            break
                else:
                    logger.debug(f"[BACKWARD SEARCH] ✗ Selector in unrelated file: {file_path}")
        
        except Exception as e:
            logger.debug(f"[BACKWARD SEARCH] Error during search: {e}")
        
        logger.info(f"[AUTO-UPDATE] Found selector in {len(files_with_selector)} file(s): {files_with_selector}")
        return files_with_selector
    
    def _workspace_search_for_selector(self, selector_value: str) -> List[str]:
        """Try to find files using workspace search API. Returns empty list if not found or API unavailable."""
        try:
            # Use dedicated search endpoint (not the unified AI endpoint)
            search_url = f"{self._local_ai_url}/v1/workspace/files/search"
            # Prefer a narrower search first (avoids huge workspaces like venv), then fall back.
            preferred_pattern = os.environ.get("SELENIUM_WORKSPACE_SEARCH_FILE_PATTERN", "automation_tools/**/*.py")
            patterns_to_try = [preferred_pattern, "**/*.py"]
            seen_patterns = set()

            for file_pattern in patterns_to_try:
                if not file_pattern or file_pattern in seen_patterns:
                    continue
                seen_patterns.add(file_pattern)

                search_payload = {
                    "query": selector_value,
                    "filePattern": file_pattern,
                    "maxResults": 50
                }

                logger.debug(f"[WORKSPACE-SEARCH-REQUEST] URL: {search_url}")
                logger.debug(f"[WORKSPACE-SEARCH-REQUEST] Payload: {search_payload}")

                response = requests.post(search_url, json=search_payload, timeout=30)

                logger.debug(f"[WORKSPACE-SEARCH-RESPONSE] Status: {response.status_code}")
                logger.debug(f"[WORKSPACE-SEARCH-RESPONSE] Headers: {dict(response.headers)}")
                logger.debug(f"[WORKSPACE-SEARCH-RESPONSE] Body length: {len(response.text)} chars")

                if not response.ok:
                    logger.debug(f"[WORKSPACE-SEARCH-RESPONSE] Body: {response.text[:500]}")
                    logger.debug(f"[WORKSPACE-SEARCH] Request failed: {response.status_code}")
                    continue

                search_results = response.json()
                logger.debug(f"[WORKSPACE-SEARCH-RESPONSE] Parsed JSON keys: {list(search_results.keys())}")
                logger.debug(f"[WORKSPACE-SEARCH-RESPONSE] Full response: {search_results}")

                file_paths: List[str] = []

                # Handle dedicated endpoint 'results' markdown format
                results_text = search_results.get("results", "")
                logger.debug(f"[WORKSPACE-SEARCH] Results text length: {len(results_text)} chars")
                logger.debug(f"[WORKSPACE-SEARCH] Results text preview: {results_text[:300]}")

                if results_text and "No matches found" not in results_text:
                    logger.debug(f"[WORKSPACE-SEARCH] Parsing markdown results ({len(results_text)} chars)")
                    for line in results_text.split('\n'):
                        if line.startswith('## ') and line.endswith('.py'):
                            file_path = line[3:].strip()
                            if '__pycache__' not in file_path and not file_path.endswith('.pyc') and file_path not in file_paths:
                                file_paths.append(file_path)
                                logger.debug(f"[WORKSPACE-SEARCH] Added file: {file_path}")
                else:
                    logger.debug(f"[WORKSPACE-SEARCH] No results in response")

                if file_paths:
                    logger.info(
                        f"[WORKSPACE-SEARCH] Found {len(file_paths)} file(s) with selector (pattern={file_pattern})"
                    )
                    return file_paths

                logger.debug(f"[WORKSPACE-SEARCH] No files found (pattern={file_pattern})")

            return []
            
        except Exception as e:
            logger.error(f"[WORKSPACE-SEARCH-ERROR] Failed: {type(e).__name__}: {str(e)}")
            logger.debug(f"[WORKSPACE-SEARCH-ERROR] Details: {e}", exc_info=True)
            return []
    
    def _extract_all_imports_from_test(self, test_file: str, max_depth: int = 3, visited: Optional[set] = None) -> List[str]:  # noqa: A006
        """Extract all imported files from test file recursively.
        
        Used by backward search to verify if a file is actually imported by the test.
        Only recurses into page objects (not utilities) for efficiency.
        """
        if visited is None:
            visited = set()
        
        if test_file in visited or max_depth <= 0:
            return []
        
        visited.add(test_file)
        all_imports = []
        
        try:
            direct_imports = self._extract_imported_files(test_file)
            all_imports.extend(direct_imports)
            
            # Recursively extract imports from page objects only
            if max_depth > 1:
                for imported_file in direct_imports:
                    if imported_file not in visited and self._is_page_object_file(imported_file):
                        nested = self._extract_all_imports_from_test(imported_file, max_depth - 1, visited)
                        all_imports.extend(nested)
        
        except Exception as e:
            logger.debug(f"[IMPORT EXTRACTION] Error: {e}")
        
        return all_imports
    
    def _is_page_object_file(self, file_path: str) -> bool:
        """Check if a file is likely a page object or steps file (not a utility or base class)."""
        file_lower = file_path.lower()
        
        # Include: Page objects, Dialogs, Modals, Components, Steps
        if any(pattern in file_lower for pattern in ['page.py', 'dialog.py', 'modal.py', 'section.py', 'steps.py', 'step.py']):
            return True
        
        # Include: Files in component/header/steps directories
        if any(pattern in file_lower for pattern in ['component', 'header', 'footer', 'sidebar', '/steps/', '\\steps\\']):
            return True
        
        # Exclude: Utilities, base classes, helpers, drivers, clients
        if any(pattern in file_lower for pattern in ['utility.py', 'helper.py', 'base.py', 'util.py', '__init__.py', 'driver.py', 'client.py']):
            return False
        
        return False

    def _extract_imported_files(self, test_file: str) -> List[str]:
        """Extract imported page object file paths from a test file."""
        imported_files: List[str] = []
        
        try:
            # Read the test file content via dedicated endpoint
            read_url = f"{self._local_ai_url}/v1/workspace/files/read"
            read_payload = {"filePath": test_file}
            
            logger.debug(f"[FILE-READ-REQUEST] URL: {read_url}")
            logger.debug(f"[FILE-READ-REQUEST] Payload: {read_payload}")
            
            read_response = requests.post(read_url, json=read_payload, timeout=30)
            
            logger.debug(f"[FILE-READ-RESPONSE] Status: {read_response.status_code}")
            logger.debug(f"[FILE-READ-RESPONSE] Headers: {dict(read_response.headers)}")
            logger.debug(f"[FILE-READ-RESPONSE] Body length: {len(read_response.text)} chars")
            
            if not read_response.ok:
                logger.debug(f"[FILE-READ-RESPONSE] Body: {read_response.text[:500]}")
                return imported_files
            
            file_content = read_response.json()
            logger.debug(f"[FILE-READ-RESPONSE] Parsed JSON keys: {list(file_content.keys())}")
            logger.debug(f"[FILE-READ-RESPONSE] Full response: {file_content}")
            
            if not file_content.get("success"):
                logger.debug(f"[FILE-READ] Read failed: success={file_content.get('success')}")
                return imported_files
            
            content = file_content.get("content", "")
            logger.debug(f"[FILE-READ] Content length: {len(content)} chars")
            
            # Pattern to match imports - configurable via SELENIUM_IMPORT_PATTERN env var
            for match in re.finditer(self._import_pattern, content):
                module_path = match.group(1)
                # Convert module path to file path
                file_path = self._module_to_file_path(module_path, test_file)
                if file_path:
                    imported_files.append(file_path)
            
            # Also extract from imports in step functions and page objects
            # Pattern: from <path> import <class>
            step_import_pattern = r'from\s+([\w.]+)\s+import\s+([\w,\s]+)'
            for match in re.finditer(step_import_pattern, content):
                module_path = match.group(1)
                # Include Page classes and step files (configurable via environment variable)
                keywords = os.environ.get("SELENIUM_IMPORT_KEYWORDS", "Page,.steps.,steps").split(",")
                if any(keyword.strip() in module_path for keyword in keywords):
                    file_path = self._module_to_file_path(module_path, test_file)
                    if file_path:
                        imported_files.append(file_path)
        
        except Exception as e:
            logger.debug(f"[IMPORT EXTRACTION] Error: {e}")
        
        return imported_files

    def _module_to_file_path(self, module_path: str, reference_file: str) -> Optional[str]:
        """Convert a Python module path to a file path."""
        try:
            # Extract the root package name from module_path
            parts = module_path.split('.')
            if not parts:
                return None
            
            root_package = parts[0]
            ref_path = Path(reference_file)
            
            # Find the root package directory by going up from the reference file
            current = ref_path.parent
            package_root = None
            
            while current.parent != current:
                if (current / root_package).exists():
                    package_root = current / root_package
                    break
                current = current.parent
            
            if not package_root:
                return None
            
            # Convert module path to relative path, removing the root package
            relative_parts = parts[1:]  # Remove root package prefix
            if not relative_parts:
                return None
            
            relative_path = Path(*relative_parts)
            file_path = package_root / relative_path.with_suffix('.py')
            
            if file_path.exists():
                return str(file_path).replace('\\', '/')
            
        except Exception as e:
            logger.debug(f"[MODULE CONVERSION] Error converting {module_path}: {e}")
        
        return None

    def update_test_file_via_service(
        self,
        file_path: str,
        original_by: str,
        original_value: str,
        corrected_by: str,
        corrected_value: str
    ) -> Dict[str, Any]:
        try:
            # Read the file using dedicated endpoint
            read_url = f"{self._local_ai_url}/v1/workspace/files/read"
            read_payload = {"filePath": file_path}
            
            logger.debug(f"[FILE-EDIT-READ-REQUEST] URL: {read_url}")
            logger.debug(f"[FILE-EDIT-READ-REQUEST] Payload: {read_payload}")
            
            read_response = requests.post(read_url, json=read_payload, timeout=30)
            
            logger.debug(f"[FILE-EDIT-READ-RESPONSE] Status: {read_response.status_code}")
            logger.debug(f"[FILE-EDIT-READ-RESPONSE] Headers: {dict(read_response.headers)}")
            logger.debug(f"[FILE-EDIT-READ-RESPONSE] Body length: {len(read_response.text)} chars")
            
            read_response.raise_for_status()
            file_content = read_response.json()
            
            logger.debug(f"[FILE-EDIT-READ-RESPONSE] Parsed JSON keys: {list(file_content.keys())}")

            if not file_content.get("success"):
                logger.error(f"[FILE-EDIT] Read failed: {file_content}")
                return {"success": False, "errors": ["Could not read file"]}

            content = file_content.get("content", "")
            logger.debug(f"[FILE-EDIT] Read {len(content)} chars from {file_path}")

            def _strategy_to_by_token(strategy: str) -> Optional[str]:
                s = (strategy or "").strip().lower()
                mapping = {
                    "css selector": "CSS_SELECTOR",
                    "css": "CSS_SELECTOR",
                    "xpath": "XPATH",
                    "id": "ID",
                    "name": "NAME",
                    "class name": "CLASS_NAME",
                    "class": "CLASS_NAME",
                    "tag name": "TAG_NAME",
                    "tag": "TAG_NAME",
                    "link text": "LINK_TEXT",
                    "partial link text": "PARTIAL_LINK_TEXT",
                }
                return mapping.get(s)

            corrected_by_token = _strategy_to_by_token(corrected_by)

            # Prefer strategy-aware replacements like: By.XPATH, '<old>' -> By.ID, '<new>'
            # This prevents invalid updates such as leaving By.XPATH with an id value.
            replacements: List[Dict[str, str]] = []
            if corrected_by_token:
                # Find all occurrences of the selector value inside a By.<TOKEN>, '<value>' pair.
                # We intentionally allow any existing By token to be replaced.
                locator_pattern = re.compile(
                    r"By\\.[A-Z_]+(\\s*,\\s*)(['\"])" + re.escape(original_value) + r"\\2"
                )

                for match in locator_pattern.finditer(content):
                    quote = match.group(2)
                    escaped_corrected_value = corrected_value.replace(quote, f"\\{quote}")
                    old_substring = match.group(0)
                    new_substring = f"By.{corrected_by_token}{match.group(1)}{quote}{escaped_corrected_value}{quote}"
                    if old_substring != new_substring:
                        replacements.append({"oldString": old_substring, "newString": new_substring})

                if replacements:
                    logger.debug(f"[FILE-EDIT] Prepared {len(replacements)} strategy-aware replacement(s)")
                else:
                    logger.debug("[FILE-EDIT] No strategy-aware matches found")
            
            # If we couldn't find a By.<TOKEN>, '<value>' match, fall back to value-only replacement
            # ONLY when the strategy does not change (or we don't know the corrected strategy).
            if not replacements:
                corrected_by_normalized = (corrected_by or "").strip().lower()
                original_by_normalized = (original_by or "").strip().lower()

                if corrected_by_token and corrected_by_normalized != original_by_normalized:
                    logger.warning(
                        "[FILE-EDIT] Strategy changed but no locator match found; refusing unsafe value-only update"
                    )
                    return {
                        "success": False,
                        "errors": [
                            "Strategy changed (e.g. xpath -> id) but locator tuple not found in file; skipping unsafe edit"
                        ],
                    }

                old_patterns = [
                    f'"{original_value}"',
                    f"'{original_value}'",
                ]

                found_pattern = None
                new_pattern = None
                for old_pattern in old_patterns:
                    if old_pattern in content:
                        found_pattern = old_pattern
                        logger.debug(f"[FILE-EDIT] Found value-only pattern: {old_pattern[:100]}")

                        # Choose quote style based on what's in the corrected value
                        if "'" in corrected_value and '"' not in corrected_value:
                            new_pattern = f'"{corrected_value}"'
                        elif '"' in corrected_value and "'" not in corrected_value:
                            new_pattern = f"'{corrected_value}'"
                        elif "'" in corrected_value and '"' in corrected_value:
                            if old_pattern.startswith('"'):
                                escaped_value = corrected_value.replace('"', '\\"')
                                new_pattern = f'"{escaped_value}"'
                            else:
                                escaped_value = corrected_value.replace("'", "\\'")
                                new_pattern = f"'{escaped_value}'"
                        else:
                            new_pattern = f'"{corrected_value}"' if old_pattern.startswith('"') else f"'{corrected_value}'"

                        break

                if not found_pattern or new_pattern is None:
                    logger.warning(f"[FILE-EDIT] Could not find selector: {original_value[:50]}")
                    return {"success": False, "errors": [f"Could not find selector: {original_value[:50]}..."]}

                replacements = [{"oldString": found_pattern, "newString": new_pattern}]

            # Use dedicated endpoint for edit (supports multiple replacements)
            edit_url = f"{self._local_ai_url}/v1/workspace/files/edit"
            edit_payload = {"filePath": file_path, "replacements": replacements}
            
            logger.debug(f"[FILE-EDIT-REQUEST] URL: {edit_url}")
            logger.debug(f"[FILE-EDIT-REQUEST] Payload: {edit_payload}")
            
            edit_response = requests.post(edit_url, json=edit_payload, timeout=30)
            
            logger.debug(f"[FILE-EDIT-RESPONSE] Status: {edit_response.status_code}")
            logger.debug(f"[FILE-EDIT-RESPONSE] Headers: {dict(edit_response.headers)}")
            logger.debug(f"[FILE-EDIT-RESPONSE] Body length: {len(edit_response.text)} chars")
            logger.debug(f"[FILE-EDIT-RESPONSE] Body: {edit_response.text[:1000]}")
            
            edit_response.raise_for_status()
            result: Dict[str, Any] = edit_response.json()
            
            logger.debug(f"[FILE-EDIT-RESPONSE] Parsed JSON: {result}")
            logger.info(f"[FILE-EDIT] File update result: success={result.get('success')}")
            return result
        except requests.exceptions.ConnectionError as e:
            logger.error(f"[FILE-EDIT-ERROR] Connection failed: {e}")
            logger.warning(f"[LOCAL AI SERVICE] Not available at {self._local_ai_url}")
            return {"success": False, "errors": ["Local AI service not available"]}
        except Exception as e:
            logger.error(f"[FILE-EDIT-ERROR] {type(e).__name__}: {str(e)}")
            logger.debug(f"[FILE-EDIT-ERROR] Details: {e}", exc_info=True)
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
