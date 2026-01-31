# Copilot Instructions for Selenium Selector AutoCorrect

## Project Overview

Selenium Selector AutoCorrect is a Python package that automatically corrects Selenium element selectors using AI when they fail. It reduces test maintenance by hooking into WebDriverWait and suggesting working alternatives when timeouts occur.

**Key Technologies:**
- Python 3.8+
- Selenium 4.0+
- Local AI service with OpenAI-compatible API
- Test Framework: pytest

**GitHub Repository:** https://github.com/MartyZhou/selenium-selector-autocorrect

## Repository Structure

```
selector_autocorrect/
├── __init__.py               # Public API exports
├── auto_correct.py           # Core auto-correction logic
├── ai_providers.py           # AI provider implementation (LocalAIProvider)
├── correction_tracker.py     # Tracks and reports corrections
├── wait_hook.py              # WebDriverWait hook installation
└── py.typed                  # PEP 561 marker for type hints
```

## Development Guidelines

### Code Style
- Follow PEP 8 style guide
- Use type annotations for better maintainability
- Use Google-style docstrings for public APIs
- Write pytest tests for new features
- Maintain code coverage above 80%

### Module Responsibilities

#### auto_correct.py - Core Logic
- SelectorAutoCorrect class: Main engine for selector correction
- Orchestrates AI provider calls, handles timeout logic, manages state
- When modifying: Ensure backward compatibility with existing test hooks

#### ai_providers.py - AI Integration
- Abstract AIProvider base class
- LocalAIProvider implementation for local AI service
- When modifying: Ensure new providers maintain consistent interface
- Important: Handle API errors gracefully with fallback behavior

#### correction_tracker.py - Recording & Reporting
- CorrectionTracker class: Records all selector corrections with metadata
- Stores source file/line info, generates reports
- When modifying: Preserve backward compatibility for report format

#### wait_hook.py - Selenium Integration
- install_auto_correct_hook(): Monkey-patches WebDriverWait
- Minimal, clean hook implementation
- When modifying: Test thoroughly with actual Selenium WebDriver

### Key Features

1. Zero code changes required - users only need to call install_auto_correct_hook()
2. Local AI provider support with OpenAI-compatible API
3. Correction tracking with full metadata for audit and auto-update capabilities
4. Environment configuration - all settings via environment variables
5. Graceful degradation - fallback behavior when AI is unavailable

## Configuration

Environment variables:
- LOCAL_AI_API_URL: Local AI service endpoint (default: http://localhost:8765)
- SELENIUM_AUTO_CORRECT: Enable/disable (default: "1")
- SELENIUM_SUGGEST_BETTER: Suggest better selectors (default: "0")
- SELENIUM_AUTO_UPDATE_TESTS: Auto-update test files (default: "0")

## Common Tasks

### Adding a New AI Provider
1. Create new class inheriting from AIProvider in ai_providers.py
2. Implement suggest_selector() and is_available() methods
3. Add to get_provider() factory function
4. Update environment variable documentation
5. Add tests for new provider

### Modifying Hook Behavior
1. Changes to wait_hook.py require testing with real Selenium WebDriver
2. Ensure compatibility with Selenium 4.0+
3. Test with both local and remote WebDriver instances
4. Verify no performance regression

### Updating Correction Tracking
1. Maintain backward compatibility of CorrectionTracker
2. Ensure report format can be parsed by external tools
3. Update export_corrections_report() if format changes
4. Add migration path for existing correction records

## Testing

```bash
pytest
pytest --cov=src/selenium_selector_autocorrect
pytest tests/test_auto_correct.py
```

Test with actual WebDriver instances when possible, not just mocks, to catch integration issues.

## Common Pitfalls

1. Threading/Concurrency: WebDriver is not thread-safe; test concurrent usage carefully
2. AI Provider Errors: Always wrap AI calls in try-except; implement fallback behavior
3. File Path Handling: Use pathlib.Path for cross-platform compatibility
4. Selector Mutations: Don't modify test file source code without user consent unless SELENIUM_AUTO_UPDATE_TESTS=1

## Contribution Checklist

- [ ] Code follows PEP 8 style
- [ ] Type hints present for all functions
- [ ] Docstrings document public APIs
- [ ] Tests added/updated with new functionality
- [ ] Backward compatibility maintained
- [ ] Environment variable documentation updated
- [ ] No performance regression introduced
- [ ] Works with Selenium 4.0+ and Python 3.8+

## Documentation References

- Selenium Documentation: https://selenium.dev/documentation/webdriver/
- PyPI Package: https://pypi.org/project/selenium-selector-autocorrect/
- GitHub Repository: https://github.com/MartyZhou/selenium-selector-autocorrect
- Main README: See README.md for user-facing documentation

## Code Review Focus

1. AI Provider Integration: Robust error handling and fallback behavior
2. Selenium Compatibility: No breaking changes with WebDriver API
3. Performance: No significant slowdown on failed element location
4. Type Safety: Type hints consistent and complete
5. Backward Compatibility: No breaking changes to public API
