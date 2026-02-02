# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] - 2026-02-02

### Fixed
- Removed unused imports and instance variables in correction_tracker
- Implemented missing `_file_contains_selector()` method
- Cleaned up documentation and README formatting
- Updated docstrings for clarity

## [0.1.1] - 2026-02-01

### Added
- `suggest_better_selector()` now properly invoked on successful element finds
- Complete type annotations with mypy --strict compliance
- TypedDict definitions for structured record types
- TYPE_CHECKING imports for circular import prevention

### Fixed
- Fixed logging prefix to use `[AUTO-SUGGEST]` for better selector suggestions
- Improved type safety throughout codebase

## [0.1.0] - 2026-01-31

### Added
- Initial release of selenium-selector-autocorrect
- Automatic selector correction using AI when WebDriverWait times out
- Support for local AI services with OpenAI-compatible API
- Correction tracking with source file and line number detection
- Optional automatic test file updates with `SELENIUM_AUTO_UPDATE_TESTS`
- Correction report export in JSON format
- Configurable via environment variables
- Hook-based integration with Selenium WebDriverWait via `install_auto_correct_hook()`
- Page element analysis and context gathering
- Caching of corrections and suggestions
- Detailed logging of correction attempts

## [Unreleased]

### Planned
- Support for additional AI providers
- Enhanced selector analysis algorithms
- Batch correction updates
- Integration with popular test frameworks
- Performance optimizations
- Extended test coverage
