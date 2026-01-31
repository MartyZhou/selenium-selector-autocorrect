"""Example: Using correction tracking."""

from selenium_selector_autocorrect import (
    install_auto_correct_hook,
    get_correction_tracker,
    export_corrections_report,
)

# Install the hook
install_auto_correct_hook()

# ... run your Selenium tests ...

# Export corrections report
tracker = get_correction_tracker()
export_corrections_report("corrections.json")

print(f"Total corrections: {len(tracker.get_corrections())}")
print(f"Successful corrections: {len(tracker.get_successful_corrections())}")
