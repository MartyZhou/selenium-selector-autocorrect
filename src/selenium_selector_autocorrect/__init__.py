"""Selenium Selector AutoCorrect

A Python package that automatically corrects Selenium element selectors using AI
when they fail, reducing test maintenance and improving test reliability.

Usage:
    from selenium_selector_autocorrect import install_auto_correct_hook
    
    install_auto_correct_hook()

Environment Variables:
    LOCAL_AI_API_URL: URL of local AI service (default: http://localhost:8765)
    SELENIUM_AUTO_CORRECT: Enable auto-correction (default: "1")
    SELENIUM_SUGGEST_BETTER: Suggest better selectors for found elements (default: "0")
    SELENIUM_AUTO_UPDATE_TESTS: Auto-update test files with corrections (default: "0")
"""

__version__ = "1.0.0"

from .ai_providers import AIProvider, LocalAIProvider, configure_provider, get_provider
from .auto_correct import (
    SelectorAutoCorrect,
    configure_auto_correct,
    get_auto_correct,
    set_auto_correct_enabled,
)
from .correction_tracker import (
    CorrectionTracker,
    apply_corrections_to_test_files,
    export_corrections_report,
    get_correction_tracker,
    record_correction,
)
from .wait_hook import install_auto_correct_hook, uninstall_auto_correct_hook

__all__ = [
    "__version__",
    "SelectorAutoCorrect",
    "get_auto_correct",
    "set_auto_correct_enabled",
    "configure_auto_correct",
    "CorrectionTracker",
    "get_correction_tracker",
    "record_correction",
    "apply_corrections_to_test_files",
    "export_corrections_report",
    "AIProvider",
    "LocalAIProvider",
    "get_provider",
    "configure_provider",
    "install_auto_correct_hook",
    "uninstall_auto_correct_hook",
]

