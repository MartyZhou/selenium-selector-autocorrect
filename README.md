# Selenium Selector AutoCorrect

A Python package that automatically corrects Selenium element selectors using AI when they fail, reducing test maintenance and improving test reliability.

## Features

- **Automatic Selector Correction**: When a WebDriverWait times out, the package uses AI to analyze the page and suggest working alternatives
- **Local AI Integration**: Uses a local AI service with OpenAI-compatible API
- **Correction Tracking**: Records all corrections with source file and line information
- **Optional Auto-Update**: Can automatically update test files with corrected selectors
- **Zero Code Changes**: Works by hooking into Selenium's WebDriverWait

## Installation

```bash
pip install selenium-selector-autocorrect
```

## Quick Start

```python
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_selector_autocorrect import install_auto_correct_hook

install_auto_correct_hook()

driver = webdriver.Chrome()
driver.get("https://example.com")

element = WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.ID, "some-element"))
)
```

## Configuration

Configure via environment variables:

- `LOCAL_AI_API_URL`: URL of local AI service (default: `http://localhost:8765`)
- `SELENIUM_AUTO_CORRECT`: Enable/disable auto-correction (default: `"1"`)
- `SELENIUM_SUGGEST_BETTER`: Suggest better selectors for found elements (default: `"0"`)
- `SELENIUM_AUTO_UPDATE_TESTS`: Auto-update test files with corrections (default: `"0"`)

### Example

```python
import os

os.environ['LOCAL_AI_API_URL'] = 'http://localhost:8765'
os.environ['SELENIUM_AUTO_CORRECT'] = '1'
os.environ['SELENIUM_AUTO_UPDATE_TESTS'] = '1'  # Enable auto-update
```

## Usage

### Basic Usage

```python
from selenium_selector_autocorrect import install_auto_correct_hook

install_auto_correct_hook()
```

### Advanced Usage

```python
from selenium_selector_autocorrect import (
    get_auto_correct,
    get_correction_tracker,
    export_corrections_report,
)

auto_correct = get_auto_correct()
auto_correct.enabled = True

tracker = get_correction_tracker()
export_corrections_report("corrections_report.json")
```

## AI Service Setup

This package requires a local AI service with an OpenAI-compatible API. The following endpoints are used:

- `POST {LOCAL_AI_API_URL}/v1/chat/completions` — chat completions for suggestions
- `POST {LOCAL_AI_API_URL}/v1/workspace/files/read` — read file content
- `POST {LOCAL_AI_API_URL}/v1/workspace/files/edit` — apply edits to files
- `POST {LOCAL_AI_API_URL}/v1/workspace/files/search` — search workspace

## Exporting Reports

```python
from selenium_selector_autocorrect import export_corrections_report

export_corrections_report("corrections_report.json")
```

Report format:

```json
{
  "corrections": [
    {
      "original_by": "id",
      "original_value": "old-selector",
      "corrected_by": "css selector",
      "corrected_value": ".new-selector",
      "success": true,
      "test_file": "/path/to/test.py",
      "test_line": 42,
      "timestamp": "2024-01-31T10:30:00"
    }
  ],
  "summary": {
    "total": 10,
    "successful": 8,
    "generated_at": "2024-01-31T10:35:00"
  }
}
```

## Troubleshooting

**AI service not available**: Ensure the local AI service is running and reachable via `LOCAL_AI_API_URL`.

**Auto-update not running**: Verify `SELENIUM_AUTO_UPDATE_TESTS` is set to `"1"`.

**Selector strings not found when updating**: Check quote styles in your source files match those used in the correction.

## Requirements

- Python >= 3.8
- selenium >= 4.0.0
- requests >= 2.25.0

## License

MIT

## Contributing

Please follow PEP 8, add tests for new features, and update documentation when changing behavior.

See [CHANGELOG.md](CHANGELOG.md) for release notes and version history.
